import copy
import datetime
import deepdiff
import getpass
import json
import os
import time
import typing as T
from discord import Color
from discord_webhook import DiscordEmbed, DiscordWebhook
from eth_typing import Address
from web3 import Web3

from config_admin import ADMIN_ADDRESS
from config_pumpskin import COMMISSION_WALLET_ADDRESS
from utils import discord
from utils import logger
from utils.config_types import UserConfig
from utils.email import Email, send_email
from utils.general import get_pretty_seconds
from utils.price import token_to_wei, wei_to_token_raw
from utils.user import get_alias_from_user
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client
from web3_utils.avax_web3_client import AvaxCWeb3Client
from web3_utils.potn_web3_client import PotnWeb3Client
from web3_utils.ppie_web3_client import PpieWeb3Client
from pumpskin.config_manager_pumpskin import PumpskinConfigManager
from pumpskin.game_stats import NULL_GAME_STATS, PumpskinLifetimeGameStatsLogger
from pumpskin.token_profit_lp import PumpskinTokenProfitManager
from pumpskin.types import Rarity, StakedPumpskin
from pumpskin.lp_token_web3_client import PotnLpWeb3Client, PpieLpWeb3Client
from pumpskin.pumpskin_web2_client import PumpskinWeb2Client
from pumpskin.pumpskin_web3_client import (
    PumpskinCollectionWeb3Client,
    PumpskinContractWeb3Client,
    PumpskinNftWeb3Client,
    PotnLpStakingContractWeb3Client,
    PpieLpStakingContractWeb3Client,
)

ATTRIBUTES_FILE = "attributes.json"
COLLECTION_FILE = "collection.json"
RARITY_FILE = "rarity.json"

PUMPSKIN_ATTRIBUTES = {
    "Background": {},
    "Frame": {},
    "Body": {},
    "Neck": {},
    "Eyes": {},
    "Head": {},
    "Facial": {},
    "Item": {},
}


