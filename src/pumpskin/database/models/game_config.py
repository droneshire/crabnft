from marshmallow import Schema, fields, post_load
from sqlalchemy import types, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.schema import Column
from sqlalchemy.sql import func

from database.connect import AccountBase
from database.models.game_config import GameConfig


class SpecialPumpskins(AccountBase):  # type: ignore
    __tablename__ = "SpecialPumpskins"

    id = Column(types.Integer, primary_key=True)
    pumpkin_id = Column(types.Integer, nullable=False)
    max_level = Column(types.Integer, nullable=False, default=100)
    game_config_id = Column(types.Integer, ForeignKey("GameConfig.id"))


class SpecialPumpskinsSchema(Schema):  # type: ignore
    id = fields.Int()
    pumpkin_id = fields.Int()
    max_level = fields.Int()
    game_config_id = fields.Int()

    @post_load
    def make_object(self, data, **kwargs):
        return SpecialPumpskins(**data)


class PumpskinsGameConfig(AccountBase):  # type: ignore
    __tablename__ = "PumpskinsGameConfig"
    __mapper_args__ = {"polymorphic_identity": "PumpskinsGameConfig"}

    id = Column(types.Integer, ForeignKey("GameConfig.id"), primary_key=True)
    name = Column(types.String(40), nullable=False)

    potn_claim_multiplier = Column(types.Float, nullable=False, default=1.0)
    ppie_claim_multiplier = Column(types.Float, nullable=False, default=1.0)
    ppie_stake_multiplier = Column(types.Float, nullable=False, default=1.0)

    max_level = Column(types.Integer, nullable=False, default=100)

    special_pumps = relationship("SpecialPumpskins", backref="GameConfig")
    only_special_pumps = Column(types.Boolean, nullable=False, default=False)

    all_available_ppie_balances = Column(types.Boolean, nullable=False, default=True)
    all_available_potn_balances = Column(types.Boolean, nullable=False, default=True)

    rewards_claim_multiplier = Column(types.Float, nullable=False, default=10.0)

    percent_ppie_profit = Column(types.Float, nullable=False, default=0.0)
    percent_ppie_hold = Column(types.Float, nullable=False, default=0.0)
    percent_ppie_levelling = Column(types.Float, nullable=False, default=100.0)
    percent_ppie_lp = Column(types.Float, nullable=False, default=0.0)

    percent_potn_profit = Column(types.Float, nullable=False, default=0.0)
    percent_potn_hold = Column(types.Float, nullable=False, default=0.0)
    percent_potn_levelling = Column(types.Float, nullable=False, default=100.0)
    percent_potn_lp = Column(types.Float, nullable=False, default=0.0)

    min_avax_to_profit = Column(types.Float, nullable=False, default=0.10)


class PumpskinsGameConfigSchema(Schema):  # type: ignore
    id = fields.Int()
    name = fields.Str()

    potn_claim_multiplier = fields.Float()
    ppie_claim_multiplier = fields.Float()
    ppie_stake_multiplier = fields.Float()
    max_level = fields.Float()
    special_pumps = fields.List(fields.Nested(SpecialPumpskinsSchema))
    only_special_pumps = fields.Bool()
    all_available_ppie_balances = fields.Bool()
    all_available_potn_balances = fields.Bool()
    rewards_claim_multiplier = fields.Float()
    percent_ppie_profit = fields.Float()
    percent_ppie_hold = fields.Float()
    percent_ppie_levelling = fields.Float()
    percent_ppie_lp = fields.Float()
    percent_potn_profit = fields.Float()
    percent_potn_hold = fields.Float()
    percent_potn_levelling = fields.Float()
    percent_potn_lp = fields.Float()
    min_avax_to_profit = fields.Float()

    @post_load
    def make_object(self, data, **kwargs):
        return PumpskinsGameConfig(**data)
