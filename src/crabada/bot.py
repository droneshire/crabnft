import json
import logging
import os
import time
import typing as T
from twilio.rest import Client

from crabada.web2_client import CrabadaWeb2Client
from crabada.web3_client import CrabadaWeb3Client
from crabada.factional_advantage import get_faction_adjusted_battle_point
from crabada.types import CrabForLending, GameStats, IdleGame, NULL_GAME_STATS, Team
from utils import logger
from utils.config_types import UserConfig, SmsConfig
from utils.price import tus_to_wei, wei_to_tus, wei_to_cra_raw, wei_to_tus_raw


class CrabadaBot:
    AVAX_NODE_URL = "https://api.avax.network/ext/bc/C/rpc"
    TIME_BETWEEN_TRANSACTIONS = 5.0
    TIME_BETWEEN_EACH_UPDATE = 30.0
    SMS_COST_PER_MESSAGE = 0.0075

    def __init__(
        self,
        user: str,
        config: UserConfig,
        from_sms_number: str,
        admin_sms_number: str,
        enable_admin_sms_alert: bool,
        sms_client: Client,
        log_dir: str,
        dry_run: bool,
    ) -> None:
        self.user = user
        self.config = config
        self.from_sms_number = from_sms_number
        self.admin_sms_number = admin_sms_number
        self.enable_admin_sms_alert = enable_admin_sms_alert
        self.sms = sms_client

        self.crabada_w3 = T.cast(
            CrabadaWeb3Client,
            (
                CrabadaWeb3Client()
                .set_credentials(config["address"], config["private_key"])
                .set_node_uri(self.AVAX_NODE_URL)
            ).set_dry_run(dry_run),
        )
        self.crabada_w2 = CrabadaWeb2Client()

        self.address = self.config["address"]
        self.game_stats = NULL_GAME_STATS
        self.game_stats_file = os.path.join(log_dir, user.lower() + "_lifetime_game_bot_stats.json")
        self.updated_game_stats = True

        if not os.path.isfile(self.game_stats_file):
            with open(self.game_stats_file, "w") as outfile:
                json.dump(
                    NULL_GAME_STATS, outfile, indent=4, sort_keys=True,
                )
        else:
            with open(self.game_stats_file, "r") as infile:
                self.game_stats = json.load(infile)
        logger.print_ok_blue(f"Adding bot for user {self.user} with address {self.address}")

    def _send_status_update_sms(self, custom_message: str) -> None:
        if not self.config["get_sms_updates"]:
            return

        text_message = f"\U0001F980 Crabada Bot Alert \U0001F980\n\n"
        text_message += f"Action: {custom_message}\n\n"

        text_message += f"Explorer: https://snowtrace.io/address/{self.config['address']}\n\n"
        text_message += "---\U0001F579  GAME STATS\U0001F579  ---\n"
        for k, v in self.game_stats.items():
            if isinstance(v, float):
                text_message += f"{k.upper()}: {v:2f}\n"
            else:
                text_message += f"{k.upper()}: {v}\n"

        text_message += "\n"

        try:
            message = self.sms.messages.create(
                body=text_message, from_=self.from_sms_number, to=self.config["sms_number"]
            )
        except:
            pass

        self.game_stats["sms_cost"] += self.SMS_COST_PER_MESSAGE
        self.game_stats["sms_sent"] += 1

        game_logger = logging.getLogger()
        if game_logger:
            game_logger.debug(json.dumps(message.sid, indent=4, sort_keys=True))

    def _print_mine_status(self) -> None:
        open_mines = self.crabada_w2.list_my_open_mines((self.address))
        team_to_mines = {mine["game_id"]: mine for mine in open_mines}

        open_mines_str = " ".join([str(m["game_id"]) for m in open_mines])
        formatted_date = time.strftime("%A, %Y-%m-%d %H:%M:%S", time.localtime(time.time()))
        logger.print_warn(f"Mines ({formatted_date})")
        for mine in open_mines:
            logger.print_normal(
                f"\t{mine['game_id']}\t\tround {mine['round']}\t\t{self.crabada_w2.get_remaining_time_formatted(mine)}\t\t"
            )
        logger.print_normal("\n")

    def _check_and_maybe_start_mines(self) -> None:
        available_teams = self.crabada_w2.list_available_teams(self.address)
        for team in available_teams:

            teams_specified_to_mine = [m["team_id"] for m in self.config["mining_teams"]]
            if team["team_id"] not in teams_specified_to_mine:
                logger.print_warn(f"Skipping team {team['team_id']} for mining...")
                continue

            logger.print_normal(f"Attemting to start new mine with team {team['team_id']}!")
            tx_hash = self.crabada_w3.start_game(team["team_id"])
            tx_receipt = self.crabada_w3.get_transaction_receipt(tx_hash)
            if tx_receipt["status"] != 1:
                logger.print_fail(f"Error starting mine for team {team['team_id']}")
            else:
                logger.print_ok_arrow(f"Successfully started mine for team {team['team_id']}")
            time.sleep(self.TIME_BETWEEN_TRANSACTIONS)

    def _check_and_maybe_reinforce_mines(self) -> None:
        teams = self.crabada_w2.list_teams(self.address)
        for team in teams:
            team_mine = self.crabada_w2.get_mine(team["game_id"])

            if team_mine is None:
                continue

            if not self.crabada_w2.mine_needs_reinforcement(team_mine):
                logger.print_normal(
                    f"Mine[{team_mine.get('game_id', 'null')}]: No need for reinforcement"
                )
                continue

            reinforcment_crab = None
            if (
                team_mine["attack_point"] - get_faction_adjusted_battle_point(team, team_mine)
                < self.config["max_reinforce_bp_delta"]
            ):
                logger.print_normal(
                    f"Mine[{team_mine['game_id']}]: using reinforcement strategy of highest bp"
                )
                reinforcment_crab = self.crabada_w2.get_best_high_bp_crab_for_lending(
                    self.config["max_reinforcement_price_tus"]
                )
            else:
                logger.print_normal(
                    f"Mine[{team_mine['game_id']}]: using reinforcement strategy of highest mp"
                )
                reinforcment_crab = self.crabada_w2.get_best_high_mp_crab_for_lending(
                    self.config["max_reinforcement_price_tus"]
                )

            if reinforcment_crab is None:
                logger.print_fail("Could not find affordable reinforcement!")
                return

            price_tus = wei_to_tus_raw(reinforcment_crab["price"])
            battle_points = reinforcment_crab["battle_point"]
            mine_points = reinforcment_crab["mine_point"]
            crabada_id = reinforcment_crab["crabada_id"]

            logger.print_normal(
                f"Mine[{team_mine['game_id']}]: Found reinforcement crabada {crabada_id} for {price_tus} Tus [BP {battle_points} | MP {mine_points}]"
            )

            tx_hash = self.crabada_w3.reinforce_defense(
                team["game_id"], crabada_id, reinforcment_crab["price"]
            )
            tx_receipt = self.crabada_w3.get_transaction_receipt(tx_hash)
            if tx_receipt["status"] != 1:
                logger.print_fail_arrow(f"Error reinforcing mine {team['game_id']}")
            else:
                logger.print_ok_arrow(f"Successfully reinforced mine {team['game_id']}")
                self.game_stats["tus_net"] -= price_tus
                self.game_stats["tus_reinforcement"] += price_tus
                self.updated_game_stats = True
            time.sleep(self.TIME_BETWEEN_TRANSACTIONS)

    def _check_and_maybe_close_mines(self) -> None:
        teams = self.crabada_w2.list_teams(self.address)
        for team in teams:
            if team["game_id"] is None and team["game_type"] != "mining":
                continue

            team_mine = self.crabada_w2.get_mine(team["game_id"])
            if not self.crabada_w2.mine_is_finished(team_mine):
                continue

            logger.print_normal(f"Attempting to close game {team['game_id']}")
            tx_hash = self.crabada_w3.close_game(team["game_id"])
            tx_receipt = self.crabada_w3.get_transaction_receipt(tx_hash)
            if tx_receipt["status"] != 1:
                logger.print_fail_arrow(f"Error closing mine {team['game_id']}")
            else:
                logger.print_ok_arrow(f"Successfully closed mine {team['game_id']}")
                self._update_bot_stats(team, team_mine)
                outcome = (
                    "won \U0001F389"
                    if team_mine["winner_team_id"] == team["team_id"]
                    else "lost \U0001F915"
                )
                self._send_status_update_sms(
                    f"finished mine for team {team['team_id']}, you {outcome}"
                )
            time.sleep(self.TIME_BETWEEN_TRANSACTIONS)

    def _update_bot_stats(self, team: Team, mine: IdleGame) -> None:
        if mine["winner_team_id"] == team["team_id"]:
            self.game_stats["game_wins"] += 1
        else:
            self.game_stats["game_losses"] += 1

        self.game_stats["game_win_percent"] = (
            100.0
            * float(self.game_stats["game_wins"])
            / (self.game_stats["game_wins"] + self.game_stats["game_losses"])
        )

        self.game_stats["tus_gross"] += wei_to_tus_raw(mine["miner_tus_reward"])
        self.game_stats["cra_net"] += wei_to_cra_raw(mine["miner_cra_reward"])
        self.game_stats["tus_net"] += wei_to_tus_raw(mine["miner_tus_reward"])

        self.game_stats["commission_tus"] += (
            wei_to_tus_raw(mine["miner_tus_reward"]) * self.config["commission_percent_per_mine"]
        )
        self.game_stats["tus_net"] -= self.game_stats["commission_tus"]

        with open(self.game_stats_file, "w") as outfile:
            json.dump(self.game_stats, outfile, indent=4, sort_keys=True)
        self.updated_game_stats = True

    def _print_bot_stats(self) -> None:
        logger.print_normal("\n")
        logger.print_bold("--------\U0001F579  GAME STATS\U0001F579  ------")
        logger.print_normal(f"Explorer: https://snowtrace.io/address/{self.config['address']}\n\n")
        for k, v in self.game_stats.items():
            logger.print_ok_blue(f"{k.upper()}: {v}")
        logger.print_bold("------------------------------\n")

    def run(self) -> None:
        logger.print_normal("=" * 60)
        logger.print_ok(f"User: {self.user.upper()}")
        self._print_mine_status()
        self._check_and_maybe_start_mines()
        self._check_and_maybe_reinforce_mines()
        self._check_and_maybe_close_mines()
        if self.updated_game_stats:
            self.updated_game_stats = False
            self._print_bot_stats()
        time.sleep(self.TIME_BETWEEN_EACH_UPDATE)

    def end(self) -> None:
        logger.print_fail(f"Exiting bot for {self.user}...")

        if self.enable_admin_sms_alert:
            sms_message = f"\U0001F980 Crabada Bot Alert \U0001F980\n\n"
            sms_message += f"Crabada Bot Stopped \U0000203C\n"
            message = self.sms.messages.create(
                body=sms_message, from_=self.from_sms_number, to=self.admin_sms_number,
            )
            game_logger = logging.getLogger()
            if game_logger:
                game_logger.debug(json.dumps(message.sid, indent=4, sort_keys=True))

        self._print_bot_stats()
        with open(self.game_stats_file, "w") as outfile:
            json.dump(self.game_stats, outfile, indent=4, sort_keys=True)
