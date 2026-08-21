import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from profiler.prompt import MEASURES


RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "scores": {
            "type": "OBJECT",
            "properties": {
                measure: {"type": "INTEGER", "minimum": 0, "maximum": 100}
                for measure in MEASURES
            },
            "required": list(MEASURES),
        },
        "confidence": {"type": "INTEGER", "minimum": 0, "maximum": 100},
        "evidence_summary": {"type": "STRING"},
    },
    "required": ["scores", "confidence", "evidence_summary"],
}

IDENTIFICATION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "protagonist_name": {"type": "STRING"},
        "confidence": {"type": "INTEGER", "minimum": 0, "maximum": 100},
        "evidence_summary": {"type": "STRING"},
    },
    "required": ["protagonist_name", "confidence", "evidence_summary"],
}


def validate_profile(data: dict) -> dict:
    if not isinstance(data, dict) or not isinstance(data.get("scores"), dict):
        raise ValueError("Gemini response is missing the scores object")

    scores = data["scores"]
    if set(scores) != set(MEASURES):
        raise ValueError("Gemini response does not contain exactly the six profile measures")

    for measure, value in scores.items():
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 100:
            raise ValueError(f"Invalid score for {measure}: {value!r}")

    confidence = data.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, int) or not 0 <= confidence <= 100:
        raise ValueError(f"Invalid confidence: {confidence!r}")

    summary = data.get("evidence_summary")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("Gemini response is missing an evidence summary")

    return {
        "scores": {measure: scores[measure] for measure in MEASURES},
        "confidence": confidence,
        "evidence_summary": summary.strip(),
    }


def validate_identification(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ValueError("Gemini protagonist identification is not an object")

    name = data.get("protagonist_name")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 120:
        raise ValueError("Gemini returned an invalid protagonist name")
    if name.strip().casefold() in {"unknown", "n/a", "none"}:
        raise ValueError("Gemini could not identify a protagonist")

    confidence = data.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, int) or not 0 <= confidence <= 100:
        raise ValueError(f"Invalid protagonist confidence: {confidence!r}")

    summary = data.get("evidence_summary")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("Gemini returned no protagonist evidence summary")

    return {
        "protagonist_name": name.strip(),
        "confidence": confidence,
        "evidence_summary": summary.strip(),
    }


def request_structured(
    prompt: str,
    response_schema: dict,
    max_output_tokens: int,
    timeout: int = 90,
) -> dict:
    api_key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY in backend/.env")

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{quote(model, safe='')}:generateContent"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": response_schema,
            "temperature": 0.2,
            "maxOutputTokens": max_output_tokens,
        },
    }
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"Gemini API returned HTTP {error.code}: {details}") from error
    except URLError as error:
        raise RuntimeError(f"Could not reach Gemini API: {error.reason}") from error

    try:
        text = body["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
        raise ValueError("Gemini returned an unexpected response") from error


def generate_profile(prompt: str, timeout: int = 90) -> dict:
    return validate_profile(
        request_structured(prompt, RESPONSE_SCHEMA, max_output_tokens=700, timeout=timeout)
    )


def identify_protagonist(prompt: str, timeout: int = 90) -> dict:
    return validate_identification(
        request_structured(
            prompt,
            IDENTIFICATION_SCHEMA,
            max_output_tokens=300,
            timeout=timeout,
        )
    )
