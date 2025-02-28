import random
from eth_account import Account
from loguru import logger
from primp import AsyncClient
from web3 import AsyncWeb3

from src.utils.config import Config
from src.model.magiceden.get_mint_data import get_mint_data
from src.utils.constants import EXPLORER_URL, RPC_URL


class MagicEden:
    def __init__(
        self, account_index: int, config: Config, private_key: str, session: AsyncClient
    ):
        self.account_index = account_index
        self.private_key = private_key
        self.config = config
        self.account = Account.from_key(private_key)
        self.session: AsyncClient = session

        self.web3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(RPC_URL))

    async def mint(self) -> bool:
        """
        Mint an NFT from the specified contract on MagicEden

        Returns:
            bool: True if minting was successful, False otherwise
        """
        try:
            from src.model.magiceden.abi import ABI

            # 使用 to_checksum_address 将地址转换为正确的格式
            nft_contract_raw = random.choice(self.config.MAGICEDEN.NFT_CONTRACTS)
            
            nft_contract = self.web3.to_checksum_address(nft_contract_raw)

            logger.info(
                f"[{self.account_index}] | 🚀 Starting MagicEden mint for contract: {nft_contract}"
            )

            # 从 MagicEden API 获取铸币数据
            mint_data = await get_mint_data(self.session, nft_contract, self.account)

            # 检查用户是否已经铸造了 NFT
            if mint_data == "already_minted":
                logger.success(
                    f"[{self.account_index}] | ✅ NFT already minted from MagicEden (max mints per wallet reached)"
                )
                return True

            if mint_data == "all_nfts_minted":
                logger.warning(
                    f"[{self.account_index}] | ⚡️ All NFTs are minted from MagicEden or your balance is low."
                )
                return True

            if not mint_data:
                logger.error(
                    f"[{self.account_index}] | ❌ Failed to get MagicEden mint data for contract: {nft_contract}"
                )
                return False

            # 检查 API 响应中的交易数据
            try:
                # 检查响应是否包含直接交易的数据
                if (
                    "steps" in mint_data
                    and len(mint_data["steps"]) > 1
                    and "items" in mint_data["steps"][1]
                ):
                    sale_step = mint_data["steps"][1]
                    if len(sale_step["items"]) > 0 and "data" in sale_step["items"][0]:
                        tx_data = sale_step["items"][0]["data"]

                        # 使用来自 API 的交易数据
                        # logger.info(
                        #     f"[{self.account_index}] | 📝 Using transaction data from MagicEden API"
                        # )

                        # 我们获得必要的参数
                        to_address = self.web3.to_checksum_address(tx_data["to"])
                        from_address = self.web3.to_checksum_address(tx_data["from"])
                        data = tx_data["data"]
                        value = (
                            int(tx_data["value"], 16)
                            if tx_data["value"].startswith("0x")
                            else int(tx_data["value"])
                        )

                        # 如果可用，从 API 获取 gas_estimate
                        gas_estimate = sale_step["items"][0].get("gasEstimate", 500000)

                        # 使用来自 API 的数据创建交易
                        base_fee = await self.web3.eth.gas_price
                        priority_fee = int(base_fee * 0.1)  # 10% priority fee
                        max_fee_per_gas = base_fee + priority_fee

                        # 我们收到了随机数
                        nonce = await self.web3.eth.get_transaction_count(
                            self.account.address
                        )

                        # 使用更新的参数创建交易
                        tx = {
                            "from": from_address,
                            "to": to_address,
                            "value": value,
                            "data": data,
                            "nonce": nonce,
                            "maxFeePerGas": max_fee_per_gas,
                            "maxPriorityFeePerGas": priority_fee,
                            "chainId": 10143,
                        }

                        # 我们正在尝试估算天然气
                        try:
                            gas_estimate = await self.web3.eth.estimate_gas(tx)
                            gas_with_buffer = int(gas_estimate * 1.2)  # 20% буфер
                            tx["gas"] = gas_with_buffer

                            # logger.info(
                            #     f"[{self.account_index}] | ⛽ Estimated gas: {gas_estimate}, using: {gas_with_buffer}"
                            # )
                        except Exception as e:
                            raise Exception(f"⚠️ Failed to estimate gas: {e}")

                        # 检查余额
                        balance = await self.web3.eth.get_balance(self.account.address)
                        if balance < value:
                            logger.error(
                                f"[{self.account_index}] | ❌ Insufficient balance. "
                                f"Required: {value} wei, Available: {balance} wei"
                            )
                            return False

                        # 我们签署并发送交易
                        signed_tx = self.web3.eth.account.sign_transaction(
                            tx, self.private_key
                        )
                        tx_hash = await self.web3.eth.send_raw_transaction(
                            signed_tx.raw_transaction
                        )

                        logger.info(
                            f"[{self.account_index}] | 📤 MagicEden transaction sent: {EXPLORER_URL}{tx_hash.hex()}"
                        )

                        # 等待交易确认
                        tx_receipt = await self.web3.eth.wait_for_transaction_receipt(
                            tx_hash
                        )

                        if tx_receipt["status"] == 1:
                            logger.success(
                                f"[{self.account_index}] | ✅ Successfully minted MagicEden NFT. TX: {EXPLORER_URL}{tx_hash.hex()}"
                            )
                            return True
                        else:
                            logger.error(
                                f"[{self.account_index}] | ❌ MagicEden transaction failed. TX: {EXPLORER_URL}{tx_hash.hex()}"
                            )
                            return False

                # 如果您没有找到直接交易的数据，请使用标准方法
                logger.info(f"[{self.account_index}] | 🔄 Using standard mint approach")

                # 从铸币厂响应中提取必要的数据
                total_price = int(mint_data["path"][0]["totalPrice"])
                if total_price <= 0:
                    # 如果价格为 0，则留下 0 即可获得免费薄荷糖
                    total_price = 0
                    logger.info(
                        f"[{self.account_index}] | 🎁 MagicEden free mint detected"
                    )

                logger.info(
                    f"[{self.account_index}] | 💰 MagicEden mint price: {total_price}"
                )

                # 创建合约实例
                contract = self.web3.eth.contract(address=nft_contract, abi=ABI)

                # 获取当前 gas 价格并计算最高费用
                base_fee = await self.web3.eth.gas_price
                priority_fee = int(base_fee * 0.1)  # 10% priority fee
                max_fee_per_gas = base_fee + priority_fee

                # 首先构建没有 gas 估算的交易
                tx_params = {
                    "from": self.account.address,
                    "value": total_price,
                    "nonce": await self.web3.eth.get_transaction_count(
                        self.account.address
                    ),
                    "maxFeePerGas": max_fee_per_gas,
                    "maxPriorityFeePerGas": priority_fee,
                    "chainId": 10143,  # 我们明确指定 Monad 的 chainId
                }

                # 我们正在尝试估算gas
                try:
                    gas_estimate = await contract.functions.mint(
                        1, self.account.address
                    ).estimate_gas(tx_params)

                    gas_with_buffer = int(gas_estimate * 1.2)
                    logger.info(
                        f"[{self.account_index}] | ⛽ MagicEden gas estimate: {gas_estimate}, using: {gas_with_buffer}"
                    )

                    tx_params["gas"] = gas_with_buffer
                except Exception as e:
                    logger.error(
                        f"[{self.account_index}] | ❌ Failed to estimate gas: {e}. Cannot proceed with transaction."
                    )
                    return False

                # 建立最终交易
                tx = await contract.functions.mint(
                    1, self.account.address
                ).build_transaction(tx_params)

                # Sign transaction
                signed_tx = self.web3.eth.account.sign_transaction(tx, self.private_key)

                # Send transaction
                tx_hash = await self.web3.eth.send_raw_transaction(
                    signed_tx.raw_transaction
                )
                logger.info(
                    f"[{self.account_index}] | 📤 MagicEden transaction sent: {tx_hash.hex()}"
                )

                # Wait for transaction receipt
                tx_receipt = await self.web3.eth.wait_for_transaction_receipt(tx_hash)

                if tx_receipt["status"] == 1:
                    logger.success(
                        f"[{self.account_index}] | ✅ Successfully minted MagicEden NFT. TX: {tx_hash.hex()}"
                    )
                    return True
                else:
                    logger.error(
                        f"[{self.account_index}] | ❌ MagicEden transaction failed. TX: {tx_hash.hex()}"
                    )
                    return False

            except (KeyError, IndexError, TypeError) as e:
                logger.error(
                    f"[{self.account_index}] | ❌ Failed to extract data from mint response: {e}. Response: {mint_data}"
                )
                return False

        except Exception as e:
            logger.error(
                f"[{self.account_index}] | ❌ Error minting MagicEden NFT: {e}"
            )
            return False
