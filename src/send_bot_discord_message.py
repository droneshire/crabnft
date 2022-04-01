"""
Collect TUS commission from specified bot users
"""
import argparse
import typing as T

from utils import discord, logger

NEW_USER_ADDED_MESSAGE = f"""\U0001F389 New Crabadian Added!"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--channel",
        choices=discord.DISCORD_WEBHOOK_URL.keys(),
        help="discord channels to send message",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--message", help="message")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.dry_run:
        logger.print_warn(f"DRY RUN ACTIVATED")

    logger.print_bold(f"Sending message to {args.channel}...")

    if not args.message:
        return

    message = args.message
    message += f"\nsnib snib \U0001F980\n"

    if not args.dry_run:
        discord.get_discord_hook(args.channel).send(message)

    logger.print_normal(message)


if __name__ == "__main__":
    main()
