import argparse
import inspect
import logging
import os
import sys
import time

from mint_sniper import collection_select
from utils import logger, file_util


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--log-level",
        choices=["INFO", "DEBUG", "ERROR", "NONE"],
        default="INFO",
    )
    log_dir = logger.get_logging_dir("mint_sniper")
    parser.add_argument("--log-dir", default=log_dir)
    parser.add_argument("--collection", choices=[c.value for c in collection_select.Collections])
    parser.add_argument("--force", action="store_true")

    return parser.parse_args()


def get_mint_stats(collection: str, download_and_parse: bool) -> None:
    class_name = collection_select.Collections(args.collection).value
    class_obj = getattr(sys.modules[inspect.getmodule(collection_select).__name__], class_name)

    mint_collection = class_obj(download_and_parse)

    logger.print_bold(
        f"Collecting mint attribute data and rarity for {' '.join(mint_collection.collection_name.split('_'))}"
    )
    if not download_and_parse:
        try:
            rarity = mint_collection.get_full_collection_rarity(save_to_disk=True)
        except ValueError:
            download_and_parse = True

    mint_collection.save_nft_collection_attributes(download_and_parse)
    rarity = mint_collection.get_full_collection_rarity(save_to_disk=True)

    logger.print_ok_arrow(f"Done!")

    mint_collection.write_rarity_to_csv(rarity)


if __name__ == "__main__":
    args = parse_args()

    logger.setup_log(
        args.log_level,
        args.log_dir,
        "sniper",
    )

    get_mint_stats(args.collection, args.force)
