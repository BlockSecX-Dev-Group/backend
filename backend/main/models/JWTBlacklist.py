

import os
import sys
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from main.models.database import db


class JWTBlacklist(db.Model):
    """
    失效JWT表模型
    """
    __tablename__ = 'jwt_blacklist'
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(2048), nullable=False)
    invalidated_at = db.Column(db.TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow,  comment='失效时间')
