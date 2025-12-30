
from web3 import Web3
import os
import sys
from eth_account import Account
from mnemonic import Mnemonic
import os
from cryptography.fernet import Fernet, InvalidToken
from cryptography.fernet import Fernet
from hdwallet.cryptocurrencies import Ethereum as EthereumMainnet  # 尝试别名导入
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from main.managers.Config import Config
from main.models.TokenDistributeRecord import TokenDistributeRecord
from main.models.database import db
from main.models.Wallet import Wallet
from main.models.PaymentOrder import PaymentOrder
from main.managers.UserManager import UserManager


class TokenService:

    def __init__(self):
        self.web3_token_pool_address = Config.get_value('web3_token_pool_address')
        self.web3_token_pool_private_key = Config.get_value('web3_token_pool_private_key')
        self.web3_token_contract_address = Config.get_value('web3_token_contract_address')

        # 种子短语
        MNEMONIC_FILE = 'mnemonic.txt'
        if not os.path.exists(MNEMONIC_FILE):
            mnemo = Mnemonic("english")
            mnemonic = mnemo.generate(strength=256)
            with open(MNEMONIC_FILE, 'w') as f:
                f.write(mnemonic)
        else:
            with open(MNEMONIC_FILE, 'r') as f:
                mnemonic = f.read()
        self.mnemonic = mnemonic

        # 加密密钥
        ENCRYPTION_KEY_FILE = 'encryption_key.txt'
        if not os.path.exists(ENCRYPTION_KEY_FILE):
            encryption_key = Fernet.generate_key()
            with open(ENCRYPTION_KEY_FILE, 'wb') as f:
                f.write(encryption_key)
        else:
            with open(ENCRYPTION_KEY_FILE, 'rb') as f:
                encryption_key = f.read()
        cipher = Fernet(encryption_key)
        self.cipher = cipher

        # 启用 eth-account 的助记词功能
        Account.enable_unaudited_hdwallet_features()

    def web2_token_to_web3_token(self, user_address, token_amount):
        # 现在用的是测试网，等上主网这里要改的
        bsc_testnet_url = "https://data-seed-prebsc-1-s1.binance.org:8545/"
        web3 = Web3(Web3.HTTPProvider(bsc_testnet_url))

        # 检查连接
        if not web3.is_connected():
            raise Exception("无法连接到 BSC 测试网")

        # web token相关信息通过配置文件获取，直接改配置文件即可
        private_key = self.web3_token_pool_private_key
        sender_address = Web3.to_checksum_address(self.web3_token_pool_address)
        receiver_address = Web3.to_checksum_address(user_address)
        contract_address = Web3.to_checksum_address(self.web3_token_contract_address)

        # 简化的 ERC-20 ABI，只包含 transfer 函数
        abi = [
            {
                "constant": False,
                "inputs": [
                    {"name": "_to", "type": "address"},
                    {"name": "_value", "type": "uint256"}
                ],
                "name": "transfer",
                "outputs": [{"name": "", "type": "bool"}],
                "type": "function"
            }
        ]

        # 创建合约对象
        contract = web3.eth.contract(address=contract_address, abi=abi)

        amount = web3.to_wei(token_amount, 'ether')  # 这里填实际数值即可，精度会自己计算（精度为 18 位，类似 ether 单位）

        # 构建交易
        nonce = web3.eth.get_transaction_count(sender_address)
        tx = contract.functions.transfer(receiver_address, amount).build_transaction({
            'chainId': 97,  # BSC 测试网的 Chain ID
            'gas': 200000,  # Gas 限制，根据实际情况调整
            'gasPrice': web3.to_wei('10', 'gwei'),  # Gas 价格
            'nonce': nonce
        })

        # 签名交易
        signed_tx = web3.eth.account.sign_transaction(tx, private_key)

        # 发送交易, 交易信息返回如果后面换成主网也要跟着改，可以考虑返回的不是txid， 而是区块链浏览器地址
        tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)

        print(f"交易哈希: {web3.to_hex(tx_hash)}")
        print(f"查看交易状态: https://testnet.bscscan.com/tx/{web3.to_hex(tx_hash)}")

        # TODO 这里还得补一个扣用户的款
        UserManager.update_user_balance(user_address, (-1) * token_amount)
        tokenDistributeRecord = TokenDistributeRecord(user_address=user_address, token_amount=token_amount)
        db.session.add(tokenDistributeRecord)
        db.session.commit()
        # 直接用Web3库的这个方法最方便，不然就算直接用hex()函数转字符串还得手动补一个0x头
        return True, Web3.to_hex(tx_hash)

    # 生成新收款地址函数
    def generate_new_address(self):
        index = Wallet.query.count()
        account = Account.from_mnemonic(self.mnemonic, account_path=f"m/44'/60'/0'/0/{index}")
        address = account.address
        private_key = account.key.hex()
        encrypted_private_key = self.cipher.encrypt(private_key.encode()).decode()

        # with app.app_context():
        new_wallet = Wallet(address=address, private_key=encrypted_private_key)
        db.session.add(new_wallet)
        db.session.commit()
        return address

    def get_and_decrypt_all_private_keys(self):
        # 获取加密密钥
        ENCRYPTION_KEY_FILE = 'encryption_key.txt'
        try:
            with open(ENCRYPTION_KEY_FILE, 'rb') as f:
                encryption_key = f.read()
            print(f"成功加载加密密钥，长度: {len(encryption_key)} 字节")
        except FileNotFoundError:
            print(f"错误: 找不到 {ENCRYPTION_KEY_FILE} 文件")
            return []
        except Exception as e:
            print(f"读取加密密钥时出错: {str(e)}")
            return []

        cipher = Fernet(encryption_key)

        # 从数据库查询所有钱包记录
        wallets = Wallet.query.all()
        print(f"找到 {len(wallets)} 个钱包记录")

        # 创建存储解密后私钥的列表
        decrypted_private_keys = []

        # 遍历所有钱包记录，解密私钥并添加到列表
        for wallet in wallets:
            if wallet.private_key:
                print(f"处理钱包 ID {wallet.id}，加密私钥: {wallet.private_key}")
                try:
                    decrypted_key = cipher.decrypt(wallet.private_key.encode()).decode()
                    decrypted_private_keys.append(decrypted_key)
                    print(f"钱包 ID {wallet.id} 解密成功")
                except InvalidToken:  # 正确使用 InvalidToken
                    print(f"解密钱包 ID {wallet.id} 失败: 无效的加密密钥或数据损坏")
                except Exception as e:
                    print(f"解密钱包 ID {wallet.id} 失败: {str(e)}")
            else:
                print(f"钱包 ID {wallet.id} 的私钥为空，跳过")

        # 逐行打印到控制台
        print("\n所有解密后的私钥:")
        for i, key in enumerate(decrypted_private_keys, 1):
            print(f"私钥 {i}: {key}")

        return decrypted_private_keys

    def create_recharge_order(self, user_address, recharge_amount):
        receive_address = self.generate_new_address()
        payment_order = PaymentOrder(user_address=user_address, recharge_amount=recharge_amount, receive_address=receive_address, paid_status=False)
        db.session.add(payment_order)
        db.session.commit()
        return receive_address

    def get_user_recharge_history(self, user_address):
        payment_orders = PaymentOrder.query.filter_by(user_address=user_address).all()
        user_orders = [{
            "user_address": payment_order.user_address,
            "receive_address": payment_order.receive_address,
            "recharge_amount": payment_order.recharge_amount,
            "order_time": payment_order.order_time,
            "paid_status": payment_order.paid_status,
            "tx_hash": payment_order.tx_hash
        } for payment_order in payment_orders]
        return user_orders


    def get_recharge_order_info(self, receive_address):
        payment_order = PaymentOrder.query.filter_by(receive_address=receive_address).first()
        return {
            "user_address": payment_order.user_address,
            "receive_address": payment_order.receive_address,
            "recharge_amount": payment_order.recharge_amount,
            "order_time": payment_order.order_time,
            "paid_status": payment_order.paid_status,
            "tx_hash": payment_order.tx_hash
        }

