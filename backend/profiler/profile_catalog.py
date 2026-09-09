"""Shared workflow for whole-novel profile generators."""

import argparse

from profiler.comments import load_comments, select_story_comments
from profiler.gemini import generate_novel_profile
from profiler.profile_novel import database_client, fetch_novel
from profiler.prompt import build_novel_profile_prompt
from profiler.sources import collect_public_comments


def parse_profile_args(description: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("novel_id", type=int)
    parser.add_argument("--comments", help="Use a UTF-8 comment file instead of reading links")
    parser.add_argument("--no-fetch-comments", action="store_true", help="Use only synopsis and tags")
    parser.add_argument("--save", action="store_true", help="Offer to save after preview")
    parser.add_argument("--yes", action="store_true", help="Save without confirmation; requires --save")
    return parser.parse_args()


def run_profile(profile_type: str, table: str, measures, args: argparse.Namespace) -> None:
    novel = fetch_novel(args.novel_id)
    if args.comments:
        raw_comments = load_comments(args.comments)
    elif args.no_fetch_comments:
        raw_comments = []
    else:
        raw_comments, _ = collect_public_comments(novel.get("reading_links") or [])
    comments = select_story_comments(raw_comments)
    result = generate_novel_profile(
        build_novel_profile_prompt(novel, comments, profile_type), measures
    )

    print(f"\n{novel['title']} — {profile_type.title()} profile")
    print("-" * 60)
    for measure in measures:
        print(f"{measure.replace('_', ' ').title():25} {result['scores'][measure]:3}")
    print(f"{'Confidence':25} {result['confidence']:3}")
    print(f"Comments analyzed:         {len(comments)}")
    print(f"Evidence: {result['evidence_summary']}")

    if not args.save:
        print("\nPreview only. Run again with --save when you want to write this profile.")
        return
    approved = args.yes or input(f"\nSave the {profile_type} profile to Supabase? [y/N] ").strip().casefold() == "y"
    if not approved:
        print("Not saved.")
        return
    database_client(for_write=True).table(table).upsert(
        {"novel_id": args.novel_id, **result["scores"]}, on_conflict="novel_id"
    ).execute()
    print(f"Saved {profile_type} profile to {table}.")
