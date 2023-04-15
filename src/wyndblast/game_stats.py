import time
import typing as T

from contextlib import contextmanager
from sqlalchemy.sql import func

from config_admin import STATS_DB
from database.connect import ManagedSession
from utils import logger
from wyndblast import types
from wyndblast.database.models.daily_activities import (
    DailyActivities,
    ElementalStones,
    WinLoss,
    WinLossSchema,
)
from wyndblast.database.models.commission import Commission
from wyndblast.database.models.pve import Level, Pve
from wyndblast.database.models.user import WyndblastUser


class PveStats(T.TypedDict):
    levels_completed: T.List[str]
    account_exp: int
    unclaimed_chro: float
    claimed_chro: float


class LifetimeStats(T.TypedDict):
    chro: float
    wams: float
    elemental_stones: types.ElementalStones
    stage_1: T.Dict[str, float]
    stage_2: T.Dict[str, float]
    stage_3: T.Dict[str, float]
    commission_chro: T.Dict[str, float]
    avax_gas: float
    pve_game: T.Dict[str, PveStats]


NULL_GAME_STATS = {
    "chro": 0.0,
    "wams": 0.0,
    "elemental_stones": {
        "Fire": 0,
        "Wind": 0,
        "Earth": 0,
        "Light": 0,
        "Darkness": 0,
        "Water": 0,
        "elemental_stones_qty": 0,
    },
    "stage_1": {
        "wins": 0,
        "losses": 0,
    },
    "stage_2": {
        "wins": 0,
        "losses": 0,
    },
    "stage_3": {
        "wins": 0,
        "losses": 0,
    },
    "commission_chro": {},
    "avax_gas": 0.0,
    "pve_game": {},
}


