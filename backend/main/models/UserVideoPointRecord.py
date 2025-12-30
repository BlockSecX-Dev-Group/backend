from datetime import datetime
from main.models.database import db

class UserVideoPointRecord(db.Model):
    __tablename__ = 'user_video_point_record'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_address = db.Column(db.String(64), nullable=False, comment='用户钱包地址')
    video_id = db.Column(db.String(64), nullable=False, comment='视频ID')
    point_amount = db.Column(db.Integer, nullable=False, comment='发放积分数量')
    is_received = db.Column(db.Boolean, default=False, comment='是否已领取')
    receive_time = db.Column(db.DateTime, comment='领取时间')
    create_time = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('user_address', 'video_id', name='uk_user_video'),  # 唯一索引：同一用户同一视频仅能领一次
    )