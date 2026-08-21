def resolve_protagonist_name(novel: dict, supplied_name: str | None) -> str | None:
    if supplied_name and supplied_name.strip():
        return supplied_name.strip()

    profile = novel.get("protagonist_profiles")
    if isinstance(profile, list):
        profile = profile[0] if profile else None
    if isinstance(profile, dict) and profile.get("protagonist_name"):
        return str(profile["protagonist_name"]).strip()

    return None
