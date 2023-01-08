from marshmallow import Schema, fields, post_load
from sqlalchemy import types, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.schema import Column
from sqlalchemy.sql import func

from database.connect import Base
from database.models.game_config import GameConfig


class WyndblastGameConfig(GameConfig):  # type: ignore
    __tablename__ = "WyndblastGameConfig"
    __mapper_args__ = {"polymorphic_identity": "WyndblastGameConfig"}

    id = Column(types.Integer, ForeignKey("GameConfig.id"), primary_key=True)
    name = Column(types.String(40), nullable=False)


class WyndblastGameConfigSchema(Schema):  # type: ignore
    id = fields.Int()
    name = fields.Str()

    @post_load
    def make_object(self, data, **kwargs):
        return WyndblastGameConfig(**data)
