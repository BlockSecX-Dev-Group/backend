import os
import time
import json
from web3 import Web3
from eth_account import Account
from eth_account.messages import encode_typed_data
from eth_utils import to_checksum_address
# from dotenv import load_dotenv  <-- 删掉了这行
from sqlalchemy import desc

from sqlalchemy import func
from main.managers.Config import Config
from main.models.NFTMintRecord import NFTMintRecord
from main.models.SignInRecord import SignInRecord
from main.models.database import db

# load_dotenv() <-- 删掉了这行

class NFTManager:
    _instance = None

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        # 1. 基础配置 (从 Config.json 读取公开信息)
        self.contract_address = to_checksum_address(Config.get_value('nft_contract_address'))
        self.rpc_url = Config.get_value('nft_rpc_url')
        
        # 处理 chain_id 可能为空或字符串的情况
        cid = Config.get_value('nft_chain_id')
        self.chain_id = int(cid) if cid else 56
        
        # === 核心 EIP-712 配置 ===
        self.eip712_name = "NFToken"  
        self.eip712_version = "1"
        self.fixed_uri = "ipfs://QmS4NWLBXYZQ8sQ1ycYPEh6riq3Y3Qdr35EtbB7VXFdzMR"

        # 2. 管理员私钥读取逻辑 (去除了 dotenv 依赖)
        # 优先读取系统环境变量 (适合 Docker/Systemd)
        # 如果没有，则读取 config.json (适合直接运行)
        priv_key_candidate = os.environ.get("NFT_MINTER_PRIVATE_KEY", "")
        
        if not priv_key_candidate:
            priv_key_candidate = Config.get_value('nft_minter_private_key')
            
        if not priv_key_candidate:
            print("⚠️ 警告: 未找到 NFT_MINTER_PRIVATE_KEY，请检查 config.json 或系统环境变量")
            self.relayer_private_key = ""
        else:
            self.relayer_private_key = priv_key_candidate.replace("0x", "")

        # 3. Web3 连接
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        
        # 只有当私钥存在时才加载账户，防止报错
        if self.relayer_private_key:
            self.relayer_account = Account.from_key(self.relayer_private_key)
        else:
            self.relayer_account = None
        
        # 4. 合约 ABI
        self.contract_abi = [
            {"inputs":[{"internalType":"address","name":"owner","type":"address"}],"name":"nonces","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
            {"inputs":[{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"nonce","type":"uint256"},{"internalType":"uint256","name":"deadline","type":"uint256"},{"internalType":"bytes","name":"sig","type":"bytes"}],"name":"sigMint","outputs":[],"stateMutability":"nonpayable","type":"function"}
        ]
        self.contract = self.w3.eth.contract(address=self.contract_address, abi=self.contract_abi)

    # 铸造资格：最低签到天数
    MIN_SIGN_IN_DAYS = 10

    def get_user_sign_in_days(self, user_address):
        """获取用户累计签到天数"""
        from sqlalchemy import distinct
        result = db.session.query(
            func.count(distinct(SignInRecord.sign_in_date))
        ).filter(
            SignInRecord.user_address == user_address
        ).scalar()
        return result or 0

    def check_mint_eligibility(self, user_address):
        """检查用户是否有资格铸造 NFT"""
        checksum_addr = to_checksum_address(user_address)

        # 检查累计签到天数
        sign_in_days = self.get_user_sign_in_days(checksum_addr)
        if sign_in_days < self.MIN_SIGN_IN_DAYS:
            return False, f"签到天数不足，需要 {self.MIN_SIGN_IN_DAYS} 天，当前 {sign_in_days} 天"

        return True, {"sign_in_days": sign_in_days}

    def get_mint_params(self, user_address):
        """接口1：为前端准备签名数据"""
        try:
            checksum_addr = to_checksum_address(user_address)

            # 0. 检查铸造资格
            eligible, result = self.check_mint_eligibility(checksum_addr)
            if not eligible:
                return False, result

            # 1. 实时查链上 Nonce
            nonce = self.contract.functions.nonces(checksum_addr).call()

            # 2. 设置过期时间 (1小时)
            deadline = int(time.time()) + 3600

            return True, {
                "to": checksum_addr,
                "nonce": nonce,
                "deadline": deadline,
                "uri": self.fixed_uri,
                "chain_id": self.chain_id,
                "verifying_contract": self.contract_address,
                "eip712_name": self.eip712_name,
                "eip712_version": self.eip712_version,
            }
        except Exception as e:
            return False, f"链上数据获取失败: {str(e)}"

    def verify_and_submit_mint(self, user_address, signature, nonce, deadline):
        """接口2：验证签名并由管理员上链"""
        if not self.relayer_account:
            return False, "服务端未配置管理员私钥"

        user_address = to_checksum_address(user_address)

        # 0. 再次检查铸造资格（防止绕过 get_mint_params 直接调用）
        eligible, result = self.check_mint_eligibility(user_address)
        if not eligible:
            return False, result

        # 1. 验证签名
        is_valid = self._verify_signature(user_address, int(nonce), int(deadline), signature)
        if not is_valid:
            return False, "签名验证失败：您不是该账户的所有者"

        # 2. 发起交易
        try:
            tx_hash = self._send_relayer_tx(user_address, int(nonce), int(deadline), signature)

            # 3. 存库
            sign_in_days = result.get("sign_in_days", 0)

            record = NFTMintRecord(
                user_address=user_address,
                signature=signature,
                nonce=str(nonce),
                token_uri=self.fixed_uri,
                expire_time=deadline,
                sign_in_days_snapshot=sign_in_days,
                mint_status='minted',
                tx_hash=tx_hash
            )
            db.session.add(record)
            db.session.commit()
            return True, tx_hash
        except Exception as e:
            db.session.rollback()
            return False, f"上链失败: {str(e)}"

    def _verify_signature(self, user_address, nonce, deadline, signature):
        try:
            types = {
                "EIP712Domain": [{"name": "name", "type": "string"},{"name": "version", "type": "string"},{"name": "chainId", "type": "uint256"},{"name": "verifyingContract", "type": "address"}],
                "Mint": [{"name": "to", "type": "address"},{"name": "uri", "type": "string"},{"name": "nonce", "type": "uint256"},{"name": "deadline", "type": "uint256"}]
            }
            domain = {"name": self.eip712_name, "version": self.eip712_version, "chainId": self.chain_id, "verifyingContract": self.contract_address}
            message = {"to": user_address, "uri": self.fixed_uri, "nonce": nonce, "deadline": deadline}
            full_payload = {"types": types, "primaryType": "Mint", "domain": domain, "message": message}
            
            recovered = Account.recover_message(encode_typed_data(full_message=full_payload), signature=signature)
            return recovered.lower() == user_address.lower()
        except Exception as e:
            print(f"验签出错: {e}")
            return False

    def _send_relayer_tx(self, to, nonce, deadline, signature):
        # 处理签名格式
        if signature.startswith("0x"):
            sig_bytes = bytes.fromhex(signature[2:])
        else:
            sig_bytes = bytes.fromhex(signature)

        # 修复 v 值 (0/1 -> 27/28)
        v = sig_bytes[-1]
        if v < 27:
            v += 27
            sig_bytes = sig_bytes[:-1] + bytes([v])

        # 构建交易
        func = self.contract.functions.sigMint(to, nonce, deadline, sig_bytes)
        relayer_nonce = self.w3.eth.get_transaction_count(self.relayer_account.address, 'pending')
        
        tx_params = func.build_transaction({
            'chainId': self.chain_id,
            'gas': 300000,
            'gasPrice': self.w3.eth.gas_price,
            'nonce': relayer_nonce,
            'from': self.relayer_account.address
        })
        
        signed_tx = self.w3.eth.account.sign_transaction(tx_params, private_key=self.relayer_private_key)
        # web3.py 7.x 使用 raw_transaction，旧版本使用 rawTransaction
        raw_tx = getattr(signed_tx, 'raw_transaction', None) or getattr(signed_tx, 'rawTransaction', None)
        tx_hash = self.w3.eth.send_raw_transaction(raw_tx).hex()
        # 确保返回带 0x 前缀的哈希
        return tx_hash if tx_hash.startswith('0x') else f'0x{tx_hash}'

    def get_mint_history(self, user_address, page=1, page_size=20):
        try:
            query = NFTMintRecord.query.filter_by(user_address=user_address).order_by(desc(NFTMintRecord.minted_at))
            pagination = query.paginate(page=page, per_page=page_size, error_out=False)
            results = []
            for item in pagination.items:
                results.append({
                    "id": item.id,
                    "tx_hash": item.tx_hash,
                    "nonce": item.nonce,
                    "status": item.mint_status,
                    "token_uri": item.token_uri,
                    "mint_time": item.minted_at.strftime('%Y-%m-%d %H:%M:%S') if item.minted_at else None,
                    "days_snapshot": item.sign_in_days_snapshot 
                })
            return True, {
                "list": results,
                "total": pagination.total,
                "pages": pagination.pages,
                "current_page": page,
                "page_size": page_size
            }
        except Exception as e:
            return False, f"查询历史失败: {str(e)}"