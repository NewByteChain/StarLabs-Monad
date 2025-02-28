from web3 import AsyncWeb3
from eth_account import Account
from loguru import logger
from typing import Optional, Tuple
from dataclasses import dataclass
from threading import Lock

from src.utils.constants import RPC_URL
from src.utils.config import Config


@dataclass
class WalletInfo:
    account_index: int
    private_key: str
    address: str
    balance: float
    transactions: int


class WalletStats:
    def __init__(self, config: Config):
        # Используем публичную RPC ноду Base
        self.w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(RPC_URL))
        self.config = config
        self._lock = Lock()

    async def get_wallet_stats(
        self, private_key: str, account_index: int
    ) -> Optional[bool]:
        """
        获取钱包统计信息并保存到配置

        参数：
        private_key：钱包的私钥
        account_index: 账户索引

        返回：
        bool: 如果成功则为 True，如果错误则为 False
        """
        try:
            # 我们从私钥中获取地址
            account = Account.from_key(private_key)
            address = account.address

            # 查询ETH余额
            balance_wei = await self.w3.eth.get_balance(address)
            balance_eth = self.w3.from_wei(balance_wei, "ether")

            # 获取交易数量（nonce）
            tx_count = await self.w3.eth.get_transaction_count(address)

            wallet_info = WalletInfo(
                account_index=account_index, # 账户索引
                private_key=private_key,    # 私钥
                address=address,            # 地址
                balance=float(balance_eth), # 余额
                transactions=tx_count,      # 交易数量
            )

            with self._lock:
                self.config.WALLETS.wallets.append(wallet_info)

            logger.info(
                f"Wallet {address}: Balance = {balance_eth:.4f} MON, "
                f"Transactions = {tx_count}"
            )

            return True

        except Exception as e:
            logger.error(f"Error getting wallet stats: {e}")
            return False
