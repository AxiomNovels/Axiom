"""Generate protagonist, philosophy, and storytelling profiles for one novel."""

import argparse
import subprocess
import sys


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate all three AI profiles for one novel")
    parser.add_argument("novel_id", type=int)
    parser.add_argument("--protagonist", help="Override automatic protagonist detection")
    parser.add_argument("--comments", help="Use a UTF-8 comment file instead of reading links")
    parser.add_argument("--no-fetch-comments", action="store_true", help="Use only synopsis and tags")
    parser.add_argument("--minimum-name-confidence", type=int, default=75)
    parser.add_argument("--save", action="store_true", help="Offer to save generated profiles")
    parser.add_argument("--yes", action="store_true", help="Save without confirmation; requires --save")
    return parser.parse_args()


def module_command(module: str, args: argparse.Namespace) -> list[str]:
    command = [sys.executable, "-m", module, str(args.novel_id)]
    if args.comments:
        command.extend(["--comments", args.comments])
    if args.no_fetch_comments:
        command.append("--no-fetch-comments")
    if args.save:
        command.append("--save")
    if args.yes:
        command.append("--yes")
    return command


def main() -> None:
    args = parse_args()
    protagonist_command = module_command("profiler.profile_protagonist", args)
    protagonist_command.extend(["--minimum-name-confidence", str(args.minimum_name_confidence)])
    if args.protagonist:
        protagonist_command.extend(["--protagonist", args.protagonist])

    subprocess.run(protagonist_command, check=True)
    subprocess.run(module_command("profiler.profile_philosophy", args), check=True)
    subprocess.run(module_command("profiler.profile_storytelling", args), check=True)


if __name__ == "__main__":
    main()
