"""Like counts and this-viewer's like state for reading lists."""

PAGE_SIZE = 1000


def attach_like_summaries(client, lists: list[dict], viewer_id: str | None) -> list[dict]:
    """Add like_count and viewer_has_liked to each list dict, using one
    batched query. Must be given a service-role client: reading_list_likes
    has no user-facing RLS policies. Callers are responsible for only
    passing lists the viewer is already allowed to see.
    """
    for reading_list in lists:
        reading_list["like_count"] = 0
        reading_list["viewer_has_liked"] = False

    list_ids = [reading_list["id"] for reading_list in lists]
    if not list_ids:
        return lists

    counts: dict[str, int] = {}
    liked_by_viewer: set[str] = set()
    try:
        offset = 0
        while True:
            page = (
                client.table("reading_list_likes")
                .select("reading_list_id, user_id")
                .in_("reading_list_id", list_ids)
                .order("id")
                .range(offset, offset + PAGE_SIZE - 1)
                .execute()
                .data
                or []
            )
            for row in page:
                list_id = row["reading_list_id"]
                counts[list_id] = counts.get(list_id, 0) + 1
                if viewer_id and row["user_id"] == viewer_id:
                    liked_by_viewer.add(list_id)
            if len(page) < PAGE_SIZE:
                break
            offset += PAGE_SIZE
    except Exception as error:
        # Likes are secondary to the lists themselves; don't fail the whole
        # request if this lookup has trouble.
        print(f"[reading_list_likes] failed to load like summaries: {error}")
        counts = {}
        liked_by_viewer = set()

    for reading_list in lists:
        reading_list["like_count"] = counts.get(reading_list["id"], 0)
        reading_list["viewer_has_liked"] = reading_list["id"] in liked_by_viewer
    return lists