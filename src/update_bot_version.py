"""
Update bot version using discord bot
"""
import argparse
import logging

from utils import discord, logger

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--new-version", help="new version number")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.dry_run:
        logger.print_warn(f"DRY RUN ACTIVATED")

    logger.print_ok(f"Updating bot version to {args.new_version}")

    if args.dry_run:
        return

    text = f"\U0001F980   \U0001F916 **Bot upgraded! Version {args.new_version}**"
    discord.get_discord_hook().send(text)



if __name__ == "__main__":
    main()
