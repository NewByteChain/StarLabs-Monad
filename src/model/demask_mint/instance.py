import asyncio
import random
from eth_account import Account
from primp import AsyncClient
from web3 import AsyncWeb3
from web3.contract import Contract

from src.utils.constants import EXPLORER_URL, RPC_URL
from src.utils.config import Config
from loguru import logger

# 使用附加方法更新 NFT 合约的 ABI
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
        "inputs": [
            {"internalType": "bytes32[]", "name": "proof", "type": "bytes32[]"},
            {"internalType": "uint256", "name": "limit", "type": "uint256"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"},
        ],
        "name": "buy",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "", "type": "address"},
            {"internalType": "uint256", "name": "", "type": "uint256"},
        ],
        "name": "mintedCountPerWallet",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]


class Demask:
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

        self.nft_contract_address = "0x2CDd146Aa75FFA605ff7c5Cc5f62D3B52C140f9c"  # 更新了 DeMask 的合约地址
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
            # 让我们尝试使用合约中的 mintedCountPerWallet 函数
            # 此函数应返回用户已铸造的 NFT 数量
            stage_id = 0  # 我们假设这是第一阶段（可能需要调整）

            balance = await self.nft_contract.functions.mintedCountPerWallet(
                self.account.address, stage_id
            ).call()

            logger.info(f"[{self.account_index}] DeMask NFT balance: {balance}")
            return balance
        except Exception as e:
            # 如果第一种方法不起作用，请尝试标准 balanceOf
            try:
                token_id = 46917  # 交易中的代币 ID
                balance = await self.nft_contract.functions.balanceOf(
                    self.account.address, token_id
                ).call()

                logger.info(
                    f"[{self.account_index}] DeMask NFT balance (via balanceOf): {balance}"
                )
                return balance
            except Exception as e2:
                # 如果两种方法都失败，则记录错误并返回 0
                logger.warning(
                    f"[{self.account_index}] Error checking NFT balance via mintedCountPerWallet: {e}"
                )
                logger.warning(
                    f"[{self.account_index}] Error checking NFT balance via balanceOf: {e2}"
                )

                # 检查交易历史记录作为最后的手段
                try:
                    # 获取合约地址的交易历史记录
                    tx_count = await self.web3.eth.get_transaction_count(
                        self.account.address
                    )

                    # 为了简单起见，我们只检查最近 10 笔交易。
                    for i in range(max(0, tx_count - 10), tx_count):
                        try:
                            nonce = i
                            tx = await self.web3.eth.get_transaction_by_nonce(
                                self.account.address, nonce
                            )

                            # 如果交易符合我们的合同并成功完成
                            if (
                                tx
                                and tx.to
                                and tx.to.lower() == self.nft_contract_address.lower()
                            ):
                                receipt = await self.web3.eth.get_transaction_receipt(
                                    tx.hash
                                )
                                if receipt and receipt.status == 1:
                                    # 发现有一笔成功的交易到 NFT 合约
                                    logger.info(
                                        f"[{self.account_index}] Found successful transaction to DeMask contract"
                                    )
                                    return (
                                        1  # 返回 1，表示 NFT 已被铸造
                                    )
                        except Exception:
                            continue
                except Exception as e3:
                    logger.warning(
                        f"[{self.account_index}] Error checking transaction history: {e3}"
                    )

                # 如果所有方法都失败，则返回 0
                return 0

    async def mint(self):
        for retry in range(self.config.SETTINGS.ATTEMPTS):
            try:
                balance = await self.get_nft_balance()

                random_amount = random.randint(
                    self.config.DEMASK.MAX_AMOUNT_FOR_EACH_ACCOUNT[0],
                    self.config.DEMASK.MAX_AMOUNT_FOR_EACH_ACCOUNT[1],
                )

                if balance >= random_amount:
                    logger.success(
                        f"[{self.account_index}] DeMask NFT already minted: {balance} NFTS"
                    )
                    return True

                logger.info(f"[{self.account_index}] Minting DeMask NFT")

                # 使用 buy 方法准备铸币交易
                # 我们使用一个空的证明，limit=1000000，amount=1
                mint_txn = await self.nft_contract.functions.buy(
                    [], 1000000, 1
                ).build_transaction(
                    {
                        "from": self.account.address,
                        "value": self.web3.to_wei(0.1, "ether"),  # Оплата 0.1 MON
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
                        f"[{self.account_index}] Successfully minted DeMask NFT. TX: {EXPLORER_URL}{tx_hash.hex()}"
                    )
                    return True
                else:
                    logger.error(
                        f"[{self.account_index}] Failed to mint DeMask NFT. TX: {EXPLORER_URL}{tx_hash.hex()}"
                    )
                    return False

            except Exception as e:
                random_pause = random.randint(
                    self.config.SETTINGS.RANDOM_PAUSE_BETWEEN_ACTIONS[0],
                    self.config.SETTINGS.RANDOM_PAUSE_BETWEEN_ACTIONS[1],
                )
                logger.error(
                    f"[{self.account_index}] Error in mint on DeMask: {e}. Sleeping for {random_pause} seconds"
                )
                await asyncio.sleep(random_pause)

        return False
