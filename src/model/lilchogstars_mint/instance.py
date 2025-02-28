import asyncio
import random
from eth_account import Account
from primp import AsyncClient
from web3 import AsyncWeb3
from web3.contract import Contract

from src.utils.constants import EXPLORER_URL, RPC_URL
from src.utils.config import Config
from loguru import logger

# 更新 NFT 合约的 ABI
ERC1155_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "account", "type": "address"},
            {"internalType": "uint256", "name": "id", "type": "uint256"},
        ],
        "name": "balanceOf",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "uint256", "name": "quantity", "type": "uint256"}],
        "name": "mint",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "address", "name": "", "type": "address"}],
        "name": "mintedCount",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "totalSupply",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]


class Lilchogstars:
    def __init__(
        self,
        account_index: int,
        proxy: str,
        private_key: str,
        config: Config,
        session: AsyncClient,
    ):
        self.account_index = account_index
        self.proxy = proxy
        self.private_key = private_key
        self.config = config
        self.session = session

        self.account: Account = Account.from_key(private_key=private_key)
        self.web3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(RPC_URL))

        self.nft_contract_address = (
            "0xb33D7138c53e516871977094B249C8f2ab89a4F4"  # 更新合约地址
        )
        self.nft_contract: Contract = self.web3.eth.contract(
            address=self.nft_contract_address, abi=ERC1155_ABI
        )

    async def get_nft_balance(self) -> int:
        """
        检查当前账户的 NFT 余额
        返回：
        int：NFT 数量
        """
        try:
            # 使用 mintedCount 方法获取 NFT 的数量
            balance = await self.nft_contract.functions.mintedCount(
                self.account.address
            ).call()

            logger.info(
                f"[{self.account_index}] NFT balance from mintedCount: {balance}"
            )
            return balance
        except Exception as e:
            logger.error(
                f"[{self.account_index}] Error checking NFT balance with mintedCount: {e}"
            )
            raise e

    async def mint(self):
        for retry in range(self.config.SETTINGS.ATTEMPTS):
            try:
                balance = await self.get_nft_balance()  # 获取当前 NFT 余额
                # 生成随机数量以避免同时尝试 mint
                random_amount = random.randint(
                    self.config.LILCHOGSTARS.MAX_AMOUNT_FOR_EACH_ACCOUNT[0],
                    self.config.LILCHOGSTARS.MAX_AMOUNT_FOR_EACH_ACCOUNT[1],
                )

                logger.info(
                    f"[{self.account_index}] Current NFT balance: {balance}, Target: {random_amount}"
                )

                if balance >= random_amount:
                    logger.success(
                        f"[{self.account_index}] Lilchogstars NFT already minted: {balance} NFTS"
                    )
                    return True

                logger.info(f"[{self.account_index}] Minting Lilchogstars NFT")

                # 我们准备一个参数为数量=1的铸币交易
                mint_txn = await self.nft_contract.functions.mint(1).build_transaction(
                    {
                        "from": self.account.address,
                        "value": self.web3.to_wei(0, "ether"),  # Бесплатный минт
                        "nonce": await self.web3.eth.get_transaction_count(
                            self.account.address
                        ),
                        "maxFeePerGas": await self.web3.eth.gas_price,
                        "maxPriorityFeePerGas": await self.web3.eth.gas_price,
                    }
                )

                # 我们签署交易
                signed_txn = self.web3.eth.account.sign_transaction(
                    mint_txn, self.private_key
                )

                # 发送交易
                tx_hash = await self.web3.eth.send_raw_transaction(
                    signed_txn.raw_transaction
                )

                # 我们正在等待确认
                receipt = await self.web3.eth.wait_for_transaction_receipt(tx_hash)

                if receipt["status"] == 1:
                    logger.success(
                        f"[{self.account_index}] Successfully minted Lilchogstars NFT. TX: {EXPLORER_URL}{tx_hash.hex()}"
                    )
                    return True
                else:
                    logger.error(
                        f"[{self.account_index}] Failed to mint Lilchogstars NFT. TX: {EXPLORER_URL}{tx_hash.hex()}"
                    )
                    return False

            except Exception as e:
                random_pause = random.randint(
                    self.config.SETTINGS.RANDOM_PAUSE_BETWEEN_ACTIONS[0],
                    self.config.SETTINGS.RANDOM_PAUSE_BETWEEN_ACTIONS[1],
                )
                logger.error(
                    f"[{self.account_index}] Error in mint on Lilchogstars: {e}. Sleeping for {random_pause} seconds"
                )
                await asyncio.sleep(random_pause)

        return False
