import os
import json
import typing as T

from eth_typing import Address
from eth_typing.encoding import HexStr
from web3.types import TxParams, Wei
from web3_utils.web3_client import Web3Client
from web3_utils.avalanche_c_web3_client import AvalancheCWeb3Client


class CrabadaWeb3Client(AvalancheCWeb3Client):
    """
    Interact with a smart contract of the game Crabada

    The contract resides on the Avalanche blockchain; here's the
    explorer URL:
    https://snowtrace.io/address/0x82a85407bd612f52577909f4a58bfc6873f14da8#tokentxns
    """

    TUS_CONTRACT_ADDRESS = Address("0xf693248F96Fe03422FEa95aC0aFbBBc4a8FdD172")
    CRA_CONTRACT_ADDRESS = Address("0xA32608e873F9DdEF944B24798db69d80Bbb4d1ed")

    contract_address = T.cast(Address, "0x82a85407bd612f52577909f4a58bfc6873f14da8")
    this_dir = os.path.dirname(os.path.realpath(__file__))
    abi_dir = os.path.join(os.path.dirname(this_dir), "web3_utils", "abi", "abi-crabada.json")
    abi = Web3Client._get_contract_abi_from_file(abi_dir)

    def start_game(self, team_id: int) -> HexStr:
        """
        Send crabs to mine
        """
        tx: TxParams = self.build_contract_transaction(self.contract.functions.startGame(team_id))
        return self.sign_and_send_transaction(tx)

    def attack(self, game_id: int, team_id: int) -> HexStr:
        """
        Attack an open mine
        """
        tx: TxParams = self.build_contract_transaction(
            self.contract.functions.attack(game_id, team_id)
        )
        return self.sign_and_send_transaction(tx)

    def close_game(self, game_id: int) -> HexStr:
        """
        Close mining game, claim reward & send crabs back home
        """
        tx: TxParams = self.build_contract_transaction(self.contract.functions.closeGame(game_id))
        return self.sign_and_send_transaction(tx)

    def settle_game(self, game_id: int) -> HexStr:
        """
        Close looting game, claim reward & send crabs back home
        """
        tx: TxParams = self.build_contract_transaction(self.contract.functions.settleGame(game_id))
        return self.sign_and_send_transaction(tx)

    def reinforce_defense(self, game_id: int, crabadaId: int, borrowPrice: Wei) -> HexStr:
        """
        Hire a crab from the tavern to reinforce the mining team; the
        price must be expressed in Wei (1 TUS = 10^18 Wei)
        """
        tx: TxParams = self.build_contract_transaction(
            self.contract.functions.reinforceDefense(game_id, crabadaId, borrowPrice)
        )
        return self.sign_and_send_transaction(tx)

    def reinforce_attack(self, game_id: int, crabadaId: int, borrowPrice: Wei) -> HexStr:
        """
        Hire a crab from the tavern to reinforce the looting team;
        the price must be expressed in Wei (1 TUS = 10^18 Wei)
        """
        tx: TxParams = self.build_contract_transaction(
            self.contract.functions.reinforceAttack(game_id, crabadaId, borrowPrice)
        )
        return self.sign_and_send_transaction(tx)
