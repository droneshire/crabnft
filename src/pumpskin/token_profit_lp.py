import typing as T
import time

from discord import Color
from discord_webhook import DiscordEmbed, DiscordWebhook
from yaspin import yaspin

from utils import discord, logger
from utils.config_types import UserConfig
from utils.general import get_pretty_seconds
from utils.price import token_to_wei, wei_to_token
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client
from web3_utils.avax_web3_client import AvaxCWeb3Client
from web3_utils.traderjoe_web3_client import TraderJoeWeb3Client
from web3_utils.web3_client import Web3Client
from pumpskin.game_stats import PumpskinLifetimeGameStatsLogger
from pumpskin.lp_token_web3_client import PotnLpWeb3Client, PpieLpWeb3Client

ClassType = T.TypeVar("ClassType", bound="PumpskinTokenProfitManager")


@yaspin(text="Waiting...")
def wait(wait_time) -> None:
    time.sleep(wait_time)


class PumpskinTokenProfitManager:
    MIN_POTN_REWARDS_CLAIM = 200.0

    def __init__(
        self,
        staking_w3: AvalancheCWeb3Client,
        lp_w3: AvalancheCWeb3Client,
        tj_w3: TraderJoeWeb3Client,
        token_w3: AvalancheCWeb3Client,
        token_name: str,
        config: UserConfig,
        stats_logger: PumpskinLifetimeGameStatsLogger,
        min_token_amount_to_swap: float,
        dry_run: bool = False,
    ):
        self.token_name = token_name.upper()
        self.token_w3 = token_w3
        self.tj_w3 = tj_w3
        self.staking_w3 = staking_w3
        self.lp_w3 = lp_w3
        self.config = config["game_specific_configs"]["lp_and_profit_strategy"]
        self.discord_handle = config["discord_handle"]
        self.enabled = self.config["enabled"]
        self.stats_logger = stats_logger
        self.txns = []
        # TODO: remove and make this dynamic below
        self.rewards_rate = {
            "PPIE": 0.869 / 4.046,
            "POTN": 0.092 / 3.797,
        }
        self.min_token_amount_to_swap = min_token_amount_to_swap

        assert (
            config["game_specific_configs"]["lp_and_profit_strategy"][
                f"percent_{self.token_name.lower()}_profit_convert"
            ]
            + config["game_specific_configs"]["lp_and_profit_strategy"][
                f"percent_{self.token_name.lower()}_hold"
            ]
        ) <= 100.0, "Invalid percentages for percent profit/hold"

    @classmethod
    def create_token_profit_lp_class(
        cls: T.Type[ClassType],
        token_name: str,
        config: UserConfig,
        lp_class: T.Any,
        stake_contract_class: T.Any,
        token_w3: AvalancheCWeb3Client,
        stats_logger: PumpskinLifetimeGameStatsLogger,
        min_token_amount_to_swap: float,
        dry_run: bool = False,
    ) -> ClassType:
        address = config["address"]
        private_key = config["private_key"]

        tj_w3: TraderJoeWeb3Client = (
            TraderJoeWeb3Client()
            .set_credentials(address, private_key)
            .set_node_uri(AvalancheCWeb3Client.NODE_URL)
            .set_contract()
            .set_dry_run(dry_run)
        )

        lp_w3: lp_class = (
            lp_class()
            .set_credentials(address, private_key)
            .set_node_uri(AvalancheCWeb3Client.NODE_URL)
            .set_contract()
            .set_dry_run(dry_run)
        )

        stake_w3: stake_contract_class = (
            stake_contract_class()
            .set_credentials(address, private_key)
            .set_node_uri(stake_contract_class.NODE_URL)
            .set_contract()
            .set_dry_run(dry_run)
        )
        return cls(
            stake_w3,
            lp_w3,
            tj_w3,
            token_w3,
            token_name,
            config,
            stats_logger,
            min_token_amount_to_swap,
            dry_run,
        )

    def check_and_claim_rewards_from_lp_stake(self) -> T.List[str]:
        lps_staked = self.staking_w3.get_balance()
        amount_claimable = self.staking_w3.get_rewards()

        multiplier = max(0.1, self.config["rewards_claim_multiplier"])
        # TODO: min_rewards_amount_claimable = self.staking_w3.get_rewards_rate_per_day() * multiplier
        rate_per_hour = self.rewards_rate[self.token_name] * lps_staked
        rate_per_day = rate_per_hour * 24
        min_rewards_amount_claimable = max(self.MIN_POTN_REWARDS_CLAIM, rate_per_day * multiplier)

        if amount_claimable < min_rewards_amount_claimable:
            logger.print_normal(
                f"Skipping rewards claim of {amount_claimable:.2f} POTN b/c under threshold of {min_rewards_amount_claimable:.2f}"
            )
            return []

        action_str = f"Claiming {self.token_name} LP staking rewards"
        self._process_w3_results(action_str, self.staking_w3.claim_rewards())
        total_txns = self.txns
        self.txns = []
        return total_txns

    def check_and_approve_contracts(self) -> T.List[str]:
        if not self.token_w3.is_allowed():
            action_str = f"Approving {self.token_name} contract for use"
            self._process_w3_results(action_str, self.token_w3.approve())
        else:
            logger.print_ok_arrow(f"{self.token_name} contract already approved")

        if not self.lp_w3.is_allowed():
            action_str = f"Approving {self.token_name}/LP"
            self._process_w3_results(action_str, self.lp_w3.approve())
        else:
            logger.print_ok_arrow(f"{self.token_name}/LP contract already approved")

        total_txns = self.txns
        self.txns = []
        return total_txns

    def check_swap_and_lp_and_stake(
        self, amount_available: float, percent_token_leveling: float
    ) -> T.List[str]:
        if not self.enabled:
            logger.print_warn(f"Skipping {self.token_name} swap since user not opted in")
            return []

        if self.config["use_full_available_balances"]:
            amount_available = self.token_w3.get_balance()
        else:
            amount_available = min(amount_available, self.token_w3.get_balance() * 0.95)

        if amount_available < self.min_token_amount_to_swap:
            logger.print_warn(
                f"Skipping {self.token_name} swap since we only have {amount_available:.2f} available to swap"
            )
            return []

        percent_profit = self.config[f"percent_{self.token_name.lower()}_profit_convert"] / 100.0
        percent_hold = self.config[f"percent_{self.token_name.lower()}_hold"] / 100.0
        profit_token = amount_available * percent_profit
        hold_token = amount_available * percent_hold

        lp_token = max(
            0.0,
            (amount_available - profit_token - hold_token) * (1.0 - percent_token_leveling) / 2.0,
        )
        avax_token = profit_token + lp_token

        if avax_token <= 0.0:
            logger.print_warn(f"Skipping swap since nothing to swap!")
            return []

        path = [self.token_w3.contract_checksum_address, AvaxCWeb3Client.WAVAX_ADDRESS]

        logger.print_normal(
            f"From {amount_available:.2f} {self.token_name} available, Testing {avax_token:.4f} {self.token_name} in..."
        )

        avax_out_wei = self.tj_w3.get_amounts_out(token_to_wei(avax_token), path)[-1]
        amount_out_min_wei = int(avax_out_wei / 100 * 99.5)

        profit_avax = wei_to_token(amount_out_min_wei) * profit_token / avax_token
        lp_avax = wei_to_token(amount_out_min_wei) * lp_token / avax_token

        logger.print_normal(
            f"AVAX for profit: {profit_avax:.4f}, Total AVAX: {profit_avax + lp_avax:.4f}"
        )
        logger.print_normal(f"{self.token_name} for LP: {lp_token:.2f}, AVAX for LP: {lp_avax:.4f}")

        if avax_out_wei <= 0.0 or lp_avax <= 0.0 or profit_avax < self.config["min_avax_to_profit"]:
            logger.print_warn(f"Skipping swap due to too low of levels...")
            return []

        action_str = f"Converting {avax_token:.2f} {self.token_name} to AVAX"
        if not self._process_w3_results(
            action_str,
            self.tj_w3.swap_exact_tokens_for_avax(
                token_to_wei(avax_token), amount_out_min_wei, path
            ),
        ):
            logger.print_warn(f"Unable to swap {self.token_name} to AVAX...")

            total_txns = self.txns
            self.txns = []
            return total_txns

        token_available = self.stats_logger.lifetime_stats["amounts_available"][
            self.token_name.lower()
        ]
        self.stats_logger.lifetime_stats["amounts_available"][self.token_name.lower()] = max(
            0.0, token_available - avax_token
        )
        self.stats_logger.lifetime_stats[f"avax_profits"] += profit_avax

        wait(10.0)

        lp_amount = self._buy_and_stake_token_lp(lp_avax, lp_token)

        if lp_amount > 0.0 or profit_avax > 0.0:
            self._send_discord_profit_lp_purchase(profit_avax, lp_avax, lp_token, lp_amount)

        total_txns = self.txns
        self.txns = []
        return total_txns

    def _send_discord_profit_lp_purchase(
        self, profit_avax: float, lp_avax: float, lp_token: float, lp_amount: float
    ) -> None:
        webhook = DiscordWebhook(
            url=discord.DISCORD_WEBHOOK_URL["PUMPSKIN_ACTIVITY"], rate_limit_retry=True
        )
        discord_username = self.discord_handle.split("#")[0].upper()
        embed = DiscordEmbed(
            title=f"Profit + LP Bolster",
            description=f"Update on profits and LP purchase for {discord_username}\n",
            color=Color.blue().value,
        )
        embed.add_embed_field(name=f"Profit AVAX", value=f"{profit_avax:.3f}", inline=False)
        embed.add_embed_field(name=f"LP AVAX", value=f"{lp_avax:.3f}", inline=False)
        embed.add_embed_field(name=f"LP {self.token_name}", value=f"{lp_token:.3f}", inline=True)
        embed.add_embed_field(name=f"JLP Purchased/Staked", value=f"{lp_amount:.3f}", inline=False)
        embed.set_image(
            url=f"https://pumpskin.xyz/_next/image?url=%2F_next%2Fstatic%2Fmedia%2Flogo-full.c1b1f2e3.png&w=1920&q=75"
        )
        webhook.add_embed(embed)
        webhook.execute()

    def _process_w3_results(self, action_str: str, tx_hash: str) -> bool:
        logger.print_bold(f"{action_str}")

        tx_receipt = self.token_w3.get_transaction_receipt(tx_hash)
        gas = wei_to_token(self.token_w3.get_gas_cost_of_transaction_wei(tx_receipt))
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

    def _buy_and_stake_token_lp(self, amount_avax: float, amount_token: float) -> float:
        logger.print_ok_blue(
            f"Putting together {self.token_name}/AVAX pool: {amount_token:.2f} {self.token_name} | {amount_avax:.4f} AVAX"
        )

        max_slippage_percent = 95.0
        action_str = f"Buying {self.token_name}/AVAX LP Token"

        for i in range(20):
            slippage = 100.0 - 0.25 * i
            amount_token_min = int(token_to_wei(amount_token) / 100.0 * slippage)
            amount_avax_min = int(token_to_wei(amount_avax) / 100.0 * 99.5)
            logger.print_normal(f"Attempting to buy LP with {slippage:.2f}% slippage...")
            if not self._process_w3_results(
                action_str,
                self.tj_w3.buy_lp_token(
                    self.token_w3.contract_checksum_address,
                    token_to_wei(amount_token),
                    token_to_wei(amount_avax),
                    amount_token_min,
                    amount_avax_min,
                ),
            ):
                continue

            # wait to let transaction settle
            wait(15.0)
            amount_token_lp = self.lp_w3.get_balance()
            action_str = f"Staking {amount_token_lp} {self.token_name}/AVAX LP Token"
            if self._process_w3_results(
                action_str, self.staking_w3.stake(token_to_wei(amount_token_lp))
            ):
                self.stats_logger.lifetime_stats[
                    f"{self.token_name.lower()}_lp_tokens"
                ] += amount_token_lp

            return amount_token_lp

        return 0.0
