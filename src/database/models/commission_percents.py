from marshmallow import Schema, fields, post_load
from sqlalchemy import types, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.schema import Column
from sqlalchemy.sql import func

from database.connect import Base


class CommissionPercents(Base):  # type: ignore
    __tablename__ = "CommissionPercents"

    id = Column(types.Integer, primary_key=True)
    address = Column(types.String(42), nullable=False)
    percent = Column(types.Float, nullable=False, default=10.0)
    wallet_id = Column(types.String, ForeignKey("Wallet.address"))
    created_at = Column(types.DateTime(timezone=True), server_default=func.now())


class CommissionPercentsSchema(Schema):  # type: ignore
    id = fields.Int()
    address = fields.Str()
    percent = fields.Float()
    wallet_id = fields.Str()
    created_at = fields.DateTime()

    @post_load
    def make_object(self, data, **kwargs):
        return CommissionPercents(**data)
