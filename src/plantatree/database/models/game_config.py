from marshmallow import Schema, fields, post_load
from sqlalchemy import types, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.schema import Column
from sqlalchemy.sql import func

from database.connect import AccountBase
from database.models.game_config import GameConfig


class PatGameConfig(AccountBase):  # type: ignore
    __tablename__ = "PatGameConfig"
    __mapper_args__ = {"polymorphic_identity": "PatGameConfig"}

    id = Column(types.Integer, ForeignKey("GameConfig.id"), primary_key=True)
    name = Column(types.String(40), nullable=False)
    time_between_plants = Column(types.Float, nullable=False, default=60.0 * 60.0 * 24)


class PatGameConfigSchema(Schema):  # type: ignore
    id = fields.Int()
    name = fields.Str()
    time_between_plants = fields.Float()

    @post_load
    def make_object(self, data, **kwargs):
        return PatGameConfig(**data)
