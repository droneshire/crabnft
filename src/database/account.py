import time
import typing as T

from contextlib import contextmanager
from sqlalchemy.sql import func

from database.connect import ManagedSession
from database.models.account import Account
from database.models.game_config import GameConfig
from database.models.wallet import Wallet
from utils import logger


class AccountDb:
    def __init__(self, owner: str) -> None:
        self.owner = owner
        self.wallets = []

        with ManagedSession() as db:
            user = db.query(Account).filter(Account.owner == owner).first()
            assert user is not None, f"Account {self.owner} not in DB!"
            logger.print_bold(f"{user} initiated")
            for wallet in user.wallets:
                self.wallets.append(wallet.address)

    @contextmanager
    def account(self) -> T.Iterator[Account]:
        with ManagedSession() as db:
            user = db.query(Account).filter(Account.owner == self.owner).first()
            assert user is not None, f"User {self.owner} not in DB!"

            yield user

            try:
                db.add(user)
            except:
                logger.print_fail("Failed to store db item!")

    @contextmanager
    def wallet(self, address: str) -> T.Iterator[GameConfig]:
        with ManagedSession() as db:
            wallet = (
                db.query(Wallet)
                .filter(Wallet.address == address)
                .filter(Wallet.address.in_(self.wallets))
                .first()
            )
            assert wallet is not None, f"Wallet for {address} not in DB!"

            yield wallet

            try:
                db.add(wallet)
            except:
                logger.print_fail("Failed to store db item!")

    @contextmanager
    def game_config(self, game: str, address: str) -> T.Iterator[GameConfig]:
        with ManagedSession() as db:
            wallet = (
                db.query(Wallet)
                .filter(Wallet.address == address)
                .filter(Wallet.address.in_(self.wallets))
                .first()
            )
            assert wallet is not None, f"Wallet for {address} not in DB!"

            game_config = (
                db.query(GameConfig)
                .filter(GameConfig.wallet_id == wallet.address)
                .filter(GameConfig.name == game)
                .first()
            )
            assert (
                game_config is not None
            ), f"{game.upper()} Game Config for {self.owner} not in DB!"
            yield game_config

            try:
                db.add(game_config)
            except:
                logger.print_fail("Failed to store db item!")

    @staticmethod
    def add_account(user: str, email: str, discord_handle: str) -> None:
        with ManagedSession() as db:
            account = db.query(Account).filter(Account.owner == user).first()
            if account is not None:
                logger.print_warn(f"Skipping {user} add, already in db")
                return

            logger.print_ok_arrow(f"Created {user} account")

            account = Account(owner=user, email=email, discord_handle=discord_handle)

            db.add(account)

    @staticmethod
    def add_wallet(user: str, address: str, private_key: str) -> None:
        with ManagedSession() as db:
            account = db.query(Account).filter(Account.owner == user).first()
            if account is None:
                logger.print_fail(f"Failed to add wallet, user doesn't exist!")
                return

            if address in [w.address for w in account.wallets]:
                logger.print_warn(f"Skipping add wallet, already in account!")
                return

            logger.print_ok_arrow(f"Created {address} wallet for {user}")

            wallet = Wallet(address=address, private_key=private_key, account_id=account.owner)

            db.add(wallet)

    @staticmethod
    def add_game_config(
        address: str, game: str, config_type: T.Any, email_updates: bool = True
    ) -> None:
        with ManagedSession() as db:
            wallet = db.query(Wallet).filter(Wallet.address == address).first()
            if wallet is None:
                logger.print_fail(f"Failed to add game config, wallet doesn't exist!")
                return

            if game in [g.name for g in wallet.game_configs]:
                logger.print_warn(f"Skipping config, already in wallet!")
                return

            logger.print_ok_arrow(f"Created {game} config for wallet {address}")

            config = config_type(name=game, email_updates=email_updates, wallet_id=wallet.address)

            db.add(config)

    @staticmethod
    def get_configs_for_game(game: str) -> T.List[Account]:
        with ManagedSession() as db:
            accounts = db.query(Account).join(Account.wallets).join(Wallet.game_configs).filter(GameConfig.name == game).all()
            return accounts
