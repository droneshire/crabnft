from marshmallow import Schema, fields, post_load
from sqlalchemy import types, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.schema import Column
from sqlalchemy.sql import func

from database.connect import Base


class Commission(Base):  # type: ignore
    __tablename__ = "Commission"

    id = Column(types.Integer, primary_key=True)
    address = Column(types.String(80), nullable=False)
    token = Column(types.String(80), nullable=False, default="avax")
    amount = Column(types.Float, nullable=False, default=0.0)
    user_id = Column(types.Integer, ForeignKey("WyndblastUser.id"))

    def __repr__(self):
        return f"<Commission {self.address} [{self.token}]>"


class CommissionSchema(Schema):  # type: ignore
    id = fields.Int()
    address = fields.Str()
    token = fields.Str()
    amount = fields.Float()
    user_id = fields.Int()

    @post_load
    def make_object(self, data, **kwargs):
        return Commission(**data)