class WyndblastLifetimeGameStats:
    def __init__(
        self,
        user: str,
        address: str,
        commission_address: str,
        token: str,
        db_str: str = STATS_DB,
    ) -> None:
        self.db_str = db_str  # must come first

        self.alias = user
        self.address = address
        self._insert_user(user, commission_address, token)
        self._add_dailies_wallet()
        self._add_pve_wallet()
        self.user_id = None

        with ManagedSession(self.db_str) as db:
            user = db.query(WyndblastUser).filter(WyndblastUser.user == self.alias).first()
            assert user is not None, f"User {self.alias} not in DB!"
            self.user_id = user.id

    @contextmanager
    def user(self) -> T.Iterator[WyndblastUser]:
        with ManagedSession(self.db_str) as db:
            user = db.query(WyndblastUser).filter(WyndblastUser.user == self.alias).first()
            assert user is not None, f"User {self.alias} not in DB!"

            yield user

            try:
                db.add(user)
            except:
                logger.print_fail("Failed to store db item!")

    @contextmanager
    def pve(self) -> T.Iterator[Pve]:
        with ManagedSession(self.db_str) as db:
            pve = (
                db.query(Pve)
                .filter(Pve.user_id == self.user_id)
                .filter(Pve.address == self.address)
                .first()
            )
            yield pve

            try:
                db.add(pve)
            except:
                logger.print_fail("Failed to store db item!")

    @contextmanager
    def daily(self) -> T.Iterator[DailyActivities]:
        with ManagedSession(self.db_str) as db:
            daily = (
                db.query(DailyActivities)
                .filter(DailyActivities.user_id == self.user_id)
                .filter(DailyActivities.address == self.address)
                .first()
            )
            yield daily

            try:
                db.add(daily)
            except:
                logger.print_fail("Failed to store db item!")

    @contextmanager
    def commission(self, address: str) -> T.Iterator[Commission]:
        with ManagedSession(self.db_str) as db:
            commission = (
                db.query(Commission)
                .filter(Commission.user_id == self.user_id)
                .filter(Commission.address == address)
                .first()
            )
            assert commission is not None, f"{address} not in commission DB!"

            yield commission

            try:
                db.add(commission)
            except:
                logger.print_fail("Failed to store db item!")

    @contextmanager
    def winloss(self, stage: int) -> T.Iterator[WinLoss]:
        with ManagedSession(self.db_str) as db:
            winloss = (
                db.query(WinLoss)
                .filter(WyndblastUser.user == self.alias)
                .join(WyndblastUser.daily_activity_stats)
                .filter(DailyActivities.address == self.address)
                .join(DailyActivities.stages)
                .filter(WinLoss.stage == stage)
                .first()
            )

            assert winloss is not None, f"{stage} not in winloss DB!"

            yield winloss

            try:
                db.add(winloss)
            except:
                logger.print_fail("Failed to store db item!")

    def add_stage(self, level: str) -> None:
        with self.pve() as pve:
            pve_id = pve.id

        with ManagedSession(self.db_str) as db:
            level = Level(pve_id=pve_id, level=level)
            try:
                db.add(level)
            except:
                logger.print_fail("Failed to store stage in db!")

    def _insert_user(self, username: str, commission_address: str, token: str) -> None:
        with ManagedSession(self.db_str) as db:
            user = db.query(WyndblastUser).filter(WyndblastUser.user == username).first()

            if user is not None:
                logger.print_warn(f"{username} already in the database, not creating new user")
                return

            user = WyndblastUser(user=username)

            try:
                logger.print_normal(f"Adding {username} to database...")
                db.add(user)
            except:
                logger.print_fail(f"Failed to add db entry for {username}")

            user = db.query(WyndblastUser).filter(WyndblastUser.user == username).first()

            commission = Commission(address=commission_address, token=token, user_id=user.id)

            try:
                logger.print_normal(
                    f"Adding {token} commission to {commission_address} to database..."
                )
                db.add(commission)
            except:
                logger.print_fail(f"Failed to add commission entry for {commission_address}")

    def _add_dailies_wallet(self) -> None:
        with ManagedSession(self.db_str) as db:
            user = db.query(WyndblastUser).filter(WyndblastUser.user == self.alias).first()

            if user is None:
                logger.print_warn(f"{self.alias} not in the database")
                return

            daily_activity_stats = (
                db.query(DailyActivities)
                .filter(DailyActivities.user_id == user.id)
                .filter(DailyActivities.address == self.address)
                .first()
            )

            if daily_activity_stats is not None:
                logger.print_warn(f"{self.alias} {self.address} dailies already in db")
                return

            daily_activity_stats = DailyActivities(address=self.address, user_id=user.id)
            try:
                db.add(daily_activity_stats)
            except:
                logger.print_fail(f"Failed to create daily activity")
                return

            daily = (
                db.query(DailyActivities).filter(DailyActivities.address == self.address).first()
            )

            stages = []
            for stage in range(1, 4):
                stages.append(WinLoss(stage=stage, daily_activities_id=daily.id))

            estones = ElementalStones(daily_activities_id=daily.id)

            try:
                logger.print_normal(f"Adding {self.address} to daily activity database...")
                db.add(estones)
                for stage in stages:
                    db.add(stage)
            except:
                logger.print_fail(f"Failed to add daily activity db entry for {self.address}")

    def _add_pve_wallet(self) -> None:
        with ManagedSession(self.db_str) as db:
            user = db.query(WyndblastUser).filter(WyndblastUser.user == self.alias).first()

            if user is None:
                logger.print_warn(f"{self.alias} not in the database")
                return

            pve_stats = (
                db.query(Pve)
                .filter(Pve.user_id == user.id)
                .filter(Pve.address == self.address)
                .first()
            )

            if pve_stats is not None:
                logger.print_warn(f"{self.alias} {self.address} pve already in db")
                return

            pve_stats = Pve(address=self.address, user_id=user.id)

            try:
                logger.print_normal(f"Adding {self.address} to pve database...")
                db.add(pve_stats)
            except:
                logger.print_fail(f"Failed to add pve db entry for {self.address}")
