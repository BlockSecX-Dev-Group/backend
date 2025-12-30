import os
import sys
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from main.models.database import db


class LevelPassRecord(db.Model):
    __tablename__ = 'level_pass_records'
    __table_args__ = {
        'comment': '通关关卡记录'
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='记录id')
    field_id = db.Column(db.String(255), nullable=True, comment='靶场id')
    user_address = db.Column(db.String(255), nullable=True, comment='用户地址')
    reward_amount = db.Column(db.Float, nullable=True, comment='奖励数量')
    pass_time = db.Column(db.TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow, comment='通关时间')
