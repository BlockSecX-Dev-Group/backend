import os
import sys
from datetime import datetime, timezone

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from main.models.database import db


class PointQueryLog(db.Model):
    """积分查询审计日志表"""
    __tablename__ = 'point_query_log'
    __table_args__ = {'comment': '积分查询审计日志'}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='主键ID')
    user_address = db.Column(db.String(64), nullable=False, index=True, comment='用户钱包地址')
    query_points = db.Column(db.Integer, nullable=False, comment='查询时的积分值')
    query_source = db.Column(db.String(64), nullable=False, comment='查询来源(api/sign_in/answer等)')
    client_ip = db.Column(db.String(64), nullable=True, comment='客户端IP')
    user_agent = db.Column(db.String(512), nullable=True, comment='用户代理')
    query_time = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, comment='查询时间')

    def to_dict(self):
        return {
            "id": self.id,
            "user_address": self.user_address,
            "query_points": self.query_points,
            "query_source": self.query_source,
            "client_ip": self.client_ip,
            "user_agent": self.user_agent,
            "query_time": self.query_time.strftime("%Y-%m-%d %H:%M:%S") if self.query_time else ""
        }
