from web3 import AsyncWeb3
from eth_account import Account
from typing import Dict, Optional, List, Tuple
from decimal import Decimal
import random
import asyncio
from loguru import logger
from src.utils.config import Config
from src.model.gaszip.constants import (
    GASZIP_RPCS, 
    REFUEL_ADDRESS, 
    REFUEL_CALLLDATA,
    GASZIP_EXPLORERS
)
from src.utils.constants import RPC_URL


class Gaszip:
    def __init__(
        self,
        account_index: int,
        proxy: str,
        private_key: str,
        config: Config,
    ):
        self.account_index = account_index
        self.proxy = proxy
        self.private_key = private_key
        self.config = config
        self.account = Account.from_key(private_key)
        self.monad_web3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(RPC_URL))
        
    # 获取原生 MON 余额。
    async def get_monad_balance(self) -> float:
        """Get native MON balance."""
        try:
            balance_wei = await self.monad_web3.eth.get_balance(self.account.address)
            return float(self.monad_web3.from_wei(balance_wei, 'ether'))
        except Exception as e:
            logger.error(f"[{self.account_index}] Failed to get MON balance: {str(e)}")
            return 0

    # 获取特定网络的本机代币余额。
    async def get_native_balance(self, network: str) -> float:
        """Get native token balance for a specific network."""
        try:
            web3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(GASZIP_RPCS[network]))
            balance_wei = await web3.eth.get_balance(self.account.address)
            return float(web3.from_wei(balance_wei, 'ether'))
        except Exception as e:
            logger.error(f"[{self.account_index}] Failed to get balance for {network}: {str(e)}")
            return 0

    # 加油后等待MON余额增加。
    async def wait_for_balance_increase(self, initial_balance: float) -> bool:
        """Wait for MON balance to increase after refuel."""
        # 使用配置中的超时
        timeout = self.config.GASZIP.MAX_WAIT_TIME
        
        logger.info(f"[{self.account_index}] Waiting for balance to increase (max wait time: {timeout} seconds)...")
        start_time = asyncio.get_event_loop().time()
        
        # 每 5 秒检查一次余额，直至超时
        while asyncio.get_event_loop().time() - start_time < timeout:
            current_balance = await self.get_monad_balance()
            if current_balance > initial_balance:
                logger.success(
                    f"[{self.account_index}] Balance increased from {initial_balance} to {current_balance} MON"
                )
                return True
            
            # 每 15 秒记录一次进度
            elapsed = int(asyncio.get_event_loop().time() - start_time)
            if elapsed % 15 == 0:
                logger.info(f"[{self.account_index}] Still waiting for balance to increase... ({elapsed}/{timeout} seconds)")
            
            await asyncio.sleep(5)
        
        logger.error(f"[{self.account_index}] Balance didn't increase after {timeout} seconds")
        return False

    # 检查各个网络的余额并返回具有足够余额的随机网络。
    # 如果未找到合适的网络，则返回 (network_name, amount_to_refuel) 的元组或 None。
    async def get_balances(self) -> Optional[Tuple[str, float]]:
        """
        Check balances across networks and return a random network with sufficient balance.
        Returns tuple of (network_name, amount_to_refuel) or None if no suitable network found.
        """
        try:
            # 首先检查当前 MON 余额是否足够
            current_mon_balance = await self.get_monad_balance()
            logger.info(f"[{self.account_index}] Current MON balance: {current_mon_balance}")
            
            if current_mon_balance >= self.config.GASZIP.MINIMUM_BALANCE_TO_REFUEL:
                logger.info(
                    f"[{self.account_index}] Current balance ({current_mon_balance}) is above minimum "
                    f"({self.config.GASZIP.MINIMUM_BALANCE_TO_REFUEL}), skipping refuel"
                )
                return None
            
            eligible_networks = []
            # 随机选择加油金额（随机范围在配置文件中抽取）
            amount_to_refuel = random.uniform(
                self.config.GASZIP.AMOUNT_TO_REFUEL[0],
                self.config.GASZIP.AMOUNT_TO_REFUEL[1]
            )
            
            logger.info(f"[{self.account_index}] Checking balances for refueling {amount_to_refuel} MON")
            # 检查各个网络是否存在原生代币余额（Arbitrum、Optimism、Base），并且找到余额足够的网络
            for network in self.config.GASZIP.NETWORKS_TO_REFUEL_FROM:
                balance = await self.get_native_balance(network)
                logger.info(f"[{self.account_index}] {network} balance: {balance}")
                # 如果余额足够，将网络添加到 eligible_networks 列表中
                if balance > amount_to_refuel:
                    eligible_networks.append(network)
            
            if not eligible_networks:
                logger.warning(f"[{self.account_index}] No networks with sufficient balance found")
                return None
            
            selected_network = random.choice(eligible_networks) # 随机选择一个网络
            logger.info(f"[{self.account_index}] Selected {selected_network} for refueling")
            
            # 返回一个符合条件的网络和加油金额
            return (selected_network, amount_to_refuel)
            
        except Exception as e:
            logger.error(f"[{self.account_index}] Error checking balances: {str(e)}")
            return None

    # 获取交易的 gas 参数。
    async def get_gas_params(self, web3: AsyncWeb3) -> Dict[str, int]:
        """Get gas parameters for transaction."""
        latest_block = await web3.eth.get_block('latest')
        base_fee = latest_block['baseFeePerGas']
        max_priority_fee = await web3.eth.max_priority_fee
        max_fee = int((base_fee + max_priority_fee) * 1.5)
        
        return {
            "maxFeePerGas": max_fee,
            "maxPriorityFeePerGas": max_priority_fee,
        }
    
    # 执行加油交易。
    async def refuel(self) -> bool:
        """Execute the refueling transaction."""
        try:
            # 检查各个网络是否存在原生代币余额（Arbitrum、Optimism、Base）
            network_info = await self.get_balances() 
            if not network_info:
                return False
                
            network, amount = network_info
            web3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(GASZIP_RPCS[network]))
            
            # 如果我们要等待 MON 余额增加，请获取初始余额
            initial_balance = 0
            if self.config.GASZIP.WAIT_FOR_FUNDS_TO_ARRIVE:
                initial_balance = await self.get_monad_balance() 
                logger.info(f"[{self.account_index}] Initial MON balance: {initial_balance}")
            
            # Prepare transaction
            amount_wei = web3.to_wei(amount, 'ether')
            nonce = await web3.eth.get_transaction_count(self.account.address)  # 随机数
            gas_params = await self.get_gas_params(web3) # 获取交易的 gas 参数。
            
            # 预估gas
            gas_estimate = await web3.eth.estimate_gas({
                'from': self.account.address,
                'to': REFUEL_ADDRESS,  
                'value': amount_wei,
                'data': REFUEL_CALLLDATA,
            })
            
            tx = {
                'from': self.account.address,
                'to': REFUEL_ADDRESS, # 加油地址发送到外部地址
                'value': amount_wei,
                'data': REFUEL_CALLLDATA,
                'nonce': nonce,
                'gas': int(gas_estimate * 1.1),  # Add 10% buffer to gas estimate
                'chainId': await web3.eth.chain_id,
                **gas_params
            }
            
            # Sign and send transaction
            signed_tx = web3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = await web3.eth.send_raw_transaction(signed_tx.raw_transaction)
            
            logger.info(f"[{self.account_index}] Waiting for refuel transaction confirmation...")
            receipt = await web3.eth.wait_for_transaction_receipt(tx_hash)
            
            explorer_url = f"{GASZIP_EXPLORERS[network]}{tx_hash.hex()}"
            
            if receipt['status'] == 1:
                logger.success(f"[{self.account_index}] Refuel transaction successful! Explorer URL: {explorer_url}")
                
                # 如果配置为等待余额增加
                if self.config.GASZIP.WAIT_FOR_FUNDS_TO_ARRIVE:
                    logger.success(f"[{self.account_index}] Waiting for balance increase...")
                    if await self.wait_for_balance_increase(initial_balance):
                        logger.success(f"[{self.account_index}] Successfully refueled from {network}")
                        return True
                    logger.warning(f"[{self.account_index}] Balance didn't increase, but transaction was successful")
                    return True
                else:
                    logger.success(f"[{self.account_index}] Successfully refueled from {network} (not waiting for balance)")
                    return True
            else:
                logger.error(f"[{self.account_index}] Refuel transaction failed! Explorer URL: {explorer_url}")
                return False
                
        except Exception as e:
            logger.error(f"[{self.account_index}] Refuel failed: {str(e)}")
            return False
