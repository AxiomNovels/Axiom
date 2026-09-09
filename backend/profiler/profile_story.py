"""Generate philosophy and storytelling baselines for one novel.

Run from backend:
    python -m profiler.profile_story NOVEL_ID --save
    python -m profiler.profile_story NOVEL_ID --profile storytelling --save --yes
"""

import argparse

from profiler.comments import load_comments, select_story_comments
from profiler.gemini import generate_novel_profile
from profiler.profile_novel import database_client, fetch_novel
from profiler.prompt import PHILOSOPHY_MEASURES, STORYTELLING_MEASURES, build_novel_profile_prompt
from profiler.sources import collect_public_comments


PROFILE_TYPES = {
    "philosophy": ("philosophy_profiles", PHILOSOPHY_MEASURES),
    "storytelling": ("storytelling_style_profiles", STORYTELLING_MEASURES),
}


def save_profile(novel_id: int, table: str, result: dict) -> None:
    database_client(for_write=True).table(table).upsert(
        {"novel_id": novel_id, **result["scores"]}, on_conflict="novel_id"
    ).execute()


def print_preview(novel: dict, profile_type: str, measures, result: dict, comment_count: int) -> None:
    print(f"\n{novel['title']} — {profile_type.title()} profile")
    print("-" * 60)
    for measure in measures:
        print(f"{measure.replace('_', ' ').title():25} {result['scores'][measure]:3}")
    print(f"{'Confidence':25} {result['confidence']:3}")
    print(f"Comments analyzed:         {comment_count}")
    print(f"Evidence: {result['evidence_summary']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate AI philosophy and storytelling baselines")
    parser.add_argument("novel_id", type=int)
    parser.add_argument("--profile", choices=["philosophy", "storytelling", "all"], default="all")
    parser.add_argument("--comments", help="Use a UTF-8 comment file instead of reading links")
    parser.add_argument("--no-fetch-comments", action="store_true", help="Use only synopsis and tags")
    parser.add_argument("--save", action="store_true", help="Offer to save after preview")
    parser.add_argument("--yes", action="store_true", help="Save without confirmation; requires --save")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    novel = fetch_novel(args.novel_id)
    if args.comments:
        raw_comments = load_comments(args.comments)
    elif args.no_fetch_comments:
        raw_comments = []
    else:
        raw_comments, _ = collect_public_comments(novel.get("reading_links") or [])
    comments = select_story_comments(raw_comments)

    requested = PROFILE_TYPES if args.profile == "all" else {args.profile: PROFILE_TYPES[args.profile]}
    generated = {}
    for profile_type, (table, measures) in requested.items():
        result = generate_novel_profile(build_novel_profile_prompt(novel, comments, profile_type), measures)
        generated[profile_type] = (table, result)
        print_preview(novel, profile_type, measures, result, len(comments))

    if not args.save:
        print("\nPreview only. Run again with --save when you want to write these profiles.")
        return
    approved = args.yes or input("\nSave the generated profile(s) to Supabase? [y/N] ").strip().casefold() == "y"
    if not approved:
        print("Not saved.")
        return
    for profile_type, (table, result) in generated.items():
        save_profile(args.novel_id, table, result)
        print(f"Saved {profile_type} profile to {table}.")


if __name__ == "__main__":
    main()
