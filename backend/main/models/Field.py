
import os
import sys
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from main.models.database import db


class Field(db.Model):
    __tablename__ = 'fields'
    __table_args__ = {'comment': '靶场信息记录表'}

    id = db.Column(db.Integer,primary_key=True, autoincrement=True, comment='记录id')
    field_name = db.Column(db.String(255), nullable=True, comment='靶场名字')
    cost = db.Column(db.Float,nullable=True, comment='开启靶场的开销/靶场难度/价值')
    description = db.Column(db.Text, nullable=True, comment='靶场描述')
    docker_name = db.Column(db.String(255), nullable=True, comment='靶场使用的docker镜像名称')
    container_port = db.Column(db.Integer, nullable=True, default=80, comment='容器内部服务端口')
