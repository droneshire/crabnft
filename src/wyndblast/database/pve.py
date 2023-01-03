from marshmallow import Schema, fields, post_load
from sqlalchemy import types, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.schema import Column
from sqlalchemy.sql import func

from database.connect import Base


class Level(Base):  # type: ignore
    __tablename__ = "Level"

    id = Column(types.Integer, primary_key=True)
    level = Column(types.String(80), unique=True, nullable=False)
    pve_id = Column(types.Integer, ForeignKey("Pve.id"))

    def __repr__(self):
        return f"<Level {self.level}>"


class LevelSchema(Schema):  # type: ignore
    id = fields.Int()
    level = fields.Str()
    pve_id = fields.Int()

    @post_load
    def make_object(self, data, **kwargs):
        return Level(**data)


class Pve(Base):  # type: ignore
    __tablename__ = "Pve"

    id = Column(types.Integer, primary_key=True)
    address = Column(types.String(80), unique=True, nullable=False)
    levels_completed = relationship("Level", backref="pve")
    account_exp = Column(types.Integer, nullable=False, default=0)
    unclaimed_chro = Column(types.Float, nullable=False, default=0.0)
    claimed_chro = Column(types.Float, nullable=False, default=0.0)
    user_id = Column(types.Integer, ForeignKey("WyndblastUser.id"))
    created_at = Column(types.DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Pve {self.address}>"


class PveSchema(Schema):  # type: ignore
    id = fields.Int()
    address = fields.Str()
    levels_completed = fields.List(fields.Nested(LevelSchema))
    account_exp = fields.Int()
    unclaimed_chro = fields.Float()
    claimed_chro = fields.Float()
    user_id = fields.Int()
    created_at = fields.DateTime()

    @post_load
    def make_object(self, data, **kwargs):
        return Pve(**data)
