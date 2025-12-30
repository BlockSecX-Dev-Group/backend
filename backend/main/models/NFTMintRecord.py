import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from datetime import datetime, timezone
from main.models.database import db


class NFTMintRecord(db.Model):
    """NFT 铸造记录表 - 记录用户领取签到 NFT 的情况"""
    __tablename__ = 'nft_mint_records'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='主键ID')
    user_address = db.Column(db.String(64), nullable=False, index=True, comment='用户钱包地址')

    # 签名参数（用于前端调用合约）
    signature = db.Column(db.String(256), nullable=False, comment='后端生成的签名')
    nonce = db.Column(db.String(64), nullable=False, default="0")
    token_uri = db.Column(db.String(512), nullable=False, comment='NFT 元数据 URI')
    expire_time = db.Column(db.BigInteger, nullable=False, comment='签名过期时间戳')

    # 领取时的签到天数快照
    sign_in_days_snapshot = db.Column(db.Integer, nullable=False, comment='领取时的累计签到天数')

    # 状态追踪
    mint_status = db.Column(db.String(20), default='pending', nullable=False,
                            comment='铸造状态: pending(待铸造), minted(已铸造), expired(已过期)')
    tx_hash = db.Column(db.String(66), nullable=True, comment='链上交易哈希（铸造成功后填入）')

    created_at = db.Column(db.DateTime,
                           default=lambda: datetime.now(timezone.utc),
                           nullable=False,
                           comment='记录创建时间')
    minted_at = db.Column(db.DateTime, nullable=True, comment='实际铸造时间')

    __table_args__ = (
        db.Index('idx_user_minted', 'user_address', 'mint_status'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'}
    )
