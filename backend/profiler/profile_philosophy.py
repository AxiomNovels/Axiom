"""Generate and optionally save the philosophy profile for one novel."""

from profiler.profile_catalog import parse_profile_args, run_profile
from profiler.prompt import PHILOSOPHY_MEASURES


def main() -> None:
    try:
        run_profile(
            "philosophy", "philosophy_profiles", PHILOSOPHY_MEASURES,
            parse_profile_args("Generate one AI philosophy baseline"),
        )
    except RuntimeError as error:
        raise SystemExit(f"Error: {error}") from None


if __name__ == "__main__":
    main()
