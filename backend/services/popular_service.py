"""Rank the public catalogue by Axiom review averages, then paginate it."""
import hashlib
from collections import defaultdict
from fractions import Fraction

from core.pagination import all_rows


PAGE_SIZE = 20


def popular_novels(client, *, page, seed, columns):
    # Fetch only ranking inputs for the full catalogue. Fetch the larger card
    # fields for the requested page below. Separate review pagination avoids
    # truncating heavily reviewed novels at PostgREST's embedded-row limit.
    novels = all_rows(client.table("novels").select("id").order("id"))
    ratings = defaultdict(list)
    if novels:
        reviews = all_rows(client.table("reviews").select("novel_id, rating").order("id"))
        for review in reviews:
            if review.get("rating") is not None:
                ratings[review["novel_id"]].append(Fraction(str(review["rating"])))

    averages = {
        novel["id"]: sum(ratings[novel["id"]], Fraction()) / len(ratings[novel["id"]])
        if ratings[novel["id"]] else Fraction()
        for novel in novels
    }
    # A random seed chosen per browsing session gives tied novels equal
    # opportunity, while preserving page boundaries for an unchanged catalogue.
    novels.sort(key=lambda novel: (
        -averages[novel["id"]],
        hashlib.sha256(f"{seed}:{novel['id']}".encode()).digest(),
        novel["id"],
    ))
    total = len(novels)
    total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    page = min(page, max(1, total_pages))
    start = (page - 1) * PAGE_SIZE
    ids = [novel["id"] for novel in novels[start:start + PAGE_SIZE]]
    rows = []
    if ids:
        rows = client.table("novels").select(columns).in_("id", ids).execute().data or []
    by_id = {row["id"]: row for row in rows}
    items = []
    for novel_id in ids:
        # A novel may have been removed since the initial catalogue query.
        if novel_id not in by_id:
            continue
        items.append({
            **by_id[novel_id],
            "average_rating": round(float(averages[novel_id]), 2) if ratings[novel_id] else None,
            "review_count": len(ratings[novel_id]),
        })
    return {
        "novels": items,
        "page": page,
        "page_size": PAGE_SIZE,
        "total": total,
        "total_pages": total_pages,
        "seed": seed,
    }
