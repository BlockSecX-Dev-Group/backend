# -*- coding: utf-8 -*-
"""用户视频观看进度记录模型"""
# 仅保留必要导入（删除重复+多余的路径操作）
from main.models.database import db
from datetime import datetime, timezone


class UserVideoWatchRecord(db.Model):
    __tablename__ = 'user_video_watch_record'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_address = db.Column(db.String(100), nullable=False)  # 用户地址
    video_id = db.Column(db.String(50), nullable=False)       # 视频ID
    watch_record_id = db.Column(db.String(100), nullable=False)  # 单次播放唯一ID
    first_client_ts = db.Column(db.Integer, default=0)        # 首次上报客户端时间戳（秒）
    first_server_ts = db.Column(db.Integer, default=0)        # 首次上报服务器时间戳（秒）
    final_client_ts = db.Column(db.Integer, default=0)        # 最终上报客户端时间戳（秒）
    is_rewarded = db.Column(db.Boolean, default=False)        # 是否已发奖
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, onupdate=lambda: datetime.now(timezone.utc))

    # 联合唯一索引（避免重复记录）
    __table_args__ = (
        db.UniqueConstraint('user_address', 'video_id', 'watch_record_id', name='_user_video_watch_uc'),
    )