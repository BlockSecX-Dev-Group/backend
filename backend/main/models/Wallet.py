

import os
import sys
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from main.models.database import db

# 充值收款钱包表
class Wallet(db.Model):
    __tablename__ = 'wallets'  # 指定表名
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='主键，自增 ID')
    address = db.Column(db.String(255), nullable=True, comment='钱包地址（Arb One 地址）')
    private_key = db.Column(db.String(255), nullable=True, comment='加密后的私钥')
    created_at = db.Column(db.TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow,  comment='创建时间')
