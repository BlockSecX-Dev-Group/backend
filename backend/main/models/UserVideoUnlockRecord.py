# -*- coding: utf-8 -*-
"""用户视频解锁记录模型"""
from main.models.database import db
from datetime import datetime, timezone

class UserVideoUnlockRecord(db.Model):
    __tablename__ = 'user_video_unlock_record'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_address = db.Column(db.String(64), nullable=False, comment='用户地址')
    video_id = db.Column(db.String(255), nullable=False, comment='视频ID')
    sequence_num = db.Column(db.Integer, nullable=False, comment='视频顺序号')
    is_unlocked = db.Column(db.Boolean, default=False, comment='是否解锁')
    unlock_time = db.Column(db.DateTime, nullable=True, comment='解锁时间')
    last_watch_time = db.Column(db.DateTime, nullable=True, comment='最后观看时间')
    is_watched = db.Column(db.Boolean, default=False, comment='是否观看完成')
    watch_complete_time = db.Column(db.DateTime, nullable=True, comment='观看完成时间')
    create_time = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), comment='创建时间')
    update_time = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        comment='更新时间'
    )
    
    __table_args__ = (
        db.UniqueConstraint('user_address', 'video_id', name='uk_user_video'),
        db.Index('idx_user_sequence', 'user_address', 'sequence_num')
    )