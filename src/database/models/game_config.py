from marshmallow import Schema, fields, post_load
from sqlalchemy import types, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.schema import Column
from sqlalchemy.sql import func

from database.connect import AccountBase


class GameConfig(AccountBase):  # type: ignore
    __tablename__ = "GameConfig"

    id = Column(types.Integer, primary_key=True)
    name = Column(types.String(40), nullable=False)
    discriminator = Column(types.String(40), nullable=False)
    email_updates = Column(types.Boolean, nullable=False, default=True)
    wallet_id = Column(types.String, ForeignKey("Wallet.address"))
    created_at = Column(types.DateTime(timezone=True), server_default=func.now())

    __mapper_args__ = {"polymorphic_on": discriminator, "polymorphic_identity": "GameConfig"}


class GameConfigSchema(Schema):  # type: ignore
    id = fields.Int()
    discriminator = fields.Str()
    email_updates = fields.Bool()
    wallet_id = fields.Str()
    created_at = fields.DateTime()

    @post_load
    def make_object(self, data, **kwargs):
        return GameConfig(**data)
