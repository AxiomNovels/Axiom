"""Generate and optionally save the protagonist profile for one novel."""

from profiler.profile_novel import main as run


def main() -> None:
    try:
        run()
    except RuntimeError as error:
        raise SystemExit(f"Error: {error}") from None


if __name__ == "__main__":
    main()
