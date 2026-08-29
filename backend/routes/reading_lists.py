from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from core.database import create_authenticated_client, supabase
from routes.novels import NOVEL_LIST_COLUMNS


router = APIRouter(prefix="/api/reading-lists", tags=["reading-lists"])


class ReadingListCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class ReadingListRename(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class ReadingListNovelAdd(BaseModel):
    novel_id: int


def get_current_user(authorization: Optional[str] = Header(None)):
    """Resolve the Supabase user id from a `Bearer <access_token>` header.

    The frontend stores the Supabase session (including its access token)
    in localStorage after login/signup and sends it on every reading-list
    request via `authFetch` in script.js.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Log in to manage reading lists.")

    access_token = authorization.split(" ", 1)[1].strip()

    try:
        user_response = supabase.auth.get_user(access_token)
    except Exception:
        raise HTTPException(status_code=401, detail="Your session has expired. Please log in again.")

    user = getattr(user_response, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Your session has expired. Please log in again.")

    return user.id, create_authenticated_client(access_token)


def _duplicate_name_error(error: Exception) -> bool:
    message = str(error)
    return "duplicate key value" in message or "23505" in message


def _get_owned_list(list_id: str, user_id: str, client) -> dict:
    try:
        response = (
            client.table("reading_lists")
            .select("id, name, created_at")
            .eq("id", list_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    rows = response.data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Reading list not found.")

    return rows[0]


@router.get("")
def list_reading_lists(auth=Depends(get_current_user)):
    user_id, client = auth
    try:
        lists_response = (
            client.table("reading_lists")
            .select("id, name, created_at")
            .eq("user_id", user_id)
            .order("created_at")
            .execute()
        )
        counts_response = (
            client.table("reading_list_novels")
            .select("reading_list_id, novel_id, added_at")
            .eq("user_id", user_id)
            .order("added_at", desc=True)
            .execute()
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    membership_rows = counts_response.data or []
    novel_ids = list(dict.fromkeys(row["novel_id"] for row in membership_rows))
    novel_by_id = {}
    if novel_ids:
        try:
            novels_response = (
                supabase.table("novels")
                .select("id, title, cover_image_url")
                .in_("id", novel_ids)
                .execute()
            )
            novel_by_id = {novel["id"]: novel for novel in (novels_response.data or [])}
        except Exception as error:
            raise HTTPException(status_code=500, detail=str(error))

    counts: dict = {}
    previews: dict = {}
    for row in membership_rows:
        list_id = row["reading_list_id"]
        counts[list_id] = counts.get(list_id, 0) + 1
        novel = novel_by_id.get(row["novel_id"])
        if novel and len(previews.setdefault(list_id, [])) < 3:
            previews[list_id].append(novel)

    lists = lists_response.data or []
    for reading_list in lists:
        reading_list["novel_count"] = counts.get(reading_list["id"], 0)
        reading_list["preview_novels"] = previews.get(reading_list["id"], [])

    return lists


@router.post("", status_code=201)
def create_reading_list(payload: ReadingListCreate, auth=Depends(get_current_user)):
    user_id, client = auth
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="List name cannot be empty.")

    try:
        response = (
            client.table("reading_lists")
            .insert({"user_id": user_id, "name": name})
            .execute()
        )
    except Exception as error:
        if _duplicate_name_error(error):
            raise HTTPException(status_code=409, detail="You already have a list with that name.")
        raise HTTPException(status_code=500, detail=str(error))

    return response.data[0]


@router.get("/novel/{novel_id}")
def get_novel_membership(novel_id: int, auth=Depends(get_current_user)):
    """Which of the current user's lists (if any) this novel is in."""
    user_id, client = auth
    try:
        response = (
            client.table("reading_list_novels")
            .select("reading_list_id, reading_lists(id, name)")
            .eq("novel_id", novel_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    rows = response.data or []
    if not rows:
        return None

    reading_list = rows[0].get("reading_lists") or {}
    return {"id": reading_list.get("id"), "name": reading_list.get("name")}


@router.get("/{list_id}")
def get_reading_list(list_id: str, auth=Depends(get_current_user)):
    user_id, client = auth
    reading_list = _get_owned_list(list_id, user_id, client)

    try:
        items_response = (
            client.table("reading_list_novels")
            .select(f"added_at, novels({NOVEL_LIST_COLUMNS})")
            .eq("reading_list_id", list_id)
            .eq("user_id", user_id)
            .order("added_at", desc=True)
            .execute()
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    novels = [item["novels"] for item in (items_response.data or []) if item.get("novels")]

    return {**reading_list, "novels": novels}


@router.patch("/{list_id}")
def rename_reading_list(
    list_id: str, payload: ReadingListRename, auth=Depends(get_current_user)
):
    user_id, client = auth
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="List name cannot be empty.")

    _get_owned_list(list_id, user_id, client)

    try:
        response = (
            client.table("reading_lists")
            .update({"name": name})
            .eq("id", list_id)
            .eq("user_id", user_id)
            .execute()
        )
    except Exception as error:
        if _duplicate_name_error(error):
            raise HTTPException(status_code=409, detail="You already have a list with that name.")
        raise HTTPException(status_code=500, detail=str(error))

    return response.data[0]


@router.delete("/{list_id}", status_code=204)
def delete_reading_list(list_id: str, auth=Depends(get_current_user)):
    user_id, client = auth
    _get_owned_list(list_id, user_id, client)

    try:
        client.table("reading_lists").delete().eq("id", list_id).eq("user_id", user_id).execute()
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    return None


@router.post("/{list_id}/novels", status_code=201)
def add_novel_to_list(
    list_id: str, payload: ReadingListNovelAdd, auth=Depends(get_current_user)
):
    """Add a novel to this list. If it's already in a different list of
    the user's, this moves it (the unique (user_id, novel_id) constraint
    means a novel only ever lives in one list at a time)."""
    user_id, client = auth
    _get_owned_list(list_id, user_id, client)

    try:
        response = (
            client.table("reading_list_novels")
            .upsert(
                {
                    "reading_list_id": list_id,
                    "novel_id": payload.novel_id,
                    "user_id": user_id,
                },
                on_conflict="user_id,novel_id",
            )
            .execute()
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    return response.data[0]


@router.delete("/{list_id}/novels/{novel_id}", status_code=204)
def remove_novel_from_list(list_id: str, novel_id: int, auth=Depends(get_current_user)):
    user_id, client = auth
    _get_owned_list(list_id, user_id, client)

    try:
        (
            client.table("reading_list_novels")
            .delete()
            .eq("reading_list_id", list_id)
            .eq("novel_id", novel_id)
            .eq("user_id", user_id)
            .execute()
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    return None
