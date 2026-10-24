"""Read complete ordered result sets despite PostgREST's per-request row cap."""


def all_rows(query, page_size=500):
    rows = []
    offset = 0
    while True:
        page = query.range(offset, offset + page_size - 1).execute().data or []
        rows.extend(page)
        if len(page) < page_size:
            return rows
        offset += len(page)
