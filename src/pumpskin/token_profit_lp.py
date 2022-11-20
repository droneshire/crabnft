import typing as T

from utils import logger
from utils.config_types import UserConfig
from utils.price import token_to_wei, wei_to_token_raw
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client
from web3_utils.avax_web3_client import AvaxCWeb3Client
from web3_utils.traderjoe_web3_client import TraderJoeWeb3Client
from web3_utils.web3_client import Web3Client
from pumpskin.game_stats import PumpskinLifetimeGameStatsLogger
from pumpskin.lp_token_web3_client import PotnLpWeb3Client, PpieLpWeb3Client


ClassType = T.TypeVar("ClassType", bound="PumpskinTokenProfitManager")


class PumpskinTokenProfitManager:
    def __init__(
        self,
        staking_w3: AvalancheCWeb3Client,
        lp_w3: AvalancheCWeb3Client,
        tj_w3: TraderJoeWeb3Client,
        token_w3: AvalancheCWeb3Client,
        token_name: str,
        config: T.Dict[T.Any, T.Any],
        stats_logger: PumpskinLifetimeGameStatsLogger,
        dry_run: bool = False,
    ):
        self.token_name = token_name.upper()
        self.token_w3 = token_w3
        self.tj_w3 = tj_w3
        self.staking_w3 = staking_w3
        self.lp_w3 = lp_w3
        self.config = config
        self.enabled = configs["enabled"]
        self.stats_logger = stats_logger
        self.txns = []

    @classmethod
    def create_token_profit_lp_class(
        cls: T.Type[ClassType],
        token_name: str,
        config: UserConfig,
        lp_class: T.Any,
        stake_contract_class: T.Any,
        token_w3: AvalancheCWeb3Client,
        stats_logger: PumpskinLifetimeGameStatsLogger,
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
            config["game_specific_configs"]["lp_contributions"],
            stats_logger,
            dry_run,
        )

    def check_and_claim_rewards_from_lp_stake(self) -> T.List[str]:
        lps_staked = self.staking_w3.get_balance()
        amount_claimable = self.staking_w3.get_rewards()

        multiplier = max(0.1, self.config["rewards_claim_multiplier"])
        # TODO: min_rewards_amount_claimable = self.staking_w3.get_rewards_rate_per_day() * multiplier
        rate_per_hour = 0.024 * lps_staked
        rate_per_day = rate_per_hour * 24
        min_rewards_amount_claimable = rate_per_day * multiplier

        if amount_claimable < min_rewards_amount_claimable:
            logger.print_normal(
                f"Skipping rewards claim of {amount_claimable} POTN b/c under threshold of {min_rewards_amount_claimable}"
            )
            return

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

    def check_swap_and_lp_and_stake(self, amount_available: float) -> T.List[str]:
        if not self.enabled:
            logger.print_warn(f"Skipping {self.token_name} swap since user not opted in")

        percent_profit = self.config[f"percent_{self.token_name.lower()}_profit"]
        token_profit = amount_available * percent_profit
        lp_token = (amount_available - token_profit) / 2
        token_to_avax = token_profit + lp_token
        path = [self.token_w3.contract_address, AvaxCWeb3Client.WAVAX_ADDRESS]

        avax_out_wei = self.tj_w3.get_amounts_out(token_to_wei(token_to_avax), path)[-1]
        amount_out_min_wei = int(avax_out_wei / 100 * 99.5)

        profit_avax = wei_to_token_raw(amount_out_min_wei) * token_profit / token_to_avax
        lp_avax = wei_to_token_raw(amount_out_min_wei) * lp_token / token_to_avax

        logger.print_normal(
            f"{self.token_name} for profit: {profit_avax:.2f}, {self.token_name} for LP: {lp_token:.2f}, AVAX for LP: {lp_avax:.2f}"
        )
        action_str = f"Converting {token_to_avax:.2f} {self.token_name} to AVAX"
        if not self._process_w3_results(
            action_str,
            self.tj_w3.swap_exact_tokens_for_avax(
                token_to_wei(token_to_avax), amount_out_min_wei, path
            ),
        ):
            logger.print_warn(f"Unable to swap {self.token_name} to AVAX...")
            total_txns = self.txns
            self.txns = []
            return total_txns

        self._buy_and_stake_token_lp(amount_out_min, token_lp)

        total_txns = self.txns
        self.txns = []
        return total_txns

    def _process_w3_results(self, action_str: str, tx_hash: str) -> bool:
        logger.print_bold(f"{action_str}")

        tx_receipt = self.token_w3.get_transaction_receipt(tx_hash)
        gas = wei_to_token_raw(self.token_w3.get_gas_cost_of_transaction_wei(tx_receipt))
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

    def _buy_and_stake_token_lp(self, amount_avax: float, amount_token: float) -> None:
        if not self.enabled:
            logger.print_warn(f"Skipping LP cycle since user not opted in")

        amount_token_min = int(token_to_wei(amount_token) / 100 * 99.5)
        amount_avax_min = int(token_to_wei(amount_avax) / 100 * 99.5)

        logger.print_ok_blue(
            f"Putting together {self.token_name}/AVAX pool: {amount_token} {self.token_name} | {amount_avax} AVAX"
        )

        action_str = f"Buying {self.token_name}/AVAX LP Token"
        if not self._process_w3_results(
            action_str,
            self.tj_w3.buy_lp_token(
                self.token_w3.contract_checksum_address,
                token_to_wei(amount_token),
                amount_token_min,
                amount_avax_min,
            ),
        ):
            return

        amount_token_lp = self.lp_w3.get_balance()
        action_str = f"Staking {amount_token_lp} {self.token_name}/AVAX LP Token"
        self._process_w3_results(action_str, self.staking_w3.stake(token_to_wei(amount_token_lp)))
