import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from datetime import datetime
from main.models.database import db

'''定义视频解锁顺序'''

class VideoSequence(db.Model):
    __tablename__ = 'video_sequence'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='主键')
    video_id = db.Column(db.String(64), unique=True, nullable=False, comment='视频ID')
    sequence_num = db.Column(db.Integer, nullable=False, comment='解锁顺序（1/2/3...）')
    is_active = db.Column(db.Boolean, default=True, comment='是否启用')
    create_time = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间')

    # 按顺序查询视频
    @classmethod
    def get_video_by_sequence(cls, num):
        return cls.query.filter_by(sequence_num=num, is_active=True).first()
    
    # 获取视频的顺序号
    @classmethod
    def get_sequence_by_video_id(cls, video_id):
        record = cls.query.filter_by(video_id=video_id, is_active=True).first()
        return record.sequence_num if record else None
    
    # 获取所有视频的顺序列表
    @classmethod
    def get_all_sequence(cls):
        return cls.query.filter_by(is_active=True).order_by(cls.sequence_num).all()