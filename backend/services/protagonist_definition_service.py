"""Read one authoritative snapshot per operation; never cache mutable definitions."""
from fastapi import HTTPException
from postgrest.exceptions import APIError

from core.database import supabase


def load_definition(client=None):
    try:
        data = (client or supabase).rpc("get_protagonist_definition", {}).execute().data
        if not isinstance(data, dict) or not data.get("traits") or not data.get("revision"):
            raise ValueError("Missing protagonist definition")
        return data
    except Exception as error:
        raise HTTPException(503, "Protagonist definitions are unavailable. Apply database/manage_protagonist_profile.sql and retry.") from error


def measures_for(definition):
    return tuple(trait["key"] for trait in definition["traits"])


def definition_error(error):
    if isinstance(error, APIError):
        if error.code == "40001":
            return HTTPException(409, "Protagonist definitions changed. Reload and review your changes before saving.")
        if error.code == "22023":
            return HTTPException(422, error.message)
        if error.code == "P0001":
            return HTTPException(409, error.message)
    return HTTPException(503, "The profile change could not be confirmed. Reload before retrying and check that database/manage_protagonist_profile.sql is installed.")
