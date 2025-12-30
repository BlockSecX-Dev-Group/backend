
import datetime
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from main.models.database import db

class VideoInfo(db.Model):
    __tablename__ = 'video_info'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    video_id = db.Column(db.String(255), unique=True, nullable=False, comment='视频ID（文件名去扩展名）')
    video_name = db.Column(db.String(255), nullable=False, comment='视频名称（含中文）')
    video_path = db.Column(db.String(512), nullable=False, comment='视频路径（含中文）')
    video_duration = db.Column(db.Integer, default=0, comment='视频时长（秒）')
    trigger_progress = db.Column(db.Float, default=0.9, comment='触发积分进度（0.9=90%）')
    point_reward = db.Column(db.Integer, default=10, comment='奖励积分')
    is_active = db.Column(db.Boolean, default=True, comment='是否启用')
    create_time = db.Column(
        db.DateTime,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        comment='创建时间（UTC时区）'
    )

    def to_dict(self):
        return {
            'video_id': self.video_id,
            'video_name': self.video_name,
            'video_duration': self.video_duration,
            'point_reward': self.point_reward,
            'trigger_progress': self.trigger_progress,
            'sequence_num': getattr(self, 'sequence_num', None)
        }