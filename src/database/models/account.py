from marshmallow import Schema, fields, post_load
from sqlalchemy import types
from sqlalchemy.orm import relationship
from sqlalchemy.schema import Column
from sqlalchemy.sql import func

from database.connect import Base
from database.models.wallet import WalletSchema


class Account(Base):  # type: ignore
    __tablename__ = "Account"

    owner = Column(types.String(80), primary_key=True)
    email = Column(types.String(80), unique=True, nullable=False)
    discord_handle = Column(types.String(80), unique=True, nullable=False)
    wallets = relationship("Wallet", backref="Account")
    created_at = Column(types.DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Account {self.owner}:{self.discord_handle}, {self.email} {[w.address for w in self.wallets]}>"


class AccountSchema(Schema):  # type: ignore
    owner = fields.Str()
    email = fields.Str()
    discord_handle = fields.Str()
    wallets = fields.List(fields.Nested(WalletSchema))
    created_at = fields.DateTime()

    @post_load
    def make_object(self, data, **kwargs):
        return Account(**data)
