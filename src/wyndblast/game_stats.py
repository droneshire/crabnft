import time
import typing as T

from contextlib import contextmanager
from sqlalchemy.sql import func

from database.connect import ManagedSession
from utils import logger
from wyndblast.database.daily_activities import (
    DailyActivities,
    ElementalStones,
    WinLoss,
    WinLossSchema,
)
from wyndblast.database.commission import Commission
from wyndblast.database.pve import Pve
from wyndblast.database.user import WyndblastUser


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
    def __init__(self, user: str, address: str, commission_address: str, token: str) -> None:
        self.user = user
        self._insert_user(user, commission_addr, token)
        self._add_dailies_wallet(user, address)
        self._add_pve_wallet(user, address)

    @contextmanager
    def user(self) -> Iterator[WyndblastUser]:
        with ManagedSession() as db:
            user = db.query(WyndblastUser).filter(WyndblastUser.user == self.user).first()
            assert user is not None, f"User {self.user} not in DB!"

            yield user

            try:
                db.add(user)
            except:
                logger.print_fail("Failed to store db item!")

    @contextmanager
    def commission(self, address: str) -> Iterator[Commission]:
        with ManagedSession() as db:
            commission = (
                db.query(Commission).filter(Commission.daily_activities_id == address).first()
            )
            assert commission is not None, f"{address} not in commission DB!"

            yield commission

            try:
                db.add(commission)
            except:
                logger.print_fail("Failed to store db item!")

    def winloss(self, stage: int) -> Iterator[WinLoss]:
        with ManagedSession() as db:
            user = db.query(WyndblastUser).filter(WyndblastUser.user == self.user).first()
            assert user is not None, f"User {self.user} not in DB!"

            winloss = (
                db.query(WinLoss)
                .filter(WinLoss.daily_activities_id == user.daily_activity_stats.id)
                .filter(WinLoss.stage == stage)
                .first()
            )
            assert winloss is not None, f"{stage} not in winloss DB!"

            yield winloss

            try:
                db.add(winloss)
            except:
                logger.print_fail("Failed to store db item!")

    def get_win_loss(self) -> WinLossSchema:
        totals = WinLoss(stage=0)
        with ManagedSession() as db:
            user = db.query(WyndblastUser).filter(WyndblastUser.user == user).first()
            for stage in user.daily_activity_stats.stages:
                totals.wins += stage.wins
                totals.losses += stage.losses

        return WinLossSchema().load(totals)

    def _insert_user(self, user: str, commission_address: str, token: str) -> None:
        with ManagedSession() as db:
            user = db.query(WyndblastUser).filter(WyndblastUser.user == user).first()

        if user is not None:
            log.print_warn(f"{user} already in the database, not creating new user")
            return

        user = WyndblastUser(user=user)

        with ManagedSession() as db:
            try:
                log.print_normal(f"Adding {user} to database...")
                db.add(user)
            except:
                log.print_fail(f"Failed to add db entry for {user}")

        commission = Commission(address=commission_address, token=token, user_id=user.id)

        with ManagedSession() as db:
            try:
                log.print_normal(
                    f"Adding {token} commission to {commission_address} to database..."
                )
                db.add(commission)
            except:
                log.print_fail(f"Failed to add commission entry for {commission_address}")

    def _add_dailies_wallet(self, user: str, address: str) -> None:
        with ManagedSession() as db:
            user = db.query(WyndblastUser).filter(WyndblastUser.user == user).first()

        if user is None:
            log.print_warn(f"{user} not in the database")
            return

        daily_activity_stats = DailyActivities(address=address, user_id=user.id)
        stages = []
        for stage in range(1, 4):
            stages.append(WinLoss(stage=stage, daily_activities_id=daily_activity_stats.id))

        estones = ElementalStones(daily_activities_id=daily_activity_stats.id)

        with ManagedSession() as db:
            try:
                log.print_normal(f"Adding {address} to daily activity database...")
                db.add(daily_activity_stats)
                db.add(estones)
                for stage in stages:
                    db.add(stage)
            except:
                log.print_fail(f"Failed to add daily activity db entry for {address}")

    def _add_pve_wallet(self, user: str, address: str) -> None:
        with ManagedSession() as db:
            user = db.query(WyndblastUser).filter(WyndblastUser.user == user).first()

        if user is None:
            log.print_warn(f"{user} not in the database")
            return

        pve_stats = Pve(address=address, user_id=user.id)

        with ManagedSession() as db:
            try:
                log.print_normal(f"Adding {address} to pve database...")
                db.add(pve_stats)
            except:
                log.print_fail(f"Failed to add pve db entry for {address}")
