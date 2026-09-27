from fastapi import APIRouter, HTTPException

from core.database import create_service_client


router = APIRouter(prefix="/api", tags=["home"])


@router.get("/home-feature")
def get_home_feature():
    """Return the currently published manual Home-page feature, if any."""
    try:
        client = create_service_client()
        result = client.table("home_feature").select("novel_id,inquiry,description,tags,updated_at").eq("id", True).maybe_single().execute()
        feature = result.data
        if not feature:
            return None
        novel = client.table("novels").select("id,title,author,cover_image_url").eq("id", feature["novel_id"]).maybe_single().execute().data
        if not novel:
            return None
        return {**feature, "novel": novel}
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))
