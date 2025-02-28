from web3 import AsyncWeb3
from eth_account import Account
import asyncio
from typing import Dict, Optional, List, Tuple
from eth_abi import abi
from decimal import Decimal
from src.utils.constants import RPC_URL, EXPLORER_URL, ERC20_ABI
from src.model.monad_xyz.constants import AMBIENT_ABI, AMBIENT_TOKENS, AMBIENT_CONTRACT, ZERO_ADDRESS, POOL_IDX, RESERVE_FLAGS, TIP, MAX_SQRT_PRICE, MIN_SQRT_PRICE
from loguru import logger
import random
from src.utils.config import Config

    
class AmbientDex:
    def __init__(self, private_key: str, proxy: Optional[str] = None, config: Config = None):
        self.web3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(RPC_URL))
        self.account = Account.from_key(private_key)
        self.proxy = proxy
        self.router_contract = self.web3.eth.contract(
            address=self.web3.to_checksum_address(AMBIENT_CONTRACT),
            abi=AMBIENT_ABI
        )
        self.config = config

    async def get_gas_params(self) -> Dict[str, int]:
        latest_block = await self.web3.eth.get_block('latest') # 获取最新区块
        base_fee = latest_block['baseFeePerGas'] # 基础费用
        max_priority_fee = await self.web3.eth.max_priority_fee # 最高优先级费用
        max_fee = base_fee + max_priority_fee
        
        return {
            "maxFeePerGas": max_fee,
            "maxPriorityFeePerGas": max_priority_fee,
        }

    # 根据代币小数将金额转换为wei。
    def convert_to_wei(self, amount: float, token: str) -> int:
        """Convert amount to wei based on token decimals."""
        if token == "native":
            return self.web3.to_wei(amount, 'ether')
        decimals = AMBIENT_TOKENS[token.lower()]["decimals"]
        return int(Decimal(str(amount)) * Decimal(str(10 ** decimals)))

    # 将 wei 数量转换回代币单位。
    def convert_from_wei(self, amount: int, token: str) -> float:
        """Convert wei amount back to token units."""
        if token == "native":
            return float(self.web3.from_wei(amount, 'ether'))
        decimals = AMBIENT_TOKENS[token.lower()]["decimals"]
        return float(Decimal(str(amount)) / Decimal(str(10 ** decimals)))
    
    # 获取余额非零的代币列表，包括原生代币。
    async def get_tokens_with_balance(self) -> List[Tuple[str, float]]:
        """Get list of tokens with non-zero balances, including native token."""
        tokens_with_balance = []
        
        # 检查原生代币余额
        native_balance = await self.web3.eth.get_balance(self.account.address)
        if native_balance > 0:
            native_amount = float(self.web3.from_wei(native_balance, 'ether'))
            tokens_with_balance.append(("native", native_amount))
        
        # 检查其他代币余额
        for token in AMBIENT_TOKENS:
            try:
                token_contract = self.web3.eth.contract(
                    address=self.web3.to_checksum_address(AMBIENT_TOKENS[token]["address"]),
                    abi=ERC20_ABI
                )
                balance = await token_contract.functions.balanceOf(self.account.address).call()
                
                if balance > 0:
                    decimals = AMBIENT_TOKENS[token]["decimals"]
                    amount = float(Decimal(str(balance)) / Decimal(str(10 ** decimals)))
                    
                    # 余额较低时跳过 SETH 和 WETH
                    if token.lower() in ["seth", "weth"] and amount < 0.001:
                        # logger.info(f"Skipping {token} with low balance ({amount}) for potential swaps")
                        continue
                        
                    tokens_with_balance.append((token, amount))
                
            except Exception as e:
                logger.error(f"Failed to get balance for {token}: {str(e)}")
                continue
        
        return tokens_with_balance
    
    # 为 Ambient DEX 生成交换交易数据。
    async def generate_swap_data(self, token_in: str, token_out: str, amount_in_wei: int) -> Dict:
        """Generate swap transaction data for Ambient DEX."""
        try:
            is_native = token_in == "native"
            
            # 根据代币符号获取代币地址
            token_address = (
                AMBIENT_TOKENS[token_out.lower()]["address"] if is_native 
                else AMBIENT_TOKENS[token_in.lower()]["address"]
            )
            
            # 对交换参数进行编码
            encode_data = abi.encode(
                ['address', 'address', 'uint16', 'bool', 'bool', 'uint256', 'uint8', 'uint256', 'uint256', 'uint8'],
                [
                    ZERO_ADDRESS,
                    self.web3.to_checksum_address(token_address),
                    POOL_IDX,
                    is_native,
                    is_native,
                    amount_in_wei,
                    TIP,
                    MAX_SQRT_PRICE if is_native else MIN_SQRT_PRICE,
                    0,
                    RESERVE_FLAGS
                ]
            )
            
            # 为 userCmd 生成函数选择器
            function_selector = self.web3.keccak(text="userCmd(uint16,bytes)")[:4]
            
            # 对 userCmd 的参数进行编码
            cmd_params = abi.encode(['uint16', 'bytes'], [1, encode_data])
            
            # 组合函数选择器和参数
            tx_data = function_selector.hex() + cmd_params.hex()

            # Estimate gas
            gas_estimate = await self.web3.eth.estimate_gas({
                'to': AMBIENT_CONTRACT,
                'from': self.account.address,
                'data': '0x' + tx_data,
                'value': amount_in_wei if is_native else 0
            })

            return {
                "to": AMBIENT_CONTRACT,
                "data": '0x' + tx_data,
                "value": amount_in_wei if is_native else 0,
                "gas": int(gas_estimate * 1.1)  # Add 10% buffer
            }

        except Exception as e:
            logger.error(f"Failed to generate Ambient swap data: {str(e)}")
            raise

    # 执行交易并等待确认。
    async def execute_transaction(self, tx_data: Dict) -> str:
        """Execute a transaction and wait for confirmation."""
        nonce = await self.web3.eth.get_transaction_count(self.account.address)
        gas_params = await self.get_gas_params()
        
        transaction = {
            "from": self.account.address,
            "nonce": nonce,
            "type": 2,
            "chainId": 10143,
            **tx_data,
            **gas_params,
        }

        signed_txn = self.web3.eth.account.sign_transaction(transaction, self.account.key)
        tx_hash = await self.web3.eth.send_raw_transaction(signed_txn.raw_transaction)
        
        logger.info("等待交易确认...")
        receipt = await self.web3.eth.wait_for_transaction_receipt(tx_hash, poll_latency=2)
        
        if receipt['status'] == 1:
            logger.success(f"交易成功！浏览器 URL: {EXPLORER_URL}{tx_hash.hex()}")
        else:
            logger.error(f"交易失败！浏览器 URL: {EXPLORER_URL}{tx_hash.hex()}")
            raise Exception("Transaction failed")
        return tx_hash.hex()
    
    # 批准 Ambient DEX 的代币支出。
    async def approve_token(self, token: str, amount: int) -> str:
        """Approve token spending for Ambient DEX."""
        try:
            token_contract = self.web3.eth.contract(
                address=self.web3.to_checksum_address(AMBIENT_TOKENS[token.lower()]["address"]),
                abi=ERC20_ABI
            )
            
            # Check current allowance
            current_allowance = await token_contract.functions.allowance(
                self.account.address,
                AMBIENT_CONTRACT
            ).call()
            
            if current_allowance >= amount:
                logger.info(f"Allowance sufficient for {token}")
                return None
            
            # 准备批准交易
            nonce = await self.web3.eth.get_transaction_count(self.account.address)
            gas_params = await self.get_gas_params()
            
            approve_tx = await token_contract.functions.approve(
                AMBIENT_CONTRACT,
                amount
            ).build_transaction({
                'from': self.account.address,
                'nonce': nonce,
                'type': 2,
                'chainId': 10143,
                **gas_params,
            })
            
            # Sign and send transaction
            signed_txn = self.web3.eth.account.sign_transaction(approve_tx, self.account.key)
            tx_hash = await self.web3.eth.send_raw_transaction(signed_txn.raw_transaction)
            
            logger.info(f"Waiting for {token} approval confirmation...")
            receipt = await self.web3.eth.wait_for_transaction_receipt(tx_hash, poll_latency=2)
            
            if receipt['status'] == 1:
                logger.success(f"Approval successful! Explorer URL: {EXPLORER_URL}{tx_hash.hex()}")
                return tx_hash.hex()
            else:
                raise Exception(f"Approval failed for {token}")
            
        except Exception as e:
            logger.error(f"Failed to approve {token}: {str(e)}")
            raise

    async def swap(self, percentage_to_swap: float, type: str) -> str:
        """Execute swap on Ambient DEX."""
        try:
            # 获取有实际余额的代币
            tokens_with_balance = await self.get_tokens_with_balance()
            
            if not tokens_with_balance:
                raise ValueError("No tokens with balance found to swap")
            
            if type == "collect":
                # 过滤掉原生 token，因为我们正在收集它
                tokens_to_swap = [(t, b) for t, b in tokens_with_balance if t != "native"]
                if not tokens_to_swap:
                    logger.info("No tokens to collect to native")
                    return None
                
                # 将所有代币兑换为原生代币
                for token_in, balance in tokens_to_swap:
                    try:
                        decimals = AMBIENT_TOKENS[token_in.lower()]["decimals"]
                        
                        # SETH 代币的特殊处理
                        if token_in.lower() == "seth":
                            # 留下 0.00001 到 0.0001 之间的一小笔随机数
                            leave_amount = random.uniform(0.00001, 0.0001)
                            balance = balance - leave_amount
                        
                        amount_wei = int(Decimal(str(balance)) * Decimal(str(10 ** decimals)))
                        
                        # 批准代币支出
                        await self.approve_token(token_in, amount_wei)
                        random_pause = random.randint(
                            self.config.SETTINGS.PAUSE_BETWEEN_SWAPS[0],
                            self.config.SETTINGS.PAUSE_BETWEEN_SWAPS[1],
                        )
                        logger.info(f"Swapping {balance} {token_in} to MON. Sleeping {random_pause} seconds after approve")
                        await asyncio.sleep(random_pause)
                        
                        logger.info(f"Collecting {balance} {token_in} to native")
                        
                        # 生成并执行掉期交易
                        tx_data = await self.generate_swap_data(token_in, "native", amount_wei)
                        tx_hash = await self.execute_transaction(tx_data)
                        
                        # 交换之间等待
                        if token_in != tokens_to_swap[-1][0]:  # If not the last token
                            await asyncio.sleep(random.randint(5, 10))
                    except Exception as e:
                        logger.error(f"Failed to collect {token_in} to native: {str(e)}")
                        continue
                
                return "Collection complete"
                
            else:  # Regular swap
                # 选择随机代币，使用余额作为输入代币
                token_in, balance = random.choice(tokens_with_balance)
                
                # 获取可用的输出 token（不包括输入 token）
                available_out_tokens = list(AMBIENT_TOKENS.keys()) + ["native"]   # usdt等稳定币token
                available_out_tokens.remove(token_in)
                token_out = random.choice(available_out_tokens)
            
            # 根据我们是否从原生应用进行交换来计算金额
            if token_in == "native":
                # 对于原生代币，应用百分比
                balance_wei = self.web3.to_wei(balance, 'ether')
                percentage = Decimal(str(percentage_to_swap)) / Decimal('100')
                amount_wei = int(Decimal(str(balance_wei)) * percentage)
                amount_token = float(self.web3.from_wei(amount_wei, 'ether'))
            else:
                # 对于其他代币，请使用全额余额
                decimals = AMBIENT_TOKENS[token_in.lower()]["decimals"]
                balance_decimal = Decimal(str(balance))
                
                # 对 SETH 的特殊处理 - 只留下少量随机数
                if token_in.lower() == "seth":
                    leave_amount = random.uniform(0.00001, 0.0001)
                    balance_decimal = balance_decimal - Decimal(str(leave_amount))
                
                amount_wei = int(balance_decimal * Decimal(str(10 ** decimals)))
                amount_token = float(balance_decimal)
                
                # 批准代币支出（如果不是本地）
                await self.approve_token(token_in, amount_wei)
                await asyncio.sleep(random.randint(5, 10))
            
            logger.info(f"Swapping {amount_token} {token_in} to {token_out}")
            
            # 创建 swap 交易
            tx_data = await self.generate_swap_data(token_in, token_out, amount_wei)
            
            # 执行交易
            return await self.execute_transaction(tx_data)

        except Exception as e:
            logger.error(f"Ambient swap failed: {str(e)}")
            raise
        