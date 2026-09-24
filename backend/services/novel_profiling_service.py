"""Generate, preview and store AI profiles for user-uploaded novels.

Uploading a novel used to be scrape-only. This module adds the profiler step so
a new novel is saved with its protagonist, philosophy and storytelling
profiles, and so the uploader can review those profiles before confirming.

Design rules
------------
* No trait is hard-coded here. Each profile is described by a ProfileSpec whose
  measures are read from profiler/prompt.py on every request, and the API
  returns ready-to-display labels. Add, remove or rename traits (or rewrite the
  prompts) in the profiler and the upload flow follows without edits here or in
  the frontend. A brand-new *kind* of profile is one more ProfileSpec in
  _load_specs().
* Profiling can never block an upload. Every profile is generated and saved
  independently, and every public function below swallows its own errors: a
  failure only marks that profile as failed (or the whole payload as
  unavailable) and the novel is still added.
* What the user previews is what gets saved. The preview response carries a
  short-lived, signed token holding the generated profiles. The add step still
  re-scrapes the page (it never trusts client-supplied novel data) but reuses
  the token instead of paying for a second, different LLM answer. A missing,
  expired, tampered-with or outdated token (for example, the traits changed
  between preview and add) simply means the profiles are regenerated.
* The profiler package is imported lazily, so a problem there cannot stop the
  API from starting.

Public API (used by routes/novels.py)
-------------------------------------
    build_preview(user_id, source, url, novel) -> dict
    finalize(user_id, source, url, novel, novel_id, token) -> dict
    empty_payload(notice) -> dict

All three return the same shape:

    {
      "profiles": [
        {
          "kind": "philosophy", "title": "...", "description": "...",
          "status": "ready" | "saved" | "skipped" | "failed",
          "message": str | None,              # why skipped / failed
          "protagonist_name": str | None,     # protagonist profile only
          "confidence": int | None,           # 0-100, from the profiler
          "evidence_summary": str | None,
          "scores": [{"key": "...", "label": "...", "score": 0-100}, ...],
        },
        ...
      ],
      "token": str | None,    # preview only
      "notice": str | None,   # a message about profiling as a whole
    }
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable

from core.database import create_service_client


logger = logging.getLogger(__name__)

TOKEN_VERSION = 1
TOKEN_TTL_SECONDS = 30 * 60

# Same default the profiler CLI uses (profile_novel --minimum-name-confidence).
# Override with PROFILER_MIN_NAME_CONFIDENCE in backend/.env.
DEFAULT_MIN_PROTAGONIST_CONFIDENCE = 75

STATUS_READY = "ready"      # generated, not stored yet (preview)
STATUS_SAVED = "saved"      # stored in the database
STATUS_SKIPPED = "skipped"  # deliberately not generated; see .message
STATUS_FAILED = "failed"    # generation or storage failed; see .message

UNAVAILABLE_NOTICE = (
    "Profiles are unavailable right now. You can still add the novel without them."
)


# ---------------------------------------------------------------------------
# Display labels
# ---------------------------------------------------------------------------

# Only keys whose label isn't just "the key, capitalised" need an entry.
# Traits that aren't listed (including any added in the future) fall back to
# label_for()'s automatic formatting, e.g. "dream_logic" -> "Dream Logic".
_LABEL_OVERRIDES = {
    "arrogance_pride": "Ego",
    "kinship_friendship": "Kinship and Friendship",
    "sexual_desire": "Lust",
    "self_improvement": "Self-Improvement",
}
_SMALL_WORDS = {"a", "an", "and", "as", "at", "in", "of", "on", "or", "the", "to"}


def label_for(key: str) -> str:
    if key in _LABEL_OVERRIDES:
        return _LABEL_OVERRIDES[key]
    words = [word for word in str(key).split("_") if word]
    if not words:
        return str(key)
    return " ".join(
        word if index and word in _SMALL_WORDS else word.capitalize()
        for index, word in enumerate(words)
    )


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

class ProfileSkipped(Exception):
    """Raised by a generator to skip a profile with a user-facing reason."""


@dataclass
class ProfileResult:
    kind: str
    title: str
    description: str
    status: str = STATUS_FAILED
    message: str | None = None
    scores: dict[str, int] | None = None
    protagonist_name: str | None = None
    confidence: int | None = None
    evidence_summary: str | None = None

    def to_public(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "message": self.message,
            "protagonist_name": self.protagonist_name,
            "confidence": self.confidence,
            "evidence_summary": self.evidence_summary,
            "scores": [
                {"key": key, "label": label_for(key), "score": score}
                for key, score in (self.scores or {}).items()
            ],
        }

    def to_token(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "message": self.message,
            "scores": self.scores,
            "protagonist_name": self.protagonist_name,
            "confidence": self.confidence,
            "evidence_summary": self.evidence_summary,
        }


@dataclass(frozen=True)
class ProfileSpec:
    """Everything the upload flow needs to know about one kind of profile."""

    kind: str
    title: str
    description: str
    measures: tuple[str, ...]
    # (novel, raw_comments, measures) -> {"scores": {...}, "confidence": int,
    #                                     "evidence_summary": str, ...}
    generate: Callable[[dict, list[str], tuple[str, ...]], dict]
    # (service_client, novel_id, result) -> None; raises on failure
    save: Callable[[Any, int, ProfileResult], None]


# ---------------------------------------------------------------------------
# Generators. These only orchestrate the profiler's own building blocks
# (prompts, Gemini calls, comment selection), the same ones the CLI uses.
# ---------------------------------------------------------------------------

def _minimum_name_confidence() -> int:
    try:
        value = int(os.getenv("PROFILER_MIN_NAME_CONFIDENCE", DEFAULT_MIN_PROTAGONIST_CONFIDENCE))
    except ValueError:
        value = DEFAULT_MIN_PROTAGONIST_CONFIDENCE
    return max(0, min(100, value))


def _generate_protagonist(novel: dict, raw_comments: list[str], measures: tuple[str, ...]) -> dict:
    from profiler.comments import select_comments
    from profiler.gemini import generate_profile, identify_protagonist
    from profiler.prompt import build_identification_prompt, build_prompt
    from profiler.resolver import resolve_protagonist_name

    name = resolve_protagonist_name(novel, None)
    if not name:
        identification = identify_protagonist(build_identification_prompt(novel, raw_comments))
        name = identification["protagonist_name"]
        if identification["confidence"] < _minimum_name_confidence():
            # A profile for the wrong character is worse than none, so this
            # mirrors the CLI, which refuses to continue below the threshold.
            raise ProfileSkipped(
                "The protagonist couldn't be identified confidently, "
                "so no protagonist profile was generated."
            )

    comments = select_comments(raw_comments, name)
    result = dict(generate_profile(build_prompt(novel, name, comments)))
    result["protagonist_name"] = name
    return result


def _story_generator(profile_type: str) -> Callable[[dict, list[str], tuple[str, ...]], dict]:
    """Generator for the whole-novel profiles ("philosophy", "storytelling")."""

    def generate(novel: dict, raw_comments: list[str], measures: tuple[str, ...]) -> dict:
        from profiler.comments import select_story_comments
        from profiler.gemini import generate_novel_profile
        from profiler.prompt import build_novel_profile_prompt

        comments = select_story_comments(raw_comments)
        prompt = build_novel_profile_prompt(novel, comments, profile_type)
        return generate_novel_profile(prompt, measures)

    return generate


# ---------------------------------------------------------------------------
# Savers
# ---------------------------------------------------------------------------

def _save_protagonist(client, novel_id: int, result: ProfileResult) -> None:
    # Goes through the same RPC as the profiler CLI so the protagonist
    # baseline used by reader voting stays in sync with the profile.
    if not result.protagonist_name:
        raise ValueError("A protagonist profile needs a protagonist name.")
    client.rpc(
        "save_gemini_protagonist",
        {"p_novel_id": novel_id, "p_name": result.protagonist_name, "p_scores": result.scores},
    ).execute()


def _table_saver(table: str) -> Callable[[Any, int, ProfileResult], None]:
    def save(client, novel_id: int, result: ProfileResult) -> None:
        client.table(table).upsert(
            {"novel_id": novel_id, **(result.scores or {})}, on_conflict="novel_id"
        ).execute()

    return save


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

def _load_specs() -> tuple[ProfileSpec, ...]:
    """Build the profile registry from the profiler's current definitions.

    Called per request rather than at import time so the measures always
    mirror profiler/prompt.py, and so a broken profiler surfaces as a
    profiling failure instead of preventing the API from booting.

    Mirrors routes/admin.py's PROFILES table, which maps kinds to tables.
    """
    from profiler.prompt import MEASURES, PHILOSOPHY_MEASURES, STORYTELLING_MEASURES

    return (
        ProfileSpec(
            kind="protagonist",
            title="Protagonist profile",
            description="The protagonist's psychology, scored 0-100.",
            measures=tuple(MEASURES),
            generate=_generate_protagonist,
            save=_save_protagonist,
        ),
        ProfileSpec(
            kind="philosophy",
            title="Philosophy profile",
            description="The major ideas and themes, scored 0-100.",
            measures=tuple(PHILOSOPHY_MEASURES),
            generate=_story_generator("philosophy"),
            save=_table_saver("philosophy_profiles"),
        ),
        ProfileSpec(
            kind="storytelling",
            title="Storytelling style",
            description="How this story feels to read.",
            measures=tuple(STORYTELLING_MEASURES),
            generate=_story_generator("storytelling"),
            save=_table_saver("storytelling_style_profiles"),
        ),
    )


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def _validated_scores(spec: ProfileSpec, scores: Any) -> dict[str, int]:
    """Return exactly the spec's current measures, in order, as 0-100 ints.

    This is the safety net between whatever the profiler returned and the
    database: unknown extra keys are dropped, and anything missing or out of
    range is an error rather than a silent default.
    """
    if not isinstance(scores, dict):
        raise ValueError("scores must be an object")
    cleaned: dict[str, int] = {}
    for measure in spec.measures:
        value = scores.get(measure)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 100:
            raise ValueError(f"missing or invalid score for {measure!r}: {value!r}")
        cleaned[measure] = int(round(value))
    return cleaned


def _confidence(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 100:
        return None
    return int(value)


def _text(value: Any, limit: int = 1500) -> str | None:
    if not isinstance(value, str):
        return None
    return value.strip()[:limit] or None


def _collect_comments(novel: dict) -> list[str]:
    """Public reader comments used as extra evidence; best effort."""
    try:
        from profiler.sources import collect_public_comments

        comments, _sources = collect_public_comments(novel.get("reading_links") or [])
        return [comment for comment in (comments or []) if isinstance(comment, str)]
    except Exception:
        logger.warning("Couldn't collect reader comments for %r", novel.get("title"), exc_info=True)
        return []


def _run_spec(spec: ProfileSpec, novel: dict, raw_comments: list[str]) -> ProfileResult:
    """Generate one profile. Never raises."""
    result = ProfileResult(kind=spec.kind, title=spec.title, description=spec.description)
    try:
        payload = spec.generate(novel, raw_comments, spec.measures)
        scores = _validated_scores(spec, payload.get("scores"))
        result.protagonist_name = _text(payload.get("protagonist_name"), 200)
        result.confidence = _confidence(payload.get("confidence"))
        result.evidence_summary = _text(payload.get("evidence_summary"))
        result.scores = scores
        result.status = STATUS_READY
    except ProfileSkipped as skip:
        result.status = STATUS_SKIPPED
        result.message = str(skip)
    except Exception:
        logger.exception("Profiler failed for the %s profile of %r", spec.kind, novel.get("title"))
        result.status = STATUS_FAILED
        result.message = "This profile couldn't be generated right now."
    return result


def _generate_all(novel: dict, specs: tuple[ProfileSpec, ...]) -> list[ProfileResult]:
    """Generate every profile concurrently; one failing never affects the rest."""
    raw_comments = _collect_comments(novel)
    with ThreadPoolExecutor(max_workers=max(1, len(specs)), thread_name_prefix="novel-profile") as pool:
        futures = [pool.submit(_run_spec, spec, novel, raw_comments) for spec in specs]
        return [future.result() for future in futures]


# ---------------------------------------------------------------------------
# Preview token
# ---------------------------------------------------------------------------

def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _signing_key() -> bytes:
    secret = os.getenv("PROFILE_TOKEN_SECRET") or os.getenv("SUPABASE_SECRET_KEY")
    if not secret:
        raise RuntimeError("Set PROFILE_TOKEN_SECRET (or SUPABASE_SECRET_KEY) in backend/.env")
    # Derive a purpose-specific key so the service-role key itself is never
    # used directly as an HMAC key.
    return hmac.new(secret.encode("utf-8"), b"axiom-profile-preview-v1", hashlib.sha256).digest()


def _issue_token(user_id: str, source: str, url: str, novel: dict, results: list[ProfileResult]) -> str | None:
    try:
        body = {
            "v": TOKEN_VERSION,
            "uid": str(user_id),
            "src": source,
            "url": url,
            "title": novel.get("title"),
            "exp": int(time.time()) + TOKEN_TTL_SECONDS,
            "profiles": {result.kind: result.to_token() for result in results},
        }
        payload = _b64(json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8"))
        signature = _b64(hmac.new(_signing_key(), payload.encode("ascii"), hashlib.sha256).digest())
        return f"{payload}.{signature}"
    except Exception:
        logger.exception("Couldn't issue a profile preview token")
        return None


def _results_from_token(
    token: str, user_id: str, source: str, url: str, novel: dict, specs: tuple[ProfileSpec, ...]
) -> list[ProfileResult] | None:
    """Return the previewed profiles if the token is valid for this exact
    upload and still matches today's profile definitions; otherwise None."""
    try:
        payload, _, signature = token.partition(".")
        expected = hmac.new(_signing_key(), payload.encode("ascii"), hashlib.sha256).digest()
        if not signature or not hmac.compare_digest(expected, _unb64(signature)):
            return None

        body = json.loads(_unb64(payload))
        if (
            body.get("v") != TOKEN_VERSION
            or body.get("uid") != str(user_id)
            or body.get("src") != source
            or body.get("url") != url
            or body.get("title") != novel.get("title")
            or float(body.get("exp", 0)) < time.time()
        ):
            return None

        entries = body.get("profiles")
        if not isinstance(entries, dict) or set(entries) != {spec.kind for spec in specs}:
            return None

        results: list[ProfileResult] = []
        for spec in specs:
            entry = entries[spec.kind]
            result = ProfileResult(
                kind=spec.kind,
                title=spec.title,
                description=spec.description,
                status=entry["status"],
                message=_text(entry.get("message"), 300),
            )
            if result.status == STATUS_READY:
                result.scores = _validated_scores(spec, entry.get("scores"))
                result.protagonist_name = _text(entry.get("protagonist_name"), 200)
                result.confidence = _confidence(entry.get("confidence"))
                result.evidence_summary = _text(entry.get("evidence_summary"))
            elif result.status not in (STATUS_SKIPPED, STATUS_FAILED):
                return None
            results.append(result)
        return results
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _save_results(specs: tuple[ProfileSpec, ...], novel_id: int, results: list[ProfileResult]) -> list[ProfileResult]:
    """Store every ready profile, each independently. Never raises."""
    spec_by_kind = {spec.kind: spec for spec in specs}
    client = None
    for result in results:
        if result.status != STATUS_READY:
            continue
        try:
            client = client or create_service_client()
            spec_by_kind[result.kind].save(client, novel_id, result)
            result.status = STATUS_SAVED
        except Exception:
            logger.exception("Couldn't save the %s profile for novel %s", result.kind, novel_id)
            result.status = STATUS_FAILED
            result.message = "This profile was generated but couldn't be saved."
            result.scores = None
    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _payload(results: list[ProfileResult], token: str | None = None, notice: str | None = None) -> dict[str, Any]:
    return {"profiles": [result.to_public() for result in results], "token": token, "notice": notice}


