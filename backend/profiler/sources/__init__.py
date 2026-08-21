"""Public reader-feedback collectors keyed by reading platform."""

from profiler.sources.webnovel import collect_webnovel_reviews
from profiler.sources.royalroad import collect_royalroad_reviews
from profiler.sources.wattpad import collect_wattpad_comments


def collect_public_comments(reading_links: list[dict]) -> tuple[list[str], list[str]]:
    """Collect public comments from supported reading links.

    Returns the comments and human-readable source labels. Unsupported links are
    ignored so one novel may contain several platforms without breaking profiling.
    """
    comments: list[str] = []
    sources: list[str] = []

    for link in reading_links or []:
        platform = str(link.get("platform") or "").strip().casefold()
        url = str(link.get("url") or "").strip()
        if not url:
            continue

        if platform == "webnovel" or "webnovel.com" in url.casefold():
            reviews = collect_webnovel_reviews(url)
            comments.extend(reviews)
            sources.append(f"WebNovel ({len(reviews)} public reviews)")
        elif platform == "royal road" or "royalroad.com" in url.casefold():
            reviews = collect_royalroad_reviews(url)
            comments.extend(reviews)
            sources.append(f"Royal Road ({len(reviews)} public reviews)")
        elif platform == "wattpad" or "wattpad.com" in url.casefold():
            try:
                wattpad_comments = collect_wattpad_comments(url)
            except RuntimeError as error:
                # Wattpad commonly renders inline comments only after the page
                # application loads them. Its downloaded public HTML can expose
                # story parts without exposing their comments. Keep profiling
                # usable, but make the missing evidence explicit.
                print(f"Warning: {error}. Continuing without Wattpad comments.")
                sources.append("Wattpad (comments unavailable; synopsis/tags only)")
            else:
                comments.extend(wattpad_comments)
                sources.append(f"Wattpad ({len(wattpad_comments)} public comments)")

    return comments, sources
