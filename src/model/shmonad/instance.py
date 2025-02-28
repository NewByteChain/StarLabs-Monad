import asyncio
import random
from loguru import logger
from eth_account import Account
from primp import AsyncClient
from web3 import AsyncWeb3
from src.utils.config import Config
from src.utils.constants import EXPLORER_URL, RPC_URL
from src.model.shmonad.constants import SHMONAD_ADDRESS, SHMONAD_ABI, STAKE_POLICY_ID
from typing import Dict


class Shmonad:
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

    # 获取shmon余额
    async def _get_shmon_balance(self):
        for retry in range(self.config.SETTINGS.ATTEMPTS):
            try:
                contract = self.web3.eth.contract(
                    address=SHMONAD_ADDRESS, abi=SHMONAD_ABI
                )

                balance = await contract.functions.balanceOf(
                    self.account.address
                ).call()
                return balance, balance / 10**18
            except Exception as e:
                logger.error(
                    f"[{self.account_index}] | Error getting Shmonad balance: {e}"
                )
                await asyncio.sleep(1)
        return None

    async def swaps(self):
        for retry in range(self.config.SETTINGS.ATTEMPTS):
            try:
                # SHMONAD质押 = false，SHMONAD出售 = false，不进行任何操作
                if (
                    not self.config.SHMONAD.BUY_AND_STAKE_SHMON
                    and not self.config.SHMONAD.UNSTAKE_AND_SELL_SHMON
                ):
                    logger.info(
                        f"[{self.account_index}] | Shmonad operations disabled in config"
                    )
                    return True

                # 查询SHMONAD余额
                shmon_balance, shmon_balance_formatted = await self._get_shmon_balance()
                if shmon_balance is None:
                    logger.error(
                        f"[{self.account_index}] | Failed to get Shmon balance"
                    )
                    continue

                logger.success(
                    f"[{self.account_index}] | Shmon balance: {shmon_balance_formatted:.6f} shMON"
                )

                # 获取质押中的MON余额
                bonded_balance, bonded_balance_formatted = (
                    await self._get_bonded_balance()
                )
                if bonded_balance is not None:
                    logger.success(
                        f"[{self.account_index}] | Bonded balance: {bonded_balance_formatted:.6f} shMON"
                    )

                # SHMONAD 购买质押 = falsh，SHMONAD出售 = true，swap进行解除质押并赎回操作
                if (
                    self.config.SHMONAD.UNSTAKE_AND_SELL_SHMON
                    and not self.config.SHMONAD.BUY_AND_STAKE_SHMON
                ):
                    if bonded_balance_formatted > 0.001:  # 余额大于0.001才进行质押操作
                        if not await self.unstake_shmon():  # 解除质押
                            logger.error(
                                f"[{self.account_index}] | Failed to unstake Shmon"
                            )
                            continue

                        random_pause = random.randint(
                            self.config.SETTINGS.PAUSE_BETWEEN_SWAPS[0],
                            self.config.SETTINGS.PAUSE_BETWEEN_SWAPS[1],
                        )
                        logger.info(
                            f"[{self.account_index}] | Sleeping for {random_pause} seconds before selling Shmon"
                        )
                        await asyncio.sleep(random_pause)

                        if not await self.sell_shmon():
                            logger.error(
                                f"[{self.account_index}] | Failed to sell Shmon"
                            )
                            continue

                # # SHMONAD 购买质押 = true，SHMONAD出售 = false，swap进行质押操作（如果已经存在质押，则先取回质押，再重新质押）
                elif (
                    self.config.SHMONAD.BUY_AND_STAKE_SHMON
                    and not self.config.SHMONAD.UNSTAKE_AND_SELL_SHMON
                ):
                    if not await self.buy_shmon(): # 买入swap操作
                        logger.error(f"[{self.account_index}] | Failed to buy Shmon")
                        continue
                    # 等待一段时间再质押 
                    random_pause = random.randint(
                        self.config.SETTINGS.PAUSE_BETWEEN_SWAPS[0],
                        self.config.SETTINGS.PAUSE_BETWEEN_SWAPS[1],
                    )
                    logger.info(
                        f"[{self.account_index}] | Sleeping for {random_pause} seconds before staking Shmon"
                    )
                    await asyncio.sleep(random_pause)

                    if not await self.stake_shmon(): # 质押操作
                        logger.error(f"[{self.account_index}] | Failed to stake Shmon")
                        continue

                # 如果两者都启用
                else:
                    if bonded_balance_formatted > 0.001:   # 质押中的余额大于0.001
                        # 如果有质押的代币 - 先解除质押并出售
                        if not await self.unstake_shmon():
                            logger.error(
                                f"[{self.account_index}] | Failed to unstake Shmon"
                            )
                            continue

                        random_pause = random.randint(
                            self.config.SETTINGS.PAUSE_BETWEEN_SWAPS[0],
                            self.config.SETTINGS.PAUSE_BETWEEN_SWAPS[1],
                        )
                        logger.info(
                            f"[{self.account_index}] | Sleeping for {random_pause} seconds before selling Shmon"
                        )
                        await asyncio.sleep(random_pause)  # 休眠等待一会儿，再执行下一步操作

                        if not await self.sell_shmon():  # 出售操作
                            logger.error(
                                f"[{self.account_index}] | Failed to sell Shmon"
                            )
                            continue
                    elif shmon_balance_formatted > 0.001:   # 没有质押金额，并且有shmon余额
                        # 如果没有质押的，先卖出shMON
                        if not await self.sell_shmon():
                            logger.error(
                                f"[{self.account_index}] | Failed to sell Shmon"
                            )
                            continue
                    else:
                        # 没有质押，且没有shmon余额，则购买shmon
                        if not await self.buy_shmon():
                            logger.error(
                                f"[{self.account_index}] | Failed to buy Shmon"
                            )
                            continue

                        random_pause = random.randint(
                            self.config.SETTINGS.PAUSE_BETWEEN_SWAPS[0],
                            self.config.SETTINGS.PAUSE_BETWEEN_SWAPS[1],
                        )
                        logger.info(
                            f"[{self.account_index}] | Sleeping for {random_pause} seconds before staking Shmon"
                        )
                        await asyncio.sleep(random_pause) # 休眠等待一会儿，再执行下一步操作

                        if not await self.stake_shmon(): # 质押操作
                            logger.error(
                                f"[{self.account_index}] | Failed to stake Shmon"
                            )
                            continue

                return True

            except Exception as e:
                logger.error(f"[{self.account_index}] | Error swapping Shmonad: {e}")
                await asyncio.sleep(1)
                continue
        return False

    # 买入
    async def buy_shmon(self) -> bool:
        for retry in range(self.config.SETTINGS.ATTEMPTS):
            try:
                mon_balance = await self.web3.eth.get_balance(self.account.address)
                # 交互的比例
                random_percent = random.randint(
                    self.config.SHMONAD.PERCENT_OF_BALANCE_TO_SWAP[0],
                    self.config.SHMONAD.PERCENT_OF_BALANCE_TO_SWAP[1],
                )

                amount_to_swap = mon_balance * random_percent // 100
                # 留一些 MON 来加油
                amount_to_swap = int(amount_to_swap * 0.95)  #  最大质押金额95%

                logger.info(
                    f"[{self.account_index}] | Buying Shmon with {amount_to_swap / 10**18:.6f} MON"
                )

                contract = self.web3.eth.contract(
                    address=SHMONAD_ADDRESS, abi=SHMONAD_ABI
                )

                gas_params = await self.get_gas_params() # 获取 gas 参数

                # 创建 gas 定价的基本交易
                transaction = {
                    "from": self.account.address,
                    "to": SHMONAD_ADDRESS,
                    "value": amount_to_swap,
                    "data": contract.functions.deposit(
                        amount_to_swap, self.account.address
                    )._encode_transaction_data(),
                    "chainId": 10143,
                    "type": 2,
                }

                # 我们评估天然气
                estimated_gas = await self.estimate_gas(transaction)
                # 构建交易
                transaction = await contract.functions.deposit(
                    amount_to_swap,  # 资产
                    self.account.address,  # 接收者
                ).build_transaction(
                    {
                        "from": self.account.address,
                        "value": amount_to_swap,  # 我们发送相同数量的 MON
                        "nonce": await self.web3.eth.get_transaction_count(
                            self.account.address
                        ),
                        "gas": estimated_gas,
                        **gas_params,
                    }
                )
                # 发送交易
                signed_txn = self.web3.eth.account.sign_transaction(
                    transaction, self.private_key
                )
                # 获得交易tx_hash
                tx_hash = await self.web3.eth.send_raw_transaction(
                    signed_txn.raw_transaction
                )

                logger.info(
                    f"[{self.account_index}] | Buying Shmon with {amount_to_swap / 10**18:.6f} MON | Tx: {EXPLORER_URL}{tx_hash.hex()}"
                )
                # 等待交易收据（交易广播）
                receipt = await self.web3.eth.wait_for_transaction_receipt(tx_hash)
                if receipt["status"] == 1:
                    logger.success(
                        f"[{self.account_index}] | Successfully bought Shmon | Tx: {EXPLORER_URL}{tx_hash.hex()}"
                    )
                    return True
                else:
                    logger.error(f"[{self.account_index}] | Failed to buy Shmon")
                    return False

            except Exception as e:
                logger.error(f"[{self.account_index}] | Error buying Shmon: {e}")
                await asyncio.sleep(1)
                continue
        return False

    # 出售shMON
    async def sell_shmon(self) -> bool:
        for retry in range(self.config.SETTINGS.ATTEMPTS):
            try:
                shmon_balance, shmon_balance_formatted = await self._get_shmon_balance()  # 获取 shMON 余额
                if shmon_balance == 0:
                    logger.error(f"[{self.account_index}] | No Shmon balance to sell")
                    return False

                logger.info(
                    f"[{self.account_index}] | Selling {shmon_balance_formatted:.6f} shMON"
                )

                contract = self.web3.eth.contract(
                    address=SHMONAD_ADDRESS, abi=SHMONAD_ABI
                )

                gas_params = await self.get_gas_params()

                # 创建 gas 定价的基本交易
                transaction = {
                    "from": self.account.address,
                    "to": SHMONAD_ADDRESS,
                    "value": 0,
                    "data": contract.functions.redeem(
                        shmon_balance,  # 出售全部余额
                        self.account.address,  # 接收人 MON
                        self.account.address,  # 发送人 shMON
                    )._encode_transaction_data(),
                    "chainId": 10143,
                    "type": 2,
                }

                # 我们评估gas
                estimated_gas = await self.estimate_gas(transaction)

                transaction = await contract.functions.redeem(
                    shmon_balance,
                    self.account.address,
                    self.account.address,
                ).build_transaction(
                    {
                        "from": self.account.address,
                        "value": 0,
                        "nonce": await self.web3.eth.get_transaction_count(
                            self.account.address
                        ),
                        "gas": estimated_gas,
                        **gas_params,
                    }
                )

                signed_txn = self.web3.eth.account.sign_transaction(
                    transaction, self.private_key
                )
                tx_hash = await self.web3.eth.send_raw_transaction(
                    signed_txn.raw_transaction
                )

                logger.info(
                    f"[{self.account_index}] | Selling {shmon_balance_formatted:.6f} shMON | Tx: {EXPLORER_URL}{tx_hash.hex()}"
                )

                receipt = await self.web3.eth.wait_for_transaction_receipt(tx_hash)
                if receipt["status"] == 1:
                    logger.success(
                        f"[{self.account_index}] | Successfully sold Shmon | Tx: {EXPLORER_URL}{tx_hash.hex()}"
                    )
                    return True
                else:
                    logger.error(f"[{self.account_index}] | Failed to sell Shmon")
                    return False

            except Exception as e:
                logger.error(f"[{self.account_index}] | Error selling Shmon: {e}")
                await asyncio.sleep(1)
                continue
        return False

    # 股份质押
    async def stake_shmon(self) -> bool:
        for retry in range(self.config.SETTINGS.ATTEMPTS):
            try:
                shmon_balance, shmon_balance_formatted = await self._get_shmon_balance()
                if shmon_balance == 0:
                    logger.error(f"[{self.account_index}] | No Shmon balance to stake")
                    return False

                logger.info(
                    f"[{self.account_index}] | Bonding {shmon_balance_formatted:.6f} shMON"
                )

                contract = self.web3.eth.contract(
                    address=SHMONAD_ADDRESS, abi=SHMONAD_ABI
                )

                gas_params = await self.get_gas_params()

                # 创建 gas 定价的基本交易
                transaction = {
                    "from": self.account.address,
                    "to": SHMONAD_ADDRESS,
                    "value": 0,
                    "data": contract.functions.bond(
                        STAKE_POLICY_ID,  # policyID
                        self.account.address,  # 债券接收者
                        shmon_balance,  # amount
                    )._encode_transaction_data(),
                    "chainId": 10143,
                    "type": 2,
                }

                estimated_gas = await self.estimate_gas(transaction)

                transaction = await contract.functions.bond(
                    STAKE_POLICY_ID,
                    self.account.address,
                    shmon_balance,
                ).build_transaction(
                    {
                        "from": self.account.address,
                        "value": 0,
                        "nonce": await self.web3.eth.get_transaction_count(
                            self.account.address
                        ),
                        "gas": estimated_gas,
                        **gas_params,
                    }
                )

                signed_txn = self.web3.eth.account.sign_transaction(
                    transaction, self.private_key
                )
                tx_hash = await self.web3.eth.send_raw_transaction(
                    signed_txn.raw_transaction
                )

                logger.info(
                    f"[{self.account_index}] | Bonding {shmon_balance_formatted:.6f} shMON | Tx: {EXPLORER_URL}{tx_hash.hex()}"
                )

                receipt = await self.web3.eth.wait_for_transaction_receipt(tx_hash)
                if receipt["status"] == 1:
                    logger.success(
                        f"[{self.account_index}] | Successfully bonded Shmon | Tx: {EXPLORER_URL}{tx_hash.hex()}"
                    )
                    return True
                else:
                    logger.error(f"[{self.account_index}] | Failed to bond Shmon")
                    return False

            except Exception as e:
                logger.error(f"[{self.account_index}] | Error bonding Shmon: {e}")
                await asyncio.sleep(1)
                continue
        return False

    # 获取 shMON 的质押余额
    async def _get_bonded_balance(self):
        """Get bonded (staked) balance of shMON."""
        for retry in range(self.config.SETTINGS.ATTEMPTS):
            try:
                contract = self.web3.eth.contract(
                    address=SHMONAD_ADDRESS, abi=SHMONAD_ABI
                )

                balance = await contract.functions.balanceOfBonded(
                    STAKE_POLICY_ID, self.account.address
                ).call()
                return balance, balance / 10**18
            except Exception as e:
                logger.error(
                    f"[{self.account_index}] | Error getting bonded balance: {e}"
                )
                await asyncio.sleep(1)
        return None

    # 取消质押股份
    async def unstake_shmon(self) -> bool:
        for retry in range(self.config.SETTINGS.ATTEMPTS):
            try:
                bonded_balance, bonded_balance_formatted = (
                    await self._get_bonded_balance()  # 获取 shMON 的质押余额
                )
                if bonded_balance == 0:  # 如果没有质押余额直接退出
                    logger.error(
                        f"[{self.account_index}] | No bonded Shmon balance to unstake"  # 没有可解除质押的 Shmon 余额
                    )
                    return False

                # 如果存在质押进入，首先我们解除绑定
                logger.info(
                    f"[{self.account_index}] | Unbonding {bonded_balance_formatted:.6f} shMON"
                )

                contract = self.web3.eth.contract(
                    address=SHMONAD_ADDRESS, abi=SHMONAD_ABI  # 质押合约
                )

                gas_params = await self.get_gas_params() # 获取 gas 参数

                # 第一步交易： unbond接触质押
                transaction = {
                    "from": self.account.address,
                    "to": SHMONAD_ADDRESS,
                    "value": 0,
                    "data": contract.functions.unbond(
                        STAKE_POLICY_ID,
                        bonded_balance,
                        bonded_balance,
                    )._encode_transaction_data(),
                    "chainId": 10143,
                    "type": 2,
                }

                estimated_gas = await self.estimate_gas(transaction)  # 评估gas
                # 执行接触质押操作
                transaction = await contract.functions.unbond(  
                    STAKE_POLICY_ID,
                    bonded_balance,
                    bonded_balance,
                ).build_transaction(
                    {
                        "from": self.account.address,
                        "value": 0,
                        "nonce": await self.web3.eth.get_transaction_count(
                            self.account.address
                        ),
                        "gas": estimated_gas,
                        **gas_params,
                    }
                )

                signed_txn = self.web3.eth.account.sign_transaction(
                    transaction, self.private_key
                )
                tx_hash = await self.web3.eth.send_raw_transaction(
                    signed_txn.raw_transaction
                )

                logger.info(
                    f"[{self.account_index}] | Unbonding {bonded_balance_formatted:.6f} shMON | Tx: {EXPLORER_URL}{tx_hash.hex()}"
                )

                receipt = await self.web3.eth.wait_for_transaction_receipt(tx_hash)
                if receipt["status"] != 1:
                    logger.error(f"[{self.account_index}] | Failed to unbond Shmon")
                    return False

                # 等待约 1 分钟后再领取
                random_pause = random.randint(40, 60)
                random_pause_config = random.randint(
                    self.config.SETTINGS.PAUSE_BETWEEN_SWAPS[0],
                    self.config.SETTINGS.PAUSE_BETWEEN_SWAPS[1],
                )
                random_pause += random_pause_config
                logger.info(
                    f"[{self.account_index}] | Sleeping for {random_pause} seconds before claiming Shmon"
                )
                await asyncio.sleep(random_pause)

                # 第二步交易 - 接触质押之后，进行claim
                logger.info(
                    f"[{self.account_index}] | Claiming {bonded_balance_formatted:.6f} shMON"
                )

                transaction = {
                    "from": self.account.address,
                    "to": SHMONAD_ADDRESS,
                    "value": 0,
                    "data": contract.functions.claim(
                        STAKE_POLICY_ID,
                        bonded_balance,
                    )._encode_transaction_data(),
                    "chainId": 10143,
                    "type": 2,
                }

                estimated_gas = await self.estimate_gas(transaction)
                transaction = await contract.functions.claim(
                    STAKE_POLICY_ID,
                    bonded_balance,
                ).build_transaction(
                    {
                        "from": self.account.address,
                        "value": 0,
                        "nonce": await self.web3.eth.get_transaction_count(
                            self.account.address
                        ),
                        "gas": estimated_gas,
                        **gas_params,
                    }
                )

                signed_txn = self.web3.eth.account.sign_transaction(
                    transaction, self.private_key
                )
                tx_hash = await self.web3.eth.send_raw_transaction(
                    signed_txn.raw_transaction
                )

                logger.info(
                    f"[{self.account_index}] | Claiming {bonded_balance_formatted:.6f} shMON | Tx: {EXPLORER_URL}{tx_hash.hex()}"
                )

                receipt = await self.web3.eth.wait_for_transaction_receipt(tx_hash)
                if receipt["status"] == 1:
                    logger.success(
                        f"[{self.account_index}] | Successfully claimed Shmon | Tx: {EXPLORER_URL}{tx_hash.hex()}"
                    )
                    return True
                else:
                    logger.error(f"[{self.account_index}] | Failed to claim Shmon")
                    return False

            except Exception as e:
                logger.error(f"[{self.account_index}] | Error unstaking Shmon: {e}")
                await asyncio.sleep(1)
                continue
        return False

    async def get_gas_params(self) -> Dict[str, int]:
        """Get current gas parameters from the network."""
        latest_block = await self.web3.eth.get_block("latest")
        base_fee = latest_block["baseFeePerGas"]
        max_priority_fee = await self.web3.eth.max_priority_fee

        # Calculate maxFeePerGas (base fee + priority fee)
        max_fee = base_fee + max_priority_fee

        return {
            "maxFeePerGas": max_fee,
            "maxPriorityFeePerGas": max_priority_fee,
        }

    # 估算交易所需的 gas 并添加一些缓冲。
    async def estimate_gas(self, transaction: dict) -> int:
        """Estimate gas for transaction and add some buffer."""
        try:
            estimated = await self.web3.eth.estimate_gas(transaction)
            # 为确保安全，在预估气体中添加 10%
            return int(estimated * 1.1)
        except Exception as e:
            logger.warning(
                f"[{self.account_index}] Error estimating gas: {e}. Using default gas limit"
            )
            raise e
