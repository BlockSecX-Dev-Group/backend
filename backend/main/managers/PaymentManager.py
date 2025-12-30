
import os
import sys
import requests
from web3 import Web3
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from main.models.PaymentOrder import PaymentOrder
from main.managers.Config import Config
from main.models.database import db
from main.managers.UserManager import UserManager
class PaymentManager:
    arb_one_apikey = Config.get_value('ARBITRUM_ONE_API_KEY')
    recharge_rate = Config.get_value('recharge_rate')

    def check_payment(self, payment_order: PaymentOrder):
        api_url = "https://api.etherscan.io/v2/api"
        # 反正正常情况下检查这么多肯定能成功，如果不对就是用户乱搞，那就不管了
        params = {
            "module": "account",
            "action": "tokentx",
            # 这里换成usdt在bsc链上面的合约地址就可以精准筛选了
            "contractaddress": "0x55d398326f99059ff775485246999027b3197955",
            "address": payment_order.receive_address,
            "page": 1,
            "offset": 100,
            "chainid": "56",
            "sort": "asc",
            "apikey": self.arb_one_apikey
        }
        response = requests.get(api_url, params=params)
        # 这里需要判断一下接口是否成功调用，如果后面不需要绑定地址付款，下面的验证逻辑就需要改
        if response.json()['status'] != '1':
            return
        elif response.json()['status'] == '1':
            results = response.json()['result']
            for result in results:
                # 这里需要二次验证，防止漏洞利用（低价值token充数），后面考虑改为usdt合约地址验证，其实上面请求参数加了后面就不太需要验证了
                if result['tokenName'] == "Binance-Peg BSC-USD" and result['tokenSymbol'] == "BSC-USD":
                    # 验证转账地址和金额，这里要做精度转换，usdt精度默认为18（BSC链是这样的），所以这里直接写死，注意地址类型要转换，避免大小写不匹配
                    if Web3.to_checksum_address(result['from']) == Web3.to_checksum_address(payment_order.user_address) and float(result['value']) / 1e18 >= payment_order.recharge_amount:
                        print(f"地址{payment_order.receive_address}的交易验证成功")
                        # 验证成功后先改订单表
                        payment_order.paid_status = True
                        payment_order.tx_hash = result['hash']
                        db.session.commit()
                        # 验证交易成功后就要给用户发放token，按照用户下单金额发放而不是收款金额发放
                        UserManager.update_user_balance(user_address=payment_order.user_address,
                                                        user_balance_change=payment_order.recharge_amount * self.recharge_rate)
                else:
                    continue
