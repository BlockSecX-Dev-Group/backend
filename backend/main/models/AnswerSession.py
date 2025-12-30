from main.models.database import db
from datetime import datetime, timedelta
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

class AnswerSession(db.Model):
    __tablename__ = 'answer_session'  # 答题会话表
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='会话ID')
    session_id = db.Column(db.String(64), unique=True, nullable=False, comment='唯一会话标识（UUID）')
    user_address = db.Column(db.String(255), nullable=False, comment='用户地址')
    question_ids = db.Column(db.Text, nullable=False, comment='本次答题的题目ID列表（JSON）')
    is_submitted = db.Column(db.Boolean, default=False, comment='是否已提交答案（防止重复）')
    is_expired = db.Column(db.Boolean, default=False, comment='是否已过期')
    created_at = db.Column(db.DateTime, default=datetime.now, comment='会话创建时间')
    expire_at = db.Column(db.DateTime, nullable=False, comment='会话过期时间（创建后20分钟）')
    submitted_at = db.Column(db.DateTime, nullable=True, comment='提交答案时间')

    # 索引
    __table_args__ = (
        db.Index('idx_user_session', 'user_address', 'session_id'),
        db.Index('idx_expire_at', 'expire_at'),  # 用于定时任务查询过期会话
    )

 
    def is_session_expired(self):
        return datetime.now() >= self.expire_at and not self.is_submitted