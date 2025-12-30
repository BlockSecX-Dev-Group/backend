from datetime import datetime
from main.models.database import db

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

class AnswerChallengeRecord(db.Model):
    __tablename__ = 'answer_challenge_records'  # 新增表：答题记录
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='主键ID')
    user_address = db.Column(db.String(64), nullable=False, comment='用户钱包地址')
    challenge_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, comment='答题时间')
    cost_points = db.Column(db.Integer, default=10, nullable=False, comment='答题消耗积分')
    correct_count = db.Column(db.Integer, nullable=False, comment='答对题目数')
    reward_points = db.Column(db.Integer, nullable=False, comment='答题奖励积分')

    # 索引优化
    __table_args__ = (
        db.Index('idx_user_address', 'user_address'),
        db.Index('idx_challenge_time', 'challenge_time'),
    )