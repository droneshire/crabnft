from marshmallow import Schema, fields, post_load
from sqlalchemy import types, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.schema import Column
from sqlalchemy.sql import func


from database.connect import GameBase


class ElementalStones(GameBase):  # type: ignore
    __tablename__ = "ElementalStones"

    id = Column(types.Integer, primary_key=True)
    daily_activities_id = Column(types.Integer, ForeignKey("DailyActivities.id"))
    fire = Column(types.Integer, nullable=False, default=0)
    wind = Column(types.Integer, nullable=False, default=0)
    earth = Column(types.Integer, nullable=False, default=0)
    light = Column(types.Integer, nullable=False, default=0)
    darkness = Column(types.Integer, nullable=False, default=0)
    water = Column(types.Integer, nullable=False, default=0)

    def __repr__(self):
        return f"<Elemental Stones {self.id}>"


class ElementalStonesSchema(Schema):  # type: ignore
    id = fields.Int()
    daily_activities_id = fields.Int()
    fire = fields.Int()
    wind = fields.Int()
    earth = fields.Int()
    light = fields.Int()
    darkness = fields.Int()
    water = fields.Int()

    @post_load
    def make_object(self, data, **kwargs):
        return ElementalStones(**data)


class WinLoss(GameBase):  # type: ignore
    __tablename__ = "WinLoss"

    id = Column(types.Integer, primary_key=True)
    stage = Column(types.Integer, nullable=False)
    wins = Column(types.Integer, nullable=False, default=0)
    losses = Column(types.Integer, nullable=False, default=0)
    daily_activities_id = Column(types.Integer, ForeignKey("DailyActivities.id"))

    def __repr__(self):
        return f"<Win Loss {self.id}>"


class WinLossSchema(Schema):  # type: ignore
    id = fields.Int()
    stage = fields.Int()
    daily_activities_id = fields.Int()
    wins = fields.Int()
    losses = fields.Int()

    @post_load
    def make_object(self, data, **kwargs):
        return WinLoss(**data)


class DailyActivities(GameBase):  # type: ignore
    __tablename__ = "DailyActivities"

    id = Column(types.Integer, primary_key=True)
    address = Column(types.String(80), unique=True, nullable=False)
    elemental_stones = relationship("ElementalStones", backref="DailyActivities")
    stages = relationship("WinLoss", backref="win_loss")
    user_id = Column(types.Integer, ForeignKey("WyndblastUser.id"))
    created_at = Column(types.DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Daily Activities {self.address}>"


class DailyActivitiesSchema(Schema):  # type: ignore
    id = fields.Int()
    address = fields.Str()
    elemental_stones = fields.Nested(ElementalStonesSchema)
    stages = fields.List(fields.Nested(WinLossSchema))
    user_id = fields.Int()
    created_at = fields.DateTime()

    @post_load
    def make_object(self, data, **kwargs):
        return DailyActivities(**data)
