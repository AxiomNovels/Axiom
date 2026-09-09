"""Generate and optionally save the storytelling profile for one novel."""

from profiler.profile_catalog import parse_profile_args, run_profile
from profiler.prompt import STORYTELLING_MEASURES


def main() -> None:
    run_profile(
        "storytelling",
        "storytelling_style_profiles",
        STORYTELLING_MEASURES,
        parse_profile_args("Generate one AI storytelling baseline"),
    )


if __name__ == "__main__":
    main()
