from marshmallow import Schema, fields, post_load
from sqlalchemy import types
from sqlalchemy.orm import relationship
from sqlalchemy.schema import Column
from sqlalchemy.sql import func

from database.connect import Base
from wyndblast.database.commission import CommissionSchema
from wyndblast.database.daily_activities import DailyActivitiesSchema
from wyndblast.database.pve import PveSchema


class WyndblastUser(Base):  # type: ignore
    __tablename__ = "WyndblastUser"

    id = Column(types.Integer, primary_key=True)
    user = Column(types.String(80), unique=True, nullable=False)
    chro = Column(types.Float, nullable=False, default=0.0)
    wams = Column(types.Float, nullable=False, default=0.0)
    gas_avax = Column(types.Float, nullable=False, default=0.0)
    commission = relationship("Commission", backref="WyndblastUser")
    daily_activity_stats = relationship("DailyActivities", backref="WyndblastUser")
    pve_stats = relationship("Pve", backref="WyndblastUser")
    created_at = Column(types.DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<User {self.user}:{self.id}>"


class WyndblastUserSchema(Schema):  # type: ignore
    id = fields.Int()
    user = fields.Str()
    chro = fields.Float()
    wams = fields.Float()
    gas_avax = fields.Float()
    commission = fields.List(fields.Nested(CommissionSchema))
    daily_activity_stats = fields.List(fields.Nested(DailyActivitiesSchema))
    pve_stats = fields.List(fields.Nested(PveSchema))
    created_at = fields.DateTime()

    @post_load
    def make_object(self, data, **kwargs):
        return WyndblastUser(**data)
