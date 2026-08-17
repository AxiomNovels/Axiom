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
    genres = " ".join(searchable_text(" ".join(novel.get("genres") or [])))
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
        if term in synopsis_terms:
            score += 5

    all_terms = title_terms + author_terms + genre_terms + synopsis_terms
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
