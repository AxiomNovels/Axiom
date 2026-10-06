"""Re-profile existing novels after the protagonist trait set changed.

Every novel saved under the old six-trait profile is missing four of the new
traits (and the three retired ones are ignored), so its profile is incomplete
until it is generated again. This walks the catalogue and regenerates them.

Run from backend:

    python -m profiler.regenerate_profiles --dry-run --limit 3   # preview only
    python -m profiler.regenerate_profiles --sleep 2             # all incomplete novels
    python -m profiler.regenerate_profiles --all                 # redo every novel
    python -m profiler.regenerate_profiles --novel-ids 12 15 40  # specific novels

By default only novels whose profile is missing, or missing any of the ten
scores, are processed, so the script is safe to stop and re-run: finished novels
are skipped the next time.

A stored protagonist name is reused. Only novels with no stored name go through
automatic detection, and those below --minimum-name-confidence are skipped and
listed at the end for manual handling (profile_novel --protagonist "Name").
"""

import argparse
import time

from profiler.comments import select_comments
from profiler.gemini import generate_profile, identify_protagonist
from profiler.profile_novel import database_client, fetch_novel, save_profile
from profiler.prompt import MEASURES, build_identification_prompt, build_prompt
from profiler.resolver import resolve_protagonist_name
from profiler.sources import collect_public_comments


PAGE_SIZE = 1000


def fetch_all(client, table: str, columns: str, order_by: str) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        page = (
            client.table(table)
            .select(columns)
            .order(order_by)
            .range(offset, offset + PAGE_SIZE - 1)
            .execute()
            .data
            or []
        )
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            return rows
        offset += PAGE_SIZE


def novels_to_profile(include_complete: bool) -> list[int]:
    client = database_client()
    novel_ids = [row["id"] for row in fetch_all(client, "novels", "id", "id")]
    if include_complete:
        return novel_ids

    complete = set()
    columns = "novel_id," + ",".join(MEASURES)
    for row in fetch_all(client, "protagonist_profiles", columns, "novel_id"):
        if all(row.get(measure) is not None for measure in MEASURES):
            complete.add(row["novel_id"])
    return [novel_id for novel_id in novel_ids if novel_id not in complete]


def regenerate(novel_id: int, minimum_confidence: int, fetch_comments: bool, save: bool):
    novel = fetch_novel(novel_id)

    raw_comments: list[str] = []
    if fetch_comments:
        try:
            raw_comments, _sources = collect_public_comments(novel.get("reading_links") or [])
        except Exception as error:  # comments are extra evidence, never required
            print(f"  (comments unavailable: {error})")

    name = resolve_protagonist_name(novel, None)
    if not name:
        identification = identify_protagonist(build_identification_prompt(novel, raw_comments))
        if identification["confidence"] < minimum_confidence:
            raise RuntimeError(
                f"protagonist confidence {identification['confidence']} is below "
                f"{minimum_confidence} (best guess: {identification['protagonist_name']!r})"
            )
        name = identification["protagonist_name"]

    comments = select_comments(raw_comments, name)
    result = generate_profile(build_prompt(novel, name, comments))
    if save:
        save_profile(novel_id, name, result)
    return novel, name, result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Regenerate protagonist profiles for existing novels")
    parser.add_argument("--novel-ids", type=int, nargs="+", help="Only these novel ids")
    parser.add_argument("--all", action="store_true", help="Include novels that already have all ten scores")
    parser.add_argument("--limit", type=int, help="Stop after this many novels")
    parser.add_argument("--sleep", type=float, default=1.0, help="Seconds to wait between novels (default 1)")
    parser.add_argument("--no-fetch-comments", action="store_true", help="Use synopsis and tags only (faster)")
    parser.add_argument("--minimum-name-confidence", type=int, default=75)
    parser.add_argument("--dry-run", action="store_true", help="Generate and print, but do not save")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not 0 <= args.minimum_name_confidence <= 100:
        raise SystemExit("--minimum-name-confidence must be between 0 and 100")

    novel_ids = args.novel_ids or novels_to_profile(include_complete=args.all)
    if args.limit:
        novel_ids = novel_ids[: args.limit]

    mode = "DRY RUN (nothing is saved)" if args.dry_run else "saving to Supabase"
    print(f"{len(novel_ids)} novel(s) to profile; {mode}.")

    saved, failed = 0, []
    for position, novel_id in enumerate(novel_ids, start=1):
        print(f"\n[{position}/{len(novel_ids)}] novel {novel_id}")
        try:
            novel, name, result = regenerate(
                novel_id,
                args.minimum_name_confidence,
                fetch_comments=not args.no_fetch_comments,
                save=not args.dry_run,
            )
            scores = ", ".join(f"{measure}={result['scores'][measure]}" for measure in MEASURES)
            print(f"  {novel['title']} / {name} (confidence {result['confidence']})")
            print(f"  {scores}")
            saved += 1
        except Exception as error:
            print(f"  FAILED: {type(error).__name__}: {error}")
            failed.append((novel_id, str(error)))
        if position < len(novel_ids):
            time.sleep(args.sleep)

    print(f"\nDone. {'Generated' if args.dry_run else 'Saved'}: {saved}. Failed: {len(failed)}.")
    for novel_id, reason in failed:
        print(f"  novel {novel_id}: {reason}")


if __name__ == "__main__":
    main()