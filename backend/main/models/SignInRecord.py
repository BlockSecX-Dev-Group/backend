import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from datetime import datetime, timezone
from main.models.database import db

class SignInRecord(db.Model):
    __tablename__ = 'sign_in_records'  
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='主键ID')
    user_address = db.Column(db.String(64), nullable=False, comment='用户钱包地址')

    sign_in_time = db.Column(db.DateTime, 
                             default=lambda: datetime.now(timezone.utc), 
                             nullable=False, 
                             comment='签到时间（UTC）')
    reward_points = db.Column(db.Integer, default=10, nullable=False, comment='签到奖励积分')

    sign_in_date = db.Column(db.Date, 
                             nullable=False, 
                             comment='签到日期（用于防重复）')


    __table_args__ = (
        db.UniqueConstraint('user_address', 'sign_in_date', name='uk_user_sign_date'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'}  
    )

