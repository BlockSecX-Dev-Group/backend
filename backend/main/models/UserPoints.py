import os
import sys
from datetime import datetime,timezone
from main.models.database import db

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

class UserPoints(db.Model):
    __tablename__ = 'user_points'  
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='主键ID')
    user_address = db.Column(db.String(64), unique=True, nullable=False, comment='用户钱包地址')
    total_points = db.Column(db.Integer, default=0, nullable=False, comment='总积分')
    update_time = db.Column(db.DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc), comment='更新时间')
    create_time = db.Column(db.DateTime, default=datetime.now(timezone.utc), nullable=False, comment='创建时间')

    def to_dict(self):
        return {
            "user_address": self.user_address,
            "total_points": self.total_points,
            "update_time": self.update_time.strftime("%Y-%m-%d %H:%M:%S") if self.update_time else "",
            "create_time": self.create_time.strftime("%Y-%m-%d %H:%M:%S") if self.create_time else ""
        }

    def add_points(self, points):
        """增加积分"""
        if points <= 0:
            return False, "积分值必须大于0"
        self.total_points += points
        self.update_time = datetime.now(timezone.utc)
        db.session.commit()
        return True, self.total_points

    def deduct_points(self, points):
        """扣除积分"""
        if points <= 0:
            return False, "扣除积分必须大于0"
        if self.total_points < points:
            return False, "积分不足"
        self.total_points -= points
        self.update_time = datetime.now(timezone.utc)
        db.session.commit()
        return True, self.total_points