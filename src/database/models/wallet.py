from marshmallow import Schema, fields, post_load
from sqlalchemy import types, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.schema import Column
from sqlalchemy.sql import func

from database.connect import Base
from database.models.commission_percents import CommissionPercentsSchema
from database.models.game_config import GameConfigSchema


class Wallet(Base):  # type: ignore
    __tablename__ = "Wallet"

    address = Column(types.String(42), primary_key=True)
    private_key = Column(types.String(128), nullable=False)
    commission_percents = relationship("CommissionPercents", backref="Wallet")
    game_configs = relationship("GameConfig", backref="Wallet")
    account_id = Column(types.String, ForeignKey("Account.owner"))
    created_at = Column(types.DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Wallet {self.address}:{self.account_id} {len(self.game_configs)} games>"


class WalletSchema(Schema):  # type: ignore
    address = fields.Str()
    private_key = fields.Str()
    commission_percents = fields.List(fields.Nested(CommissionPercentsSchema))
    game_configs = fields.List(fields.Nested(GameConfigSchema))
    account_id = fields.Str()
    created_at = fields.DateTime()

    @post_load
    def make_object(self, data, **kwargs):
        return Wallet(**data)
