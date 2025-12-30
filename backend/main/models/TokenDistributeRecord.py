import os
import sys
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from main.models.database import db


class TokenDistributeRecord(db.Model):
    __tablename__ = 'token_distribute_records'
    __table_args__ = {
        'comment': '代币发放记录表（用户token从web2到web3）'
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='记录id')
    user_address = db.Column(db.String(255), nullable=True, comment='用户地址')
    distribute_time = db.Column(db.TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow, comment='时间')
    token_amount = db.Column(db.Float, nullable=True, comment='代币数量')