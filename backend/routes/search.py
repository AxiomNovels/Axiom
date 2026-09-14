from fastapi import APIRouter, HTTPException, Query, Request

from routes.novels import NOVEL_LIST_COLUMNS
from core.database import supabase
from services.search_service import PHILOSOPHY_MEASURES, PROFILE_MEASURES, STORYTELLING_MEASURES, filter_novels, sort_novels


router = APIRouter(prefix="/api/search", tags=["search"])


SEARCH_COLUMNS = f"{NOVEL_LIST_COLUMNS}, protagonist_profiles(*), philosophy_profiles(*), storytelling_style_profiles(*), reviews(rating)"


def _split_tags(value):
    return [tag for tag in (value or "").split(",") if tag.strip()]


def _threshold(value, field_name):
    if value is None or str(value).strip() == "":
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail=f"{field_name} must be a whole number from 0 to 100")
    if not 0 <= number <= 100:
        raise HTTPException(status_code=422, detail=f"{field_name} must be between 0 and 100")
    return number


def _rating_threshold(value):
    if value is None or str(value).strip() == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="Minimum rating must be from 0.5 to 5")
    if not 0.5 <= number <= 5:
        raise HTTPException(status_code=422, detail="Minimum rating must be between 0.5 and 5")
    return number


def _fetch_catalogue():
    return supabase.table("novels").select(SEARCH_COLUMNS).execute().data or []


@router.get("/options")
def search_options():
    try:
        # Finder options only need basic novel metadata. Keeping this query
        # independent from profile-table embeds lets a fresh clone load tags
        # even while optional profile migrations are still being applied.
        novels = (
            supabase.table("novels")
            .select("tags, status")
            .execute()
            .data
            or []
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))
    return {
        "tags": sorted({tag for novel in novels for tag in (novel.get("tags") or [])}, key=str.lower),
        "statuses": sorted({novel.get("status") for novel in novels if novel.get("status")}, key=str.lower),
        "profile_measures": list(PROFILE_MEASURES),
    }


@router.get("")
def search_novels(
    request: Request,
    q: str = "",
    include_tags: str = "",
    exclude_tags: str = "",
    tag_mode: str = "and",
    status: str = "",
    sort: str = "relevance",
    min_rating: str | None = Query(None),
    impulsivity_min: str | None = Query(None),
    impulsivity_max: str | None = Query(None),
    arrogance_pride_min: str | None = Query(None),
    arrogance_pride_max: str | None = Query(None),
    kinship_friendship_min: str | None = Query(None),
    kinship_friendship_max: str | None = Query(None),
    romantic_attachment_min: str | None = Query(None),
    romantic_attachment_max: str | None = Query(None),
    sexual_desire_min: str | None = Query(None),
    sexual_desire_max: str | None = Query(None),
    selflessness_min: str | None = Query(None),
    selflessness_max: str | None = Query(None),
):
    query = q.strip()
    raw_ranges = locals()
    thresholds = {
        f"{measure}_{bound}": _threshold(raw_ranges[f"{measure}_{bound}"], f"{measure}_{bound}")
        for measure in PROFILE_MEASURES
        for bound in ("min", "max")
    }
    ranges = {
        measure: (thresholds[f"{measure}_min"], thresholds[f"{measure}_max"])
        for measure in PROFILE_MEASURES
        if thresholds[f"{measure}_min"] is not None or thresholds[f"{measure}_max"] is not None
    }
    def query_ranges(measures):
        return {
            measure: (
                _threshold(request.query_params.get(f"{measure}_min"), f"{measure}_min"),
                _threshold(request.query_params.get(f"{measure}_max"), f"{measure}_max"),
            )
            for measure in measures
            if request.query_params.get(f"{measure}_min", "").strip()
            or request.query_params.get(f"{measure}_max", "").strip()
        }

    philosophy_ranges = query_ranges(PHILOSOPHY_MEASURES)
    storytelling_ranges = query_ranges(STORYTELLING_MEASURES)
    try:
        novels = _fetch_catalogue()
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    if query:
        # Rank first also removes catalogue entries that do not match the keywords.
        novels = sort_novels(novels, query=query)
    novels = filter_novels(
        novels,
        include_tags=_split_tags(include_tags),
        exclude_tags=_split_tags(exclude_tags),
        tag_mode=tag_mode,
        status=status,
        profile_ranges=ranges,
        philosophy_ranges=philosophy_ranges,
        storytelling_ranges=storytelling_ranges,
        min_rating=_rating_threshold(min_rating),
    )
    return sort_novels(novels, sort=sort, query=query if sort == "relevance" else "")
