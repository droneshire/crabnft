import copy
import json
import os
import typing as T

from utils import logger
from utils.file_util import make_sure_path_exists
from utils.price import Prices, wei_to_token
from utils.user import get_alias_from_user


class LifetimeGameStatsLogger:
    def __init__(
        self,
        user: str,
        null_game_stats: T.Dict[T.Any, T.Any],
        log_dir: str,
        backup_stats: T.Dict[T.Any, T.Any],
        dry_run: bool = False,
        verbose: bool = False,
    ):
        self.user = user
        self.alias = get_alias_from_user(user)
        self.null_game_stats = null_game_stats
        self.log_dir = log_dir

        self.dry_run = dry_run
        self.verbose = verbose

        self.lifetime_stats: T.Dict[T.Any, T.Any] = None

        if not os.path.isfile(self.get_lifetime_stats_file()):
            if backup_stats:
                logger.print_normal(f"Using backup stats...")
                self.lifetime_stats = copy.deepcopy(backup_stats)
            else:
                logger.print_normal(f"Using null stats...")
                self.lifetime_stats = copy.deepcopy(self.null_game_stats)
        else:
            game_stats = self.get_game_stats()
            if game_stats:
                logger.print_normal(f"Using previous game stats...")
                self.lifetime_stats = game_stats
            elif backup_stats:
                logger.print_normal(
                    f"Using backup stats even though stats present..."
                )
                self.lifetime_stats = backup_stats
            else:
                logger.print_normal(
                    f"Using null stats even though stats present..."
                )
                self.lifetime_stats = copy.deepcopy(self.null_game_stats)

        self.write_game_stats(self.lifetime_stats, dry_run=dry_run)

        self.last_lifetime_stats: T.Dict[T.Any, T.Any] = copy.deepcopy(
            self.lifetime_stats
        )

    def write_game_stats(
        self, game_stats: T.Dict[T.Any, T.Any], dry_run=False
    ) -> None:
        if dry_run or not os.path.isdir(self.log_dir):
            return

        game_stats_file = self.get_lifetime_stats_file()
        make_sure_path_exists(game_stats_file)
        with open(game_stats_file, "w") as outfile:
            json.dump(
                game_stats,
                outfile,
                indent=4,
                sort_keys=True,
            )

    def get_lifetime_stats_file(self) -> str:
        return logger.get_lifetime_game_stats(self.log_dir, self.alias.lower())

    def get_game_stats(self) -> T.Dict[T.Any, T.Any]:
        game_stats_file = self.get_lifetime_stats_file()
        if not os.path.isfile(game_stats_file):
            return copy.deepcopy(self.null_game_stats)
        try:
            with open(game_stats_file, "r") as infile:
                return json.load(infile)
        except:
            logger.print_fail(
                f"Failed to read game stats from {game_stats_file}"
            )
            return {}

    def write(self) -> None:
        delta_stats = self.delta_game_stats(
            self.lifetime_stats,
            self.last_lifetime_stats,
        )
        file_stats = self.read()
        combined_stats = self.merge_game_stats(
            delta_stats,
            file_stats,
            self.log_dir,
        )

        if self.verbose:
            logger.print_bold(
                f"Writing stats for {self.user} [alias: {self.alias}]"
            )

        self.write_game_stats(combined_stats, dry_run=self.dry_run)
        self.last_lifetime_stats = copy.deepcopy(self.lifetime_stats)

    def read(self) -> T.Dict[T.Any, T.Any]:
        if self.verbose:
            logger.print_bold(
                f"Reading stats for {self.user} [alias: {self.alias}]"
            )

        return self.get_game_stats()

    def merge_game_stats(
        self,
        user_a_stats: T.Dict[T.Any, T.Any],
        user_b_stats: T.Dict[T.Any, T.Any],
        log_dir: str,
    ) -> T.Dict[T.Any, T.Any]:
        raise NotImplementedError

    def delta_game_stats(
        self,
        user_a_stats: T.Dict[T.Any, T.Any],
        user_b_stats: T.Dict[T.Any, T.Any],
    ) -> T.Dict[T.Any, T.Any]:
        raise NotImplementedError
