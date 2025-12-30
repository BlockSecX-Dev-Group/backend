import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from main.models.database import db

class UserData(db.Model):
    __tablename__ = 'user_data'
    __table_args__ = {
        'comment': '用户数据表'
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='记录id')
    user_address= db.Column(db.String(255), nullable=True, comment='用户地址')
    token_balance = db.Column(db.Float, nullable=True, comment='token余额')

