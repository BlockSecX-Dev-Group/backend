# -*- coding: utf-8 -*-
"""
@author yumu
@version 1.0.0
"""
import os
import sys
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from main.models.database import db


class ErrorLog(db.Model):
    """
    错误日志模型
    """
    __tablename__ = 'error_log'
    error_log_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    error_event = db.Column(db.Text, nullable=True)
    error_time = db.Column(db.TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)