def empty_payload(notice: str | None = None) -> dict[str, Any]:
    return _payload([], notice=notice)


def build_preview(user_id: str, source: str, url: str, novel: dict) -> dict[str, Any]:
    """Generate profiles for the preview step. Never raises."""
    try:
        specs = _load_specs()
        results = _generate_all(novel, specs)
        token = _issue_token(user_id, source, url, novel, results)
        notice = None
        if not any(result.status == STATUS_READY for result in results):
            notice = "No profiles could be generated right now. You can still add the novel without them, or search again to retry."
        return _payload(results, token=token, notice=notice)
    except Exception:
        logger.exception("Profile preview failed for %s", url)
        return empty_payload(UNAVAILABLE_NOTICE)


def finalize(
    user_id: str, source: str, url: str, novel: dict, novel_id: int, token: str | None
) -> dict[str, Any]:
    """Store the profiles for a novel that was just inserted. Never raises.

    Reuses the previewed profiles when the token is valid; otherwise generates
    them now. Either way the novel itself is already saved.
    """
    try:
        specs = _load_specs()
        results = _results_from_token(token, user_id, source, url, novel, specs) if token else None
        if results is None:
            results = _generate_all(novel, specs)
        results = _save_results(specs, novel_id, results)
        notice = None
        if not any(result.status == STATUS_SAVED for result in results):
            notice = "The novel was added without profiles."
        return _payload(results, notice=notice)
    except Exception:
        logger.exception("Profile finalisation failed for novel %s", novel_id)
        return empty_payload("The novel was added, but its profiles couldn't be generated or saved.")