import argparse
import inspect
import logging
import os
import sys
import time

from mint_sniper import collections
from utils import logger, file_util


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log-level", choices=["INFO", "DEBUG", "ERROR", "NONE"], default="INFO")
    log_dir = logger.get_logging_dir("mint_sniper")
    parser.add_argument("--log-dir", default=log_dir)
    parser.add_argument("--collection", choices=[c.value for c in collections.Collections])
    parser.add_argument("--force", action="store_true")

    return parser.parse_args()


def setup_log(log_level: str, log_dir: str, id_string: str, subdir: str) -> None:
    if log_level == "NONE":
        return

    log_name = (
        time.strftime("%Y_%m_%d__%H_%M_%S", time.localtime(time.time())) + f"_{id_string}.log"
    )

    log_dir = os.path.join(log_dir, subdir)

    file_util.make_sure_path_exists(log_dir)

    log_file = os.path.join(log_dir, log_name)

    logging.basicConfig(
        filename=log_file,
        level=logging.getLevelName(log_level),
        format="[%(levelname)s][%(asctime)s][%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        filemode="w",
    )


def get_mint_stats(collection: str, download_and_parse: bool) -> None:
    class_name = collections.Collections(args.collection).value
    class_obj = getattr(sys.modules[inspect.getmodule(collections).__name__], class_name)

    mint_collection = class_obj(download_and_parse)

    logger.print_bold(
        f"Collecting mint attribute data and rarity for {' '.join(mint_collection.collection_name.split('_'))}"
    )
    if not download_and_parse:
        try:
            rarity = mint_collection.get_full_collection_rarity(save_to_disk=True)
        except ValueError:
            download_and_parse = True

    if download_and_parse:
        logger.print_normal(f"Processing data from web source...")
        mint_collection.save_nft_collection_attributes()
        rarity = mint_collection.get_full_collection_rarity(save_to_disk=True)

    logger.print_ok_arrow(f"Done!")

    mint_collection.write_rarity_to_csv(rarity)


if __name__ == "__main__":
    args = parse_args()

    setup_log(
        args.log_level,
        args.log_dir,
        "mint_sniper",
        "sniper",
    )

    get_mint_stats(args.collection, args.force)
