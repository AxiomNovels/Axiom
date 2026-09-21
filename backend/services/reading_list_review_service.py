"""Rating summaries for reading lists."""

PAGE_SIZE = 1000


def attach_rating_summaries(client, lists: list[dict]) -> list[dict]:
    """Add average_rating and review_count to each list dict, using one
    batched query. Must be given a service-role client: the reviews table
    has no user-facing RLS policies. Callers are responsible for only
    passing lists the viewer is already allowed to see.
    """
    for reading_list in lists:
        reading_list["average_rating"] = None
        reading_list["review_count"] = 0

    list_ids = [reading_list["id"] for reading_list in lists]
    if not list_ids:
        return lists

    ratings_by_list: dict[str, list[float]] = {}
    try:
        offset = 0
        while True:
            page = (
                client.table("reading_list_reviews")
                .select("reading_list_id, rating")
                .in_("reading_list_id", list_ids)
                .order("id")
                .range(offset, offset + PAGE_SIZE - 1)
                .execute()
                .data
                or []
            )
            for row in page:
                ratings_by_list.setdefault(row["reading_list_id"], []).append(float(row["rating"]))
            if len(page) < PAGE_SIZE:
                break
            offset += PAGE_SIZE
    except Exception as error:
        # Ratings are secondary to the lists themselves; don't fail the whole request.
        print(f"[reading_list_reviews] failed to load rating summaries: {error}")
        ratings_by_list = {}

    for reading_list in lists:
        ratings = ratings_by_list.get(reading_list["id"], [])
        if ratings:
            reading_list["review_count"] = len(ratings)
            reading_list["average_rating"] = round(sum(ratings) / len(ratings), 2)
    return lists