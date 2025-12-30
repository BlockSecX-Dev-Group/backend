import os
import sys
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from main.models.database import db

class TargetFieldOpenRecord(db.Model):
    __tablename__ = 'target_field_open_records'
    __table_args__ = {
        'comment': '靶场开启记录表'
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='记录id')
    field_id = db.Column(db.String(255), nullable=True, comment='靶场id/容器id')
    field_name = db.Column(db.String(255), nullable=True, comment='靶场名字')
    user_address = db.Column(db.String(255), nullable=True, comment='用户地址')
    flag = db.Column(db.String(255), nullable=True, comment='题目flag')
    host_port = db.Column(db.Integer, nullable=True, comment='宿主机映射端口')
    start_time = db.Column(db.TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow, comment='靶场开启的时间')
    status = db.Column(db.Enum('running', 'stop'), server_default='running', nullable=True, comment='靶场运行状态')