class PumpskinBot:
    MAX_PUMPSKINS = 5555
    MAX_TOTAL_SUPPLY = 6666
    LOW_GAS_INTERVAL = 60.0 * 60.0 * 24

    def __init__(
        self,
        user: str,
        config: UserConfig,
        email_accounts: T.List[Email],
        encrypt_password: str,
        log_dir: str,
        dry_run: bool,
        update_config: bool,
    ):
        self.user: str = user
        self.alias: str = get_alias_from_user(user)
        self.emails: T.List[Email] = email_accounts
        self.log_dir: str = log_dir
        self.dry_run: bool = dry_run
        self.address: Address = Web3.toChecksumAddress(config["address"])

        self.last_gas_notification = 0
        self.ppie_available_to_stake = 0.0
        self.potn_available_to_stake = 0.0

        self.current_stats = copy.deepcopy(NULL_GAME_STATS)
        self.txns: T.List[str] = []

        self.config_mgr = PumpskinConfigManager(
            user,
            config,
            email_accounts,
            encrypt_password,
            log_dir,
            dry_run=dry_run,
            verbose=True,
            update_from_src=update_config,
        )

        self.pumpskin_w2: PumpskinWeb2Client = PumpskinWeb2Client()

        self.collection_w3: PumpskinCollectionWeb3Client = (
            PumpskinCollectionWeb3Client()
            .set_credentials(config["address"], config["private_key"])
            .set_node_uri(PumpskinCollectionWeb3Client.NODE_URL)
            .set_contract()
            .set_dry_run(dry_run)
        )

        self.game_w3: PumpskinContractWeb3Client = (
            PumpskinContractWeb3Client()
            .set_credentials(config["address"], config["private_key"])
            .set_node_uri(PumpskinContractWeb3Client.NODE_URL)
            .set_contract()
            .set_dry_run(dry_run)
        )

        self.nft_w3: PumpskinNftWeb3Client = (
            PumpskinNftWeb3Client()
            .set_credentials(config["address"], config["private_key"])
            .set_node_uri(PumpskinNftWeb3Client.NODE_URL)
            .set_contract()
            .set_dry_run(dry_run)
        )

        self.potn_w3: PotnWeb3Client = T.cast(
            PotnWeb3Client,
            (
                PotnWeb3Client()
                .set_credentials(config["address"], config["private_key"])
                .set_node_uri(AvalancheCWeb3Client.NODE_URL)
                .set_contract()
                .set_dry_run(dry_run)
            ),
        )

        self.ppie_w3: PpieWeb3Client = T.cast(
            PpieWeb3Client,
            (
                PpieWeb3Client()
                .set_credentials(config["address"], config["private_key"])
                .set_node_uri(AvalancheCWeb3Client.NODE_URL)
                .set_contract()
                .set_dry_run(dry_run)
            ),
        )

        self.stats_logger: PumpskinLifetimeGameStatsLogger = PumpskinLifetimeGameStatsLogger(
            get_alias_from_user(self.user),
            self.log_dir,
            self.config_mgr.get_lifetime_stats(),
            self.dry_run,
            verbose=False,
        )

        self.token_manager = {}
        self.token_manager[
            "potn"
        ]: PumpskinTokenProfitManager = PumpskinTokenProfitManager.create_token_profit_lp_class(
            "POTN",
            config,
            PotnLpWeb3Client,
            PotnLpStakingContractWeb3Client,
            self.potn_w3,
            self.stats_logger,
        )
        self.token_manager[
            "ppie"
        ]: PumpskinTokenProfitManager = PumpskinTokenProfitManager.create_token_profit_lp_class(
            "PPIE",
            config,
            PpieLpWeb3Client,
            PpieLpStakingContractWeb3Client,
            self.ppie_w3,
            self.stats_logger,
        )

        # convert json to actual IDs
        copy_config = {}
        for k, v in self.config_mgr.config["game_specific_configs"]["special_pumps"].items():
            copy_config[int(k)] = v
        self.config_mgr.config["game_specific_configs"]["special_pumps"] = copy.deepcopy(
            copy_config
        )

    @staticmethod
    def get_json_path(file_name: str) -> str:
        this_dir = os.path.dirname(os.path.realpath(__file__))
        file_path = os.path.join(this_dir, file_name)
        return file_path

    @staticmethod
    def calc_potn_from_level(level: int) -> int:
        return 50 * level**2

    @staticmethod
    def calc_cooldown_from_level(level: int) -> int:
        return level + 1

    @staticmethod
    def calc_ppie_per_day_from_level(level: int) -> int:
        return level + 3

    @staticmethod
    def calc_ppie_earned_per_day(pumpskins: T.Dict[int, T.Dict[int, T.Any]]) -> int:
        return sum(
            [
                PumpskinBot.calc_ppie_per_day_from_level(p.get("kg", 0) / 100)
                for _, p in pumpskins.items()
            ]
        )

    @staticmethod
    def calc_roi_from_mint(
        ppie_price_usd: float, avax_usd: float, pumpskin_price_avax: float
    ) -> float:
        ppie_accumulations = {1: {"days": 2.1, "ppie": 8, "potn": 12}}
        for level in range(2, 101):
            ppie_accumulations[level] = {}

            potn_per_day = 3 * PumpskinBot.calc_ppie_per_day_from_level(level)
            ppie_accumulations[level]["potn"] = ppie_accumulations[level - 1]["potn"] + potn_per_day

            cost_to_level = PumpskinBot.calc_potn_from_level(level)
            days_to_level = cost_to_level / ppie_accumulations[level]["potn"]
            ppie_while_waiting_to_level = days_to_level * PumpskinBot.calc_ppie_per_day_from_level(
                level
            )
            ppie_accumulations[level]["ppie"] = (
                ppie_accumulations[level - 1]["ppie"] + ppie_while_waiting_to_level
            )
            ppie_accumulations[level]["days"] = (
                ppie_accumulations[level - 1]["days"] + days_to_level
            )

        pumpskin_price_usd = pumpskin_price_avax * avax_usd
        ppie_per_pumpskin = pumpskin_price_usd / ppie_price_usd

        roi_days = ppie_accumulations[100]["days"]
        for level, stats in ppie_accumulations.items():
            if stats["ppie"] > ppie_per_pumpskin:
                roi_days = stats["days"]
                break
        return roi_days

    @staticmethod
    def get_mint_stats() -> T.Tuple[int, int]:
        w3: PumpskinNftWeb3Client = (
            PumpskinNftWeb3Client()
            .set_credentials(ADMIN_ADDRESS, "")
            .set_node_uri(AvalancheCWeb3Client.NODE_URL)
            .set_contract()
            .set_dry_run(False)
        )
        minted = w3.get_total_pumpskins_minted()
        supply = PumpskinBot.MAX_PUMPSKINS
        return (minted, supply)

    @staticmethod
    def update_nft_collection_attributes(
        attributes_file: str,
        pumpskin_collection: str,
    ) -> T.Dict[int, float]:
        pumpskin_w2: PumpskinWeb2Client = PumpskinWeb2Client()
        pumpskins_info = {}
        pumpskins_stats = copy.deepcopy(PUMPSKIN_ATTRIBUTES)

        for pumpskin in range(PumpskinBot.MAX_TOTAL_SUPPLY):
            pumpskins_info[pumpskin] = pumpskin_w2.get_pumpskin_info(pumpskin)
            logger.print_normal(f"Processing pumpskin {pumpskin}...")
            for attribute in pumpskins_info[pumpskin].get("attributes", []):
                if attribute["trait_type"] not in pumpskins_stats:
                    logger.print_fail(f"Unknown attribute: {attribute['trait_type']}")
                    continue
                trait_type = attribute["trait_type"]
                trait_value = attribute["value"]
                pumpskins_stats[trait_type][trait_value] = (
                    pumpskins_stats[trait_type].get(trait_value, 0) + 1
                )

        with open(attributes_file, "w") as outfile:
            json.dump(
                pumpskins_stats,
                outfile,
                indent=4,
                sort_keys=True,
            )
        with open(pumpskin_collection, "w") as outfile:
            json.dump(
                pumpskins_info,
                outfile,
                indent=4,
                sort_keys=True,
            )

    @staticmethod
    def calculate_rarity_for_collection(
        rarity_file: str = None,
        save_to_disk: bool = False,
    ) -> T.Dict[int, float]:
        pumpskins_rarity = {}

        attributes_file = PumpskinBot.get_json_path(ATTRIBUTES_FILE)
        with open(attributes_file, "r") as infile:
            pumpskin_stats = json.load(infile)

        collections_file = PumpskinBot.get_json_path(COLLECTION_FILE)
        with open(collections_file, "r") as infile:
            collection_traits = json.load(infile)

        for pumpskin in range(PumpskinBot.MAX_TOTAL_SUPPLY):
            pumpskins_rarity[pumpskin] = PumpskinBot.calculate_rarity(
                pumpskin, collection_traits[str(pumpskin)], pumpskin_stats
            )

        sorted_pumpskins_rarity = dict(
            sorted(
                pumpskins_rarity.items(),
                key=lambda y: y[1].get("Overall", {"rarity": 1000.0})["rarity"],
            )
        )

        if save_to_disk and rarity_file is not None:
            with open(rarity_file, "w") as outfile:
                json.dump(
                    sorted_pumpskins_rarity,
                    outfile,
                    indent=4,
                )

        return sorted_pumpskins_rarity

    @staticmethod
    def calculate_rarity_from_query(token_id: int, attributes_file: str) -> Rarity:
        pumpskin_w2: PumpskinWeb2Client = PumpskinWeb2Client()
        pumpskin_info = pumpskin_w2.get_pumpskin_info(token_id)

        with open(attributes_file, "r") as infile:
            pumpskin_stats = json.load(infile)

        return PumpskinBot.calculate_rarity(token_id, pumpskin_info, pumpskin_stats)

    @staticmethod
    def calculate_rarity(
        token_id: int,
        pumpskin_info: T.Dict[str, T.List[T.Dict[str, str]]],
        pumpskin_stats: T.Dict[str, T.Any],
    ) -> Rarity:
        pumpskin_rarity = {k: 0.0 for k in pumpskin_stats.keys()}
        pumpskin_traits = {k: 0.0 for k in pumpskin_stats.keys()}

        if "attributes" not in pumpskin_info:
            return {}

        for attribute in pumpskin_info["attributes"]:
            pumpskin_traits[attribute["trait_type"]] = attribute["value"]

        total_trait_count = 0
        for trait, values in pumpskin_stats.items():
            total_count = 0
            pumpkin_trait_count = 0
            for value, count in values.items():
                total_count += count
                if value == pumpskin_traits[trait]:
                    pumpkin_trait_count = count
                    total_trait_count += count

            rarity = float(pumpkin_trait_count) / total_count
            pumpskin_rarity[trait] = {"trait": pumpskin_traits[trait], "rarity": rarity}

        pumpskin_rarity["Overall"] = {
            "trait": None,
            "rarity": float(total_trait_count) / (total_count * len(pumpskin_stats.keys())),
        }

        return pumpskin_rarity

    def get_pumpskin_ids(self) -> T.List[int]:
        pumpskin_ids: T.List[int] = self.collection_w3.get_staked_pumpskins(self.address)

        logger.print_ok_blue(f"Found {len(pumpskin_ids)} Pumpskins for user {self.user}!")

        return pumpskin_ids

    def _process_w3_results(self, action_str: str, tx_hash: str) -> bool:
        logger.print_bold(f"{action_str}")

        tx_receipt = self.potn_lp_w3.get_transaction_receipt(tx_hash)
        gas = wei_to_token_raw(self.potn_w3.get_gas_cost_of_transaction_wei(tx_receipt))
        logger.print_bold(f"Paid {gas} AVAX in gas")

        self.stats_logger.lifetime_stats["avax_gas"] += gas

        if tx_receipt.get("status", 0) != 1:
            logger.print_fail(f"Failed to: {action_str}!")
            return False
        else:
            logger.print_ok(f"Successfully: {action_str}")
            self.txns.append(f"https://snowtrace.io/tx/{tx_hash}")
            logger.print_normal(f"Explorer: https://snowtrace.io/tx/{tx_hash}\n\n")
            return True

    def _send_leveling_discord_activity_update(self, token_id: int, level: int) -> None:
        webhook = DiscordWebhook(
            url=discord.DISCORD_WEBHOOK_URL["PUMPSKIN_ACTIVITY"], rate_limit_retry=True
        )
        discord_username = self.config_mgr.config["discord_handle"].split("#")[0].upper()
        embed = DiscordEmbed(
            title=f"PUMPSKIN LEVELING",
            description=f"Finished leveling pumpskin for {discord_username}\n",
            color=Color.orange().value,
        )

        embed.add_embed_field(name=f"Pumpskin", value=f"{token_id}", inline=False)
        embed.add_embed_field(name=f"Level", value=f"{level}", inline=True)

        pumpskin_image_uri = self.pumpskin_w2.get_pumpskin_image(token_id)

        embed.set_thumbnail(url=pumpskin_image_uri, height=100, width=100)
        webhook.add_embed(embed)
        webhook.execute()

    def _send_discord_low_gas_notification(self, avax_gas: float) -> None:
        webhook = DiscordWebhook(
            url=discord.DISCORD_WEBHOOK_URL["PUMPSKIN_ACTIVITY"], rate_limit_retry=True
        )
        discord_username = self.config_mgr.config["discord_handle"].split("#")[0].upper()
        embed = DiscordEmbed(
            title=f"\U000026FD Gas Alert!",
            description=f"Low $AVAX gas warning for {discord_username}\n",
            color=Color.red().value,
        )
        embed.add_embed_field(name=f"AVAX", value=f"{avax_gas:.3f}", inline=False)
        embed.set_thumbnail(url="https://plantatree.finance/images/avax.png", height=100, width=100)
        webhook.add_embed(embed)
        webhook.execute()

    def _update_stats(self) -> None:
        for k, v in self.current_stats.items():
            if type(v) != type(self.stats_logger.lifetime_stats.get(k)):
                logger.print_warn(
                    f"Mismatched stats:\n{self.current_stats}\n{self.stats_logger.lifetime_stats}"
                )
                continue

            if k in ["commission_ppie"]:
                continue

            if isinstance(v, list):
                self.stats_logger.lifetime_stats[k].extend(v)
            elif isinstance(v, dict):
                for i, j in self.stats_logger.lifetime_stats[k].items():
                    self.stats_logger.lifetime_stats[k][i] += self.current_stats[k][i]
            else:
                self.stats_logger.lifetime_stats[k] += v

        self.stats_logger.lifetime_stats["commission_ppie"] = self.stats_logger.lifetime_stats.get(
            "commission_ppie", {COMMISSION_WALLET_ADDRESS: 0.0}
        )

        ppie_rewards = self.current_stats["ppie"]
        for address, commission_percent in self.config_mgr.config[
            "commission_percent_per_mine"
        ].items():
            commission_ppie = ppie_rewards * (commission_percent / 100.0)

            self.stats_logger.lifetime_stats["commission_ppie"][address] = (
                self.stats_logger.lifetime_stats["commission_ppie"].get(address, 0.0)
                + commission_ppie
            )

            logger.print_ok(
                f"Added {commission_ppie} $PPIE for {address} in commission ({commission_percent}%)!"
            )

        self.ppie_since_last_claimed = self.current_stats["ppie"]
        self.current_stats = copy.deepcopy(NULL_GAME_STATS)

        logger.print_ok_blue(
            f"Lifetime Stats for {self.user.upper()}\n{json.dumps(self.stats_logger.lifetime_stats, indent=4)}"
        )

    def _send_email_update(self, num_staked_pumpskins: int) -> None:
        content = f"Gourd Stats for {self.user.upper()}:\n"
        content += f"Active Pumpskins: {num_staked_pumpskins}\n"
        content += f"Pumpskins Levels: {self.current_stats['levels']}\n\n"
        content += f"-----CLAIMED--------\n"
        content += f"$POTN: {self.current_stats['potn']}\n"
        content += f"$PPIE: {self.current_stats['ppie']}\n\n"
        if self.txns:
            content += f"TXs:\n"
            for tx in self.txns:
                content += f"{tx}\n"
            self.txns.clear()
        content += f"Lifetime Stats:\n{json.dumps(self.stats_logger.lifetime_stats, indent=4)}\n\n"
        content += f"--------------------\n"

        logger.print_bold("\n" + content + "\n")

        diff = deepdiff.DeepDiff(self.current_stats, NULL_GAME_STATS)
        if not diff:
            logger.print_normal(f"Didn't update any stats, not sending email...")
            return

        if self.dry_run:
            return

        subject = f"\U0001F383 Pumpskin Bot Update"

        if self.config_mgr.config["email"]:
            send_email(
                self.emails,
                self.config_mgr.config["email"],
                subject,
                content,
            )

    def _check_and_stake_ppie(self, pumpskins: T.Dict[int, T.Dict[int, T.Any]]) -> None:
        # we want to only stake the percent of PPIE we've claimed
        ppie_balance = min(float(self.ppie_w3.get_balance()), self.ppie_available_to_stake)

        ppie_available_to_stake = ppie_balance * (
            self.config_mgr.config["game_specific_configs"]["percent_ppie_stake"] / 100.0
        )

        multiplier = max(
            0.1, self.config_mgr.config["game_specific_configs"]["ppie_stake_multiplier"]
        )
        min_ppie_to_stake = self.calc_ppie_earned_per_day(pumpskins) * multiplier

        if ppie_available_to_stake > min_ppie_to_stake:
            # Try to stake PPIE
            total_claimable_potn = wei_to_token_raw(self.game_w3.get_claimable_potn(self.address))
            action_str = f"Attempting to stake {ppie_available_to_stake:.2f} $PPIE"
            if self._process_w3_results(
                action_str, self.game_w3.staking_ppie(token_to_wei(ppie_available_to_stake))
            ):
                # staking PPIE also claims POTN, so track that as POTN we've claimed
                self.potn_available_to_stake += total_claimable_potn
        else:
            logger.print_warn(
                f"Not going to stake $PPIE since it is below our threshold ({ppie_available_to_stake:.2f} < {min_ppie_to_stake:.2f})"
            )

    def _drink_potion(self, token_id: int, potn_to_level: int) -> bool:
        num_potn_wei = token_to_wei(potn_to_level)
        if num_potn_wei <= 0.0:
            return True

        action_str = f"Attempting to have pumpskin {token_id} drink {potn_to_level} $POTN"
        return self._process_w3_results(
            action_str, self.game_w3.drink_potion(token_id, num_potn_wei)
        )

    def _level_pumpskins(self, token_id: int, next_level: int, is_special: bool) -> None:
        # Level Pumpskin who can be leveled up
        if is_special:
            action_str = f"Attempting to Level up special pumpskin {token_id} to {next_level}..."
        else:
            action_str = f"Attempting to Level up pumpskin {token_id} to {next_level}..."

        if self._process_w3_results(action_str, self.collection_w3.level_up_pumpkin(token_id)):
            self.current_stats["levels"] += 1
            self._send_leveling_discord_activity_update(token_id, next_level)

    def _is_cooled_down(self, token_id: int, pumpskin: T.Dict[str, T.Any]) -> bool:
        # check to see if we're past the cooldown period
        now = time.time()
        cooldown_time = pumpskin.get("cooldown_ts", now) - now
        if cooldown_time < 0:
            return True
        time_left_pretty = get_pretty_seconds(cooldown_time)
        logger.print_warn(
            f"Pumpskin {token_id} not ready for leveling yet. Remaining time: {time_left_pretty}"
        )
        return False

    def _try_to_level_pumpskins(self, pumpskins: T.Dict[int, T.Dict[int, T.Any]]) -> None:
        # Now try to level pumpskins...
        for token_id, pumpskin in pumpskins.items():
            if not self._is_cooled_down(token_id, pumpskin):
                continue

            # check to see how much POTN needed to level up
            level = pumpskin.get("kg", 10000) / 100
            next_level = level + 1
            level_potn = self.calc_potn_from_level(level)
            logger.print_ok_blue(
                f"Pumpskin {token_id}, Level {level} POTN needed for {next_level}: {level_potn}"
            )
            potn_to_level = level_potn - pumpskin.get("eaten_amount", 100000)

            special_pumps = self.config_mgr.config["game_specific_configs"]["special_pumps"]
            is_special = token_id in special_pumps
            if is_special:
                if next_level > special_pumps[token_id]:
                    logger.print_ok_blue(
                        f"Skipping level up for special pump {token_id} since at max level: {level}"
                    )
                    continue
            elif next_level > self.config_mgr.config["game_specific_configs"]["max_level"]:
                logger.print_ok_blue(
                    f"Skipping level up for {token_id} since at max user level: {level}"
                )
                continue

            if (
                self.config_mgr.config["game_specific_configs"]["only_special_pumps"]
                and not is_special
            ):
                logger.print_normal(f"Skipping {token_id} b/c only leveling special pumpskins...")
                continue

            potn_balance = self.potn_w3.get_balance()
            if potn_balance < potn_to_level:
                logger.print_warn(
                    f"Not enough $POTN to level up {token_id} to {next_level}.\n\tHave: {potn_balance:.2f} Need: {potn_to_level:.2f}. Skipping..."
                )
                continue

            if not self._drink_potion(token_id, potn_to_level):
                continue

            self._level_pumpskins(token_id, next_level, is_special)

    def _check_and_claim_potn(
        self, pumpskins: T.Dict[int, T.Dict[int, T.Any]], force: bool = False
    ) -> None:
        logger.print_ok_blue(f"Checking $POTN for claims...")
        total_claimable_potn = wei_to_token_raw(self.game_w3.get_claimable_potn(self.address))

        multiplier = max(
            0.1, self.config_mgr.config["game_specific_configs"]["potn_claim_multiplier"]
        )

        ppie_staked = wei_to_token_raw(self.game_w3.get_ppie_staked(self.address))
        min_potn_to_claim = ppie_staked * 3 * multiplier

        if total_claimable_potn >= min_potn_to_claim or force:
            self._claim_potn(total_claimable_potn)
        else:
            logger.print_warn(
                f"Not enough $POTN to claim ({total_claimable_potn:.2f} < {min_potn_to_claim})"
            )

    def _check_and_claim_ppie(
        self,
        pumpskins: T.Dict[int, T.Dict[int, T.Any]],
        force: bool = False,
        verbose: bool = False,
    ) -> None:
        logger.print_ok_blue(f"Checking $PPIE for claims...")
        total_claimable_ppie = 0.0

        ppie_tokens = []
        for token_id in pumpskins.keys():
            claimable_tokens = wei_to_token_raw(self.collection_w3.get_claimable_ppie(token_id))
            if verbose:
                logger.print_normal(
                    f"Pumpskin {token_id} has {claimable_tokens:.2f} $PPIE to claim"
                )
            total_claimable_ppie += claimable_tokens

            if claimable_tokens > 0.0:
                ppie_tokens.append(token_id)

        ppie_staked = wei_to_token_raw(self.game_w3.get_ppie_staked(self.address))
        potn_per_day = ppie_staked * 3.0
        ppie_per_day = self.calc_ppie_earned_per_day(pumpskins)

        logger.print_normal(
            f"{ppie_staked:.2f} staked $PPIE producing {potn_per_day:.2f} $POTN daily"
        )
        logger.print_normal(
            f"{len(pumpskins.keys())} Pumpskins producing {ppie_per_day:.2f} $PPIE daily"
        )

        # wait to claim at a half day's earnings
        multiplier = max(
            0.1, self.config_mgr.config["game_specific_configs"]["ppie_claim_multiplier"]
        )
        min_ppie_to_claim = ppie_per_day * multiplier

        if total_claimable_ppie >= min_ppie_to_claim or force:
            self._claim_ppie(ppie_tokens, total_claimable_ppie)
        else:
            logger.print_warn(
                f"Not enough $PPIE to claim ({total_claimable_ppie:.2f} < {min_ppie_to_claim})"
            )

    def _claim_ppie(self, ppie_tokens: T.List[int], ppie_to_claim: float) -> None:
        action_str = f"Attempting to claim {ppie_to_claim:.2f} $PPIE for {self.user}..."
        if self._process_w3_results(action_str, self.collection_w3.claim_pies(ppie_tokens)):
            self.current_stats["ppie"] += ppie_to_claim
            self.ppie_available_to_stake += ppie_to_claim

    def _claim_potn(self, potn_to_claim: float) -> None:
        action_str = f"Attempting to claim {potn_to_claim:.2f} $POTN for {self.user}..."
        if self._process_w3_results(action_str, self.game_w3.claim_potn()):
            self.current_stats["potn"] += potn_to_claim
            self.potn_available_to_stake += potn_to_claim

    def _check_for_low_gas(self, num_pumpskins: int) -> None:
        avax_w3: AvaxCWeb3Client = T.cast(
            AvaxCWeb3Client,
            (
                AvaxCWeb3Client()
                .set_credentials(
                    self.config_mgr.config["address"], self.config_mgr.config["private_key"]
                )
                .set_node_uri(AvalancheCWeb3Client.NODE_URL)
                .set_dry_run(self.dry_run)
            ),
        )
        avax_balance = avax_w3.get_balance()
        avg_gas_per_action = 0.002
        action_per_pump = 2
        gas_needed_per_pump = avg_gas_per_action * action_per_pump
        num_pump_activites_buffer = 5
        gas_needed = num_pump_activites_buffer * gas_needed_per_pump

        if avax_balance > gas_needed:
            return

        email_message = f"Hello {self.alias}!\n"
        email_message += f"You're running low on gas! Please make sure to top "
        email_message += f"off wallet {self.address} so that your patch can "
        email_message += f"continue to grow!\n\n"
        email_message += f"\U000026FD Balance: {avax_balance:.2f} $AVAX"

        logger.print_warn("\n" + email_message + "\n")

        now = time.time()
        if now - self.last_gas_notification < self.LOW_GAS_INTERVAL:
            return

        self.last_gas_notification = now

        if self.dry_run:
            return

        self._send_discord_low_gas_notification(avax_balance)

        subject = f"\U000026FD\U000026FD Pumpskin Bot Gas Alert!"

        if self.config_mgr.config["email"]:
            send_email(
                self.emails,
                self.config_mgr.config["email"],
                subject,
                email_message,
            )

    def _check_for_token_approvals(self) -> None:
        logger.print_normal(f"\n\nChecking PPIE and POTN approvals for {self.user}")

        for _, v in self.token_manager.items():
            self.txns.extend(v.check_and_approve_contracts())

    def _check_and_take_profits_and_stake_lp(self) -> None:
        for _, v in self.token_manager.items():
            self.txns.extend(v.check_and_claim_rewards_from_lp_stake())

        for _, v in self.token_manager.items():
            self.txns.extend(v.check_swap_and_lp_and_stake())

    def _run_game_loop(self) -> None:
        pumpskin_ids: T.List[int] = self.get_pumpskin_ids()
        pumpskins = {}
        for token_id in pumpskin_ids:
            pumpskin: StakedPumpskin = self.collection_w3.get_staked_pumpskin_info(token_id)
            pumpskins[token_id] = pumpskin

        ordered_pumpskins = dict(
            sorted(
                pumpskins.items(),
                key=lambda y: y[1].get("kg", 10000) / 100,
            )
        )

        # insert special pumpkins to the front of the leveling group
        final_pumpskins = {}
        for token_id_str in self.config_mgr.config["game_specific_configs"]["special_pumps"].keys():
            token_id = int(token_id_str)
            final_pumpskins[token_id] = ordered_pumpskins[token_id]
            del ordered_pumpskins[token_id]

        final_pumpskins.update(ordered_pumpskins)

        potn_balance = self.potn_w3.get_balance()
        ppie_balance = self.ppie_w3.get_balance()
        num_pumpskins = len(final_pumpskins.keys())

        logger.print_bold(f"{self.user} Balances:")
        logger.print_ok_arrow(f"PPIE: {ppie_balance:.2f}")
        logger.print_ok_arrow(f"POTN: {potn_balance:.2f}")
        logger.print_ok_arrow(f"\U0001F383: {num_pumpskins}")

        self._try_to_level_pumpskins(final_pumpskins)
        self._check_and_claim_ppie(final_pumpskins)
        self._check_and_stake_ppie(final_pumpskins)
        # staking PPIE should claim all outstanding POTN in one transaction
        # so we should really not trigger this often
        self._check_and_claim_potn(final_pumpskins)

        self._send_email_update(num_pumpskins)
        self._check_for_low_gas(num_pumpskins)
        self._update_stats()

    def init(self) -> None:
        self.config_mgr.init()

    def run(self) -> None:
        self._check_for_token_approvals()

        logger.print_bold(f"\n\nAttempting leveling activities for {self.user}")

        self._run_game_loop()
        self.stats_logger.write()

    def end(self) -> None:
        self.config_mgr.close()
        self.stats_logger.write()
        logger.print_normal(f"Shutting down {self.user} bot...")
