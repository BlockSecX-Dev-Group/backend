


import os
import sys
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from main.models.database import db

class PaymentOrder(db.Model):
    __tablename__ = 'payment_orders'  # 指定表名
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='主键，自增 ID')
    user_address = db.Column(db.String(255), nullable=True, comment='用户地址')
    receive_address = db.Column(db.String(255), nullable=True, comment='收款地址')
    recharge_amount = db.Column(db.Float, nullable=True, comment='充值金额（USDT）')
    order_time = db.Column(db.TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow, comment='下单时间')
    paid_status = db.Column(db.Boolean, nullable=True, comment='支付状态')  # 用 Boolean 替代 TINYINT(1)
    tx_hash = db.Column(db.String(255), nullable=True, comment='交易哈希')
