import re


def searchable_text(value):
    """Return lowercase words suitable for small-catalogue relevance scoring."""
    return re.findall(r"[a-z0-9]+", str(value or "").lower())


def novel_relevance(novel, query):
    """Score a novel, favoring title and author matches over metadata/body text."""
    query_text = " ".join(searchable_text(query))
    query_terms = query_text.split()
    if not query_terms:
        return 0

    title = " ".join(searchable_text(novel.get("title")))
    author = " ".join(searchable_text(novel.get("author")))
    # Genres (small, canonical) and tags (larger, free-form) are both
    # relevant to a keyword search -- e.g. "reincarnation" only lives in
    # tags, while "fantasy" only lives in genres.
    genres = " ".join(searchable_text(" ".join(novel.get("genres") or [])))
    tags = " ".join(searchable_text(" ".join(novel.get("tags") or [])))
    synopsis = " ".join(searchable_text(novel.get("synopsis")))

    score = 0
    if title == query_text:
        score += 250
    elif title.startswith(query_text):
        score += 140
    elif query_text in title:
        score += 100

    if author == query_text:
        score += 100
    elif query_text in author:
        score += 60

    title_terms = title.split()
    author_terms = author.split()
    genre_terms = genres.split()
    tag_terms = tags.split()
    synopsis_terms = synopsis.split()

    for term in query_terms:
        if term in title_terms:
            score += 45
        elif any(word.startswith(term) for word in title_terms):
            score += 30

        if term in author_terms:
            score += 22
        if term in genre_terms:
            score += 16
        if term in tag_terms:
            score += 16
        if term in synopsis_terms:
            score += 5

    all_terms = title_terms + author_terms + genre_terms + tag_terms + synopsis_terms
    matched_terms = sum(term in all_terms for term in query_terms)
    score += matched_terms * 8
    if matched_terms == len(query_terms):
        score += 25

    return score


def rank_novels(novels, query):
    """Return matching novels ordered by relevance and then title."""
    ranked = []
    for novel in novels:
        relevance = novel_relevance(novel, query)
        if relevance > 0:
            ranked.append((relevance, novel))

    ranked.sort(key=lambda item: (-item[0], item[1].get("title", "").lower()))
    return [novel for _, novel in ranked]


PROFILE_MEASURES = (
    "impulsivity",
    "arrogance_pride",
    "kinship_friendship",
    "romantic_attachment",
    "sexual_desire",
    "selflessness",
)

PHILOSOPHY_MEASURES = (
    "freedom", "survival", "existentialism", "moral_ambiguity",
    "self_improvement", "determinism", "revenge", "romance",
)

STORYTELLING_MEASURES = (
    "political_intrigue", "psychological_warfare", "kingdom_building",
    "action", "slice_of_life", "mystery", "worldbuilding",
)


def _profile_for(novel):
    profiles = novel.get("protagonist_profiles") or []
    if isinstance(profiles, dict):
        return profiles
    return profiles[0] if profiles else {}


def _embedded_profile(novel, table):
    profile = novel.get(table) or []
    if isinstance(profile, dict):
        return profile
    return profile[0] if profile else {}


def _matches_ranges(profile, ranges):
    for measure, bounds in (ranges or {}).items():
        value = profile.get(measure)
        if value is None:
            return False
        minimum, maximum = bounds
        if minimum is not None and value < minimum:
            return False
        if maximum is not None and value > maximum:
            return False
    return True


def review_summary(novel):
    reviews = novel.get("reviews") or []
    ratings = [float(review["rating"]) for review in reviews if review.get("rating") is not None]
    novel["review_count"] = len(ratings)
    novel["average_rating"] = round(sum(ratings) / len(ratings), 2) if ratings else None
    return novel


def filter_novels(novels, include_tags=None, exclude_tags=None, status=None, profile_ranges=None, tag_mode="and", philosophy_ranges=None, storytelling_ranges=None, min_rating=None):
    """Apply finder criteria to a catalogue already fetched from Supabase."""
    included = {tag.strip().lower() for tag in (include_tags or []) if tag.strip()}
    excluded = {tag.strip().lower() for tag in (exclude_tags or []) if tag.strip()}
    wanted_status = (status or "").strip().lower()
    ranges = profile_ranges or {}
    matches = []

    for novel in novels:
        review_summary(novel)
        tags = {str(tag).strip().lower() for tag in (novel.get("tags") or [])}
        if included and tag_mode == "or" and not included.intersection(tags):
            continue
        if included and tag_mode != "or" and not included.issubset(tags):
            continue
        if excluded.intersection(tags):
            continue
        if wanted_status and str(novel.get("status") or "").lower() != wanted_status:
            continue
        if min_rating is not None and (novel["average_rating"] is None or novel["average_rating"] < min_rating):
            continue

        if (
            _matches_ranges(_profile_for(novel), ranges)
            and _matches_ranges(_embedded_profile(novel, "philosophy_profiles"), philosophy_ranges)
            and _matches_ranges(_embedded_profile(novel, "storytelling_style_profiles"), storytelling_ranges)
        ):
            matches.append(novel)

    return matches


def sort_novels(novels, sort="relevance", query=""):
    if sort == "title_asc":
        return sorted(novels, key=lambda novel: (novel.get("title") or "").lower())
    if sort == "title_desc":
        return sorted(novels, key=lambda novel: (novel.get("title") or "").lower(), reverse=True)
    if query:
        return rank_novels(novels, query)
    return sorted(novels, key=lambda novel: (novel.get("title") or "").lower())
