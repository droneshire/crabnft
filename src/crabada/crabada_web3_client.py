import os
import json
import typing as T

from eth_typing import Address
from eth_typing.encoding import HexStr
from web3.types import TxParams, Wei
from web3_utils.web3_client import Web3Client
from web3_utils.swimmer_network_web3_client import SwimmerNetworkClient


class CrabadaWeb3Client(SwimmerNetworkClient):
    """
    Interact with a smart contract of the game Crabada

    The contract resides on the Swimmer subnet blockchain; here's
    the URL on Subnet explorer:
    https://subnets.avax.network/swimmer/mainnet/explorer/address/0x9ab9e81Be39b73de3CCd9408862b1Fc6D2144d2B
    """

    contract_address = T.cast(Address, "0x9ab9e81Be39b73de3CCd9408862b1Fc6D2144d2B")
    this_dir = os.path.dirname(os.path.realpath(__file__))
    abi_dir = os.path.join(os.path.dirname(this_dir), "web3_utils", "abi", "abi-crabada.json")
    abi = Web3Client._get_contract_abi_from_file(abi_dir)

    def start_game(self, team_id: int) -> HexStr:
        """
        Send crabs to mine
        """
        tx: TxParams = self.build_contract_transaction(self.contract.functions.startGame(team_id))
        return self.sign_and_send_transaction(tx)

    def attack(self, game_id: int, team_id: int, expired_time: int, certificate: int) -> HexStr:
        """
        Attack an open mine
        """
        tx: TxParams = self.build_contract_transaction(
            self.contract.functions.attack(game_id, team_id, expired_time, certificate)
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

    def reinforce_defense(self, game_id: int, crabadaId: int, borrow_price: Wei) -> HexStr:
        """
        Hire a crab from the tavern to reinforce the mining team; the
        price must be expressed in Wei (1 TUS = 10^18 Wei)
        """
        tx: TxParams = self.build_contract_transaction(
            self.contract.functions.reinforceDefense(game_id, crabadaId, borrow_price),
            value_in_wei=borrow_price,
        )
        return self.sign_and_send_transaction(tx)

    def reinforce_attack(self, game_id: int, crabadaId: int, borrow_price: Wei) -> HexStr:
        """
        Hire a crab from the tavern to reinforce the looting team;
        the price must be expressed in Wei (1 TUS = 10^18 Wei)
        """
        tx: TxParams = self.build_contract_transaction(
            self.contract.functions.reinforceAttack(game_id, crabadaId, borrow_price),
            value_in_wei=borrow_price,
        )
        return self.sign_and_send_transaction(tx)
