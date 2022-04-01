"""
Update bot version using discord bot
"""
import argparse

from utils import discord, logger


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--new-version", help="new version number")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--change-list", help="Changelist")
    parser.add_argument(
        "--channel",
        choices=discord.DISCORD_WEBHOOK_URL.keys(),
        help="discord channels to send message",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.dry_run:
        logger.print_warn(f"DRY RUN ACTIVATED")

    text = f"\U0001F980   \U0001F916 **Bot upgraded! Version {args.new_version}**\n"

    if args.change_list:
        for line in args.change_list.splitlines():
            if line.startswith("-"):
                line = f"\U000027A1  {line[1:]} \n"
            text += line

    logger.print_normal(text)

    if not args.dry_run:
        discord.get_discord_hook(args.channel).send(text)


if __name__ == "__main__":
    main()
