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
from pumpskin.allocator import TokenAllocator
from pumpskin.game_stats import PumpskinLifetimeGameStatsLogger
from pumpskin.lp_token_web3_client import PotnLpWeb3Client, PpieLpWeb3Client
from pumpskin.types import Category, Tokens

ClassType = T.TypeVar("ClassType", bound="PumpskinTokenProfitManager")


@yaspin(text="Waiting...")
def wait(wait_time) -> None:
    time.sleep(wait_time)


class PumpskinTokenProfitManager:
    MIN_POTN_REWARDS_CLAIM = 200.0
    MAX_SLIPPAGE_PERCENT = 5.0
    SLIPPAGE_INCREMENT_PERCENT = 0.25
    MIN_AVAX_CONVERSION = 0.1

    def __init__(
        self,
        staking_w3: AvalancheCWeb3Client,
        lp_w3: AvalancheCWeb3Client,
        tj_w3: TraderJoeWeb3Client,
        token_w3: AvalancheCWeb3Client,
        token: Tokens,
        config: UserConfig,
        stats_logger: PumpskinLifetimeGameStatsLogger,
        allocator: TokenAllocator,
        min_token_amount_to_swap: float,
        dry_run: bool = False,
        quiet: bool = False,
    ):
        self.token = token
        self.token_w3 = token_w3
        self.tj_w3 = tj_w3
        self.staking_w3 = staking_w3
        self.lp_w3 = lp_w3
        self.config = config["game_specific_configs"]
        self.discord_handle = config["discord_handle"]
        self.stats_logger = stats_logger
        self.allocator = allocator
        self.quiet = quiet
        self.txns = []
        # TODO: remove and make this dynamic below
        self.rewards_rate = {
            Tokens.PPIE: 0.869 / 4.046,
            Tokens.POTN: 0.092 / 3.797,
        }
        self.min_token_amount_to_swap = min_token_amount_to_swap
        self.max_avax_multiplier = 1.0

    @classmethod
    def create_token_profit_lp_class(
        cls: T.Type[ClassType],
        token: Tokens,
        config: UserConfig,
        lp_class: T.Any,
        stake_contract_class: T.Any,
        token_w3: AvalancheCWeb3Client,
        stats_logger: PumpskinLifetimeGameStatsLogger,
        allocator: TokenAllocator,
        min_token_amount_to_swap: float,
        dry_run: bool = False,
        quiet: bool = False,
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
            token,
            config,
            stats_logger,
            allocator,
            min_token_amount_to_swap,
            dry_run,
            quiet,
        )

    def check_and_claim_rewards_from_lp_stake(self) -> T.List[str]:
        lps_staked = self.staking_w3.get_balance()
        amount_claimable = self.staking_w3.get_rewards()

        multiplier = self.config["rewards_claim_multiplier"]
        # TODO: min_rewards_amount_claimable = self.staking_w3.get_rewards_rate_per_day() * multiplier
        rate_per_hour = self.rewards_rate[self.token] * lps_staked
        rate_per_day = rate_per_hour * 24
        min_rewards_amount_claimable = max(
            self.MIN_POTN_REWARDS_CLAIM, rate_per_day * multiplier
        )

        if amount_claimable < min_rewards_amount_claimable:
            logger.print_normal(
                f"Skipping rewards claim of {amount_claimable:.2f} POTN b/c under threshold of {min_rewards_amount_claimable:.2f}"
            )
            return []

        action_str = f"Claiming {self.token} LP staking rewards"
        self._process_w3_results(action_str, self.staking_w3.claim_rewards())
        total_txns = self.txns
        self.txns = []
        return total_txns

    def check_and_approve_contracts(self) -> T.List[str]:
        if not self.token_w3.is_allowed():
            action_str = f"Approving {self.token} contract for use"
            self._process_w3_results(action_str, self.token_w3.approve())
        else:
            logger.print_ok_arrow(f"{self.token} contract already approved")

        if not self.lp_w3.is_allowed():
            action_str = f"Approving {self.token}/LP"
            self._process_w3_results(action_str, self.lp_w3.approve())
        else:
            logger.print_ok_arrow(f"{self.token}/LP contract already approved")

        total_txns = self.txns
        self.txns = []
        return total_txns

    def check_swap_and_lp_and_stake(self) -> T.List[str]:
        logger.print_normal(
            f"Using a multiplier of: {self.max_avax_multiplier:.2f}"
        )

        profit_token = (
            self.allocator[self.token].get_amount(Category.PROFIT)
            * self.max_avax_multiplier
        )
        lp_token = (
            self.allocator[self.token].get_amount(Category.LP)
            * self.max_avax_multiplier
            / 2.0
        )

        avax_token = profit_token + lp_token

        if avax_token <= 0.0:
            logger.print_warn(f"Skipping swap since nothing to swap!")
            return []

        path = [
            self.token_w3.contract_checksum_address,
            AvaxCWeb3Client.WAVAX_ADDRESS,
        ]

        logger.print_normal(
            f"From {self.allocator[self.token].get_total():.2f} {self.token} available, testing {avax_token:.4f} {self.token} in..."
        )

        avax_out_wei = self.tj_w3.get_amounts_out(
            token_to_wei(avax_token), path
        )[-1]
        amount_out_min_wei = int(avax_out_wei / 100 * 99.5)

        profit_avax = (
            wei_to_token(amount_out_min_wei) * profit_token / avax_token
        )
        lp_avax = wei_to_token(amount_out_min_wei) * lp_token / avax_token

        logger.print_normal(
            f"AVAX for profit: {profit_avax:.4f}, Total AVAX: {profit_avax + lp_avax:.4f}"
        )
        logger.print_normal(
            f"{self.token} for LP: {lp_token:.2f}, AVAX for LP: {lp_avax:.4f}"
        )

        is_contributing_to_lp = (
            self.allocator[self.token].percents(Category.LP) > 0.0
        )
        is_taking_profits = (
            self.allocator[self.token].percents(Category.PROFIT) > 0.0
        )

        total_avax = wei_to_token(avax_out_wei)

        if (
            avax_out_wei <= 0.0
            or (lp_avax <= 0.0 and is_contributing_to_lp)
            or (
                profit_avax < self.config["min_avax_to_profit"]
                and is_taking_profits
            )
            or total_avax
            < max(self.MIN_AVAX_CONVERSION, self.config["min_avax_to_profit"])
        ):
            logger.print_warn(f"Skipping swap due to too low of levels...")
            return []

        action_str = f"Converting {avax_token:.2f} {self.token} to AVAX"
        did_succeed = False
        for i in range(
            int(self.MAX_SLIPPAGE_PERCENT / self.SLIPPAGE_INCREMENT_PERCENT)
        ):
            slippage = 100.0 - self.SLIPPAGE_INCREMENT_PERCENT * i
            amount_out_min_wei = int(amount_out_min_wei / 100.0 * slippage)
            logger.print_normal(
                f"Attempting to swap AVAX with {self.SLIPPAGE_INCREMENT_PERCENT * i:.2f}% slippage..."
            )
            if self._process_w3_results(
                action_str,
                self.tj_w3.swap_exact_tokens_for_avax(
                    token_to_wei(avax_token), amount_out_min_wei, path
                ),
            ):
                did_succeed = True
                break
            else:
                logger.print_warn(f"Unable to swap {self.token} to AVAX...")

        if not did_succeed:
            self.txns = []
            total_txns = self.txns
            mult_before = self.max_avax_multiplier
            self.max_avax_multiplier = max(0.05, self.max_avax_multiplier * 0.5)
            logger.print_bold(
                f"Updating conversion multiplier from {mult_before:.2f} to {self.max_avax_multiplier:.2f}"
            )
            return total_txns

        self.max_avax_multiplier = 1.0
        self.allocator[self.token].maybe_subtract(lp_token * 2, Category.LP)
        self.allocator[self.token].maybe_subtract(profit_token, Category.PROFIT)
        self.stats_logger.lifetime_stats[f"avax_profits"] += profit_avax

        wait(10.0)

        lp_amount = 0.0

        if lp_avax > 0.0 and lp_token > 0.0:
            lp_amount = self._buy_and_stake_token_lp(lp_avax, lp_token)

        if lp_amount > 0.0 or profit_avax > 0.0:
            self._send_discord_profit_lp_purchase(
                profit_avax, lp_avax, lp_token, lp_amount
            )

        total_txns = self.txns
        self.txns = []
        return total_txns

    def _send_discord_profit_lp_purchase(
        self,
        profit_avax: float,
        lp_avax: float,
        lp_token: float,
        lp_amount: float,
    ) -> None:
        if self.quiet:
            return

        webhook = DiscordWebhook(
            url=discord.DISCORD_WEBHOOK_URL["PUMPSKIN_ACTIVITY"],
            rate_limit_retry=True,
        )
        discord_username = self.discord_handle.split("#")[0].upper()
        embed = DiscordEmbed(
            title=f"Profit + LP Bolster",
            description=f"Update on profits and LP purchase for {discord_username}\n",
            color=Color.blue().value,
        )
        embed.add_embed_field(
            name=f"Profit AVAX", value=f"{profit_avax:.3f}", inline=False
        )
        embed.add_embed_field(
            name=f"LP AVAX", value=f"{lp_avax:.3f}", inline=False
        )
        embed.add_embed_field(
            name=f"LP {self.token}", value=f"{lp_token:.3f}", inline=True
        )
        embed.add_embed_field(
            name=f"JLP Purchased/Staked", value=f"{lp_amount:.3f}", inline=False
        )
        embed.set_image(
            url=f"https://pumpskin.xyz/_next/image?url=%2F_next%2Fstatic%2Fmedia%2Flogo-full.c1b1f2e3.png&w=1920&q=75"
        )
        webhook.add_embed(embed)
        webhook.execute()

    def _process_w3_results(self, action_str: str, tx_hash: str) -> bool:
        logger.print_bold(f"{action_str}")

        tx_receipt = self.token_w3.get_transaction_receipt(tx_hash)
        gas = wei_to_token(
            self.token_w3.get_gas_cost_of_transaction_wei(tx_receipt)
        )
        logger.print_bold(f"Paid {gas} AVAX in gas")

        self.stats_logger.lifetime_stats["avax_gas"] += gas

        if tx_receipt.get("status", 0) != 1:
            logger.print_fail(f"Failed to: {action_str}!")
            return False
        else:
            logger.print_ok(f"Successfully: {action_str}")
            self.txns.append(f"https://snowtrace.io/tx/{tx_hash}")
            logger.print_normal(
                f"Explorer: https://snowtrace.io/tx/{tx_hash}\n\n"
            )
            return True

    def _buy_and_stake_token_lp(
        self, amount_avax: float, amount_token: float
    ) -> float:
        logger.print_ok_blue(
            f"Putting together {self.token}/AVAX pool: {amount_token:.2f} {self.token} | {amount_avax:.4f} AVAX"
        )

        max_slippage_percent = 95.0
        action_str = f"Buying {self.token}/AVAX LP Token"

        for i in range(
            int(self.MAX_SLIPPAGE_PERCENT / self.SLIPPAGE_INCREMENT_PERCENT)
        ):
            slippage = 100.0 - self.SLIPPAGE_INCREMENT_PERCENT * i
            amount_token_min = int(
                token_to_wei(amount_token) / 100.0 * slippage
            )
            amount_avax_min = int(token_to_wei(amount_avax) / 100.0 * slippage)
            logger.print_normal(
                f"Attempting to buy LP with {slippage:.2f}% slippage..."
            )
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
            amount_token_lp = float(f"{self.lp_w3.get_balance():.5f}")
            action_str = (
                f"Staking {amount_token_lp:.5f} {self.token}/AVAX LP Token"
            )
            if self._process_w3_results(
                action_str, self.staking_w3.stake(token_to_wei(amount_token_lp))
            ):
                self.stats_logger.lifetime_stats[
                    f"{self.token.lower()}_lp_tokens"
                ] += amount_token_lp

            return amount_token_lp

        return 0.0
