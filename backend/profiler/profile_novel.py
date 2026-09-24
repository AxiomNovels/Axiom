"""Generate a protagonist baseline for one novel.

Run from backend:
    python -m profiler.profile_novel NOVEL_ID --protagonist "Name" -- save
"""

import argparse
import os
from pathlib import Path

import truststore
from dotenv import load_dotenv
from supabase import create_client

from profiler.comments import load_comments, select_comments
from profiler.gemini import generate_profile, identify_protagonist
from profiler.prompt import MEASURES, build_identification_prompt, build_prompt
from profiler.resolver import resolve_protagonist_name
from profiler.sources import collect_public_comments


BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")
truststore.inject_into_ssl()


def database_client(for_write: bool = False):
    url = os.getenv("SUPABASE_URL")
    key_name = "SUPABASE_SECRET_KEY" if for_write else "SUPABASE_PUBLISHABLE_KEY"
    key = os.getenv(key_name)
    if not url or not key:
        raise RuntimeError(f"Missing SUPABASE_URL or {key_name} in backend/.env")
    return create_client(url, key)


def fetch_novel(novel_id: int) -> dict:
    response = (
        database_client()
        .table("novels")
        .select("id,title,synopsis,genres,tags,reading_links,protagonist_profiles(protagonist_name)")
        .eq("id", novel_id)
        .limit(1)
        .execute()
    )
    if not response.data:
        raise RuntimeError(
            f"Novel ID {novel_id} was not found in the configured Supabase database. "
            "Check the novel ID and your backend/.env connection."
        )
    return response.data[0]


def save_profile(novel_id: int, protagonist_name: str, result: dict) -> None:
    database_client(for_write=True).rpc("save_gemini_protagonist", {
        "p_novel_id": novel_id,
        "p_name": protagonist_name,
        "p_scores": result["scores"],
    }).execute()


def print_preview(
    novel: dict,
    protagonist_name: str,
    result: dict,
    comment_count: int,
    comment_sources: list[str],
    name_source: str,
    name_confidence: int | None,
) -> None:
    print()
    print(f"{novel['title']} — {protagonist_name}")
    print("-" * 60)
    confidence_text = str(name_confidence) if name_confidence is not None else "n/a"
    print(f"Protagonist source:        {name_source} (confidence: {confidence_text})")
    labels = {
        "impulsivity": "Impulsivity",
        "arrogance_pride": "Ego",
        "kinship_friendship": "Kinship and Friendship",
        "romantic_attachment": "Romantic Attachment",
        "sexual_desire": "Lust",
        "selflessness": "Selflessness",
    }
    for measure in MEASURES:
        print(f"{labels[measure]:25} {result['scores'][measure]:3}")
    print(f"{'Confidence':25} {result['confidence']:3}")
    print(f"Comments analyzed:         {comment_count}")
    print(f"Comment source:            {', '.join(comment_sources) or 'None'}")
    print(f"Evidence: {result['evidence_summary']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate one AI protagonist baseline")
    parser.add_argument("novel_id", type=int)
    parser.add_argument("--protagonist", help="Override the stored protagonist name")
    parser.add_argument("--comments", help="Use a UTF-8 comment file instead of reading links")
    parser.add_argument(
        "--no-fetch-comments",
        action="store_true",
        help="Use only synopsis and tags when no comment file is supplied",
    )
    parser.add_argument(
        "--minimum-name-confidence",
        type=int,
        default=75,
        help="Minimum 0-100 confidence required for automatic protagonist detection",
    )
    parser.add_argument("--save", action="store_true", help="Offer to save after preview")
    parser.add_argument("--yes", action="store_true", help="Save without confirmation; requires --save")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not 0 <= args.minimum_name_confidence <= 100:
        raise ValueError("--minimum-name-confidence must be between 0 and 100")

    novel = fetch_novel(args.novel_id)

    if args.comments:
        raw_comments = load_comments(args.comments)
        comment_sources = [f"File: {args.comments}"]
    elif args.no_fetch_comments:
        raw_comments = []
        comment_sources = []
    else:
        raw_comments, comment_sources = collect_public_comments(
            novel.get("reading_links") or []
        )

    protagonist_name = resolve_protagonist_name(novel, args.protagonist)
    name_confidence = None
    if args.protagonist:
        name_source = "command override"
    elif protagonist_name:
        name_source = "stored profile"
    else:
        identification = identify_protagonist(
            build_identification_prompt(novel, raw_comments)
        )
        protagonist_name = identification["protagonist_name"]
        name_confidence = identification["confidence"]
        name_source = "Gemini detection"
        print(
            f"Detected protagonist: {protagonist_name} "
            f"(confidence {name_confidence})"
        )
        if name_confidence < args.minimum_name_confidence:
            raise RuntimeError(
                f"Automatic protagonist confidence {name_confidence} is below the "
                f"required {args.minimum_name_confidence}. Rerun with "
                f"--protagonist \"{protagonist_name}\" after checking the name."
            )

    comments = select_comments(raw_comments, protagonist_name)
    result = generate_profile(build_prompt(novel, protagonist_name, comments))
    print_preview(
        novel,
        protagonist_name,
        result,
        len(comments),
        comment_sources,
        name_source,
        name_confidence,
    )

    if not args.save:
        print("\nPreview only. Run again with --save when you want to write this profile.")
        return

    approved = args.yes or input("\nSave this baseline to Supabase? [y/N] ").strip().casefold() == "y"
    if not approved:
        print("Not saved.")
        return

    save_profile(args.novel_id, protagonist_name, result)
    print("Saved to protagonist_profiles.")


if __name__ == "__main__":
    main()
