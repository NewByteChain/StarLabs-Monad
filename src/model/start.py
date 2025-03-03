from loguru import logger
import primp
import random
import asyncio

from src.model.testnet_bridge.instance import TestnetBridge
from src.model.memebridge.instance import Memebridge
from src.model.dusted.instance import Dusted
from src.model.aircraft.instance import Aircraft
from src.model.magiceden.instance import MagicEden
from src.model.monadking_mint.instance import Monadking
from src.model.demask_mint.instance import Demask
from src.model.lilchogstars_mint.instance import Lilchogstars
from src.model.kintsu.instance import Kintsu
from src.model.orbiter.instance import Orbiter
from src.model.accountable.instance import Accountable
from src.model.shmonad.instance import Shmonad
from src.model.gaszip.instance import Gaszip
from src.model.monadverse_mint.instance import MonadverseMint
from src.model.bima.instance import Bima
from src.model.owlto.instance import Owlto
from src.model.magma.instance import Magma
from src.model.apriori import Apriori
from src.model.monad_xyz.instance import MonadXYZ
from src.model.nad_domains.instance import NadDomains
from src.utils.client import create_client
from src.utils.config import Config
from src.model.help.stats import WalletStats


class Start:
    def __init__(
        self,
        account_index: int,
        proxy: str,
        private_key: str,
        discord_token: str,
        email: str,
        config: Config,
    ):
        self.account_index = account_index
        self.proxy = proxy
        self.private_key = private_key
        self.discord_token = discord_token
        self.email = email
        self.config = config

        self.session: primp.AsyncClient | None = None

    # 初始化账户客户端
    async def initialize(self): 
        try:
            self.session = await create_client(self.proxy)

            return True
        except Exception as e:
            logger.error(f"[{self.account_index}] | Error: {e}")
            return False

    # 执行账户工作流程
    async def flow(self):
        try:
            monad = MonadXYZ(
                self.account_index,
                self.proxy,
                self.private_key,
                self.discord_token,
                self.config,
                self.session,
            )

            if "farm_faucet" in self.config.FLOW.TASKS:
                await monad.faucet()
                return True

            # 我们提前定义所有任务
            planned_tasks = []
            task_plan_msg = []
            task_index = 1  # Initialize a single counter for all tasks

            for task_item in self.config.FLOW.TASKS:
                if isinstance(task_item, list):
                    # For tasks in square brackets [], randomly select one
                    selected_task = random.choice(task_item)
                    planned_tasks.append((task_index, selected_task, "random_choice"))
                    task_plan_msg.append(f"{task_index}. {selected_task}")
                    task_index += 1
                elif isinstance(task_item, tuple):
                    # For tasks in parentheses (), shuffle and execute all
                    shuffled_tasks = list(task_item)
                    random.shuffle(shuffled_tasks)

                    # Add each shuffled task individually to the plan
                    for subtask in shuffled_tasks:
                        planned_tasks.append((task_index, subtask, "shuffled_item"))
                        task_plan_msg.append(f"{task_index}. {subtask}")
                        task_index += 1
                else:
                    planned_tasks.append((task_index, task_item, "single"))
                    task_plan_msg.append(f"{task_index}. {task_item}")
                    task_index += 1

            # 在一条消息中输出执行计划
            logger.info(
                f"[{self.account_index}] Task execution plan: {' | '.join(task_plan_msg)}"
            )

            # Выполняем задачи по плану
            for i, task, task_type in planned_tasks:
                logger.info(f"[{self.account_index}] Executing task {i}: {task}")
                await self.execute_task(task, monad)
                await self.sleep(task)

            return True
        except Exception as e:
            # import traceback
            # traceback.print_exc()
            logger.error(f"[{self.account_index}] | Error: {e}")
            return False


    async def execute_task(self, task, monad):
        """Execute a single task"""
        task = task.lower()

        if task == "faucet":  # 领水龙头
            await monad.faucet()

        elif task == "swaps":  # 以下是swap交易操作
            await monad.swaps(type="swaps")

        elif task == "ambient":
            await monad.swaps(type="ambient")

        elif task == "bean":
            await monad.swaps(type="bean")

        elif task == "izumi":
            await monad.swaps(type="izumi")

        elif task == "collect_all_to_monad":
            await monad.swaps(type="collect_all_to_monad")

        elif task == "gaszip":
            gaszip = Gaszip(
                self.account_index,
                self.proxy,
                self.private_key,
                self.config,
            )
            await gaszip.refuel()  # 加油交易（发送：Arbitrum、Optimism、Base给这个地址0x391E7C679d29bD940d63be94AD22A25d25b5A604）

        elif task == "memebridge":
            memebridge = Memebridge(
                self.account_index,
                self.proxy,
                self.private_key,
                self.config,
            )
            await memebridge.refuel() 

        elif task == "apriori":
            apriori = Apriori(
                self.account_index,
                self.proxy,
                self.private_key,
                self.config,
                self.session,
            )
            await apriori.stake_mon()  # apriori 质押 MON ，质押地址（0xb2f82D0f38dc453D596Ad40A37799446Cc89274A），未验证该合约地址的有效性

        elif task == "magma":
            magma = Magma(
                self.account_index,
                self.proxy,
                self.private_key,
                self.config,
                self.session,
            )
            await magma.stake_mon() # magma 质押 MON , 质押地址（0x2c9C959516e9AAEdB2C748224a41249202ca8BE7），未验证该合约地址的有效性

        elif task == "owlto":
            owlto = Owlto(
                self.account_index,
                self.proxy,
                self.private_key,
                self.config,
                self.session,
            )
            await owlto.deploy_contract() # 部署 Owlto 合约，需要更改成自己的合约字节码（在配置文件中 owlto/constants.py）

        elif task == "bima":
            bima = Bima(
                self.account_index,
                self.proxy,
                self.private_key,
                self.config,
                self.session,
            )
            await bima.get_faucet_tokens()  # 调用了合约（貌似是一个借贷合约），faucet操作
            await self.sleep("bima_faucet") # 随机停顿，停顿时间在配置文件中完成了配置

            if self.config.BIMA.LEND: # 是否借贷
                await bima.lend() # 借贷操作

        elif task == "monadverse_mint":
            monadverse_mint = MonadverseMint(
                self.account_index,
                self.proxy,
                self.private_key,
                self.config,
                self.session,
            )
            await monadverse_mint.mint()  # Mint Monadverse NFT

        elif task == "shmonad":
            shmonad = Shmonad(
                self.account_index,
                self.proxy,
                self.private_key,
                self.config,
                self.session,
            )
            await shmonad.swaps() # Swap shMON质押与解除质押交互，涉及买&卖swap shMON操作，可配置化的复杂（质押&解除质押）交互操作

        elif task == "accountable":
            accountable = Accountable(
                self.account_index,
                self.proxy,
                self.private_key,
                self.config,
                self.session,
            )
            await accountable.mint()   # game.accountable.capital 1-8号NFT mint，每个账户每个id的NFT mint限制mint数量配置文件有配置

        elif task == "orbiter":
            orbiter = Orbiter(
                self.account_index,
                self.proxy,
                self.private_key,
                self.config,
                self.session,
            )
            await orbiter.bridge()  # 跨桥链，默认10%-20%资金桥接，可配置全仓桥接（95%）仓位ETH进行垮桥链接。"orbiter"-通过 Orbiter 将 ETH 从 Sepolia 桥接到 Monad

        elif task == "testnet_bridge":
            testnet_bridge = TestnetBridge(
                self.account_index,
                self.proxy,
                self.private_key,
                self.config,
                self.session,
            )
            await testnet_bridge.execute()  

        elif task == "logs":
            wallet_stats = WalletStats(self.config)
            await wallet_stats.get_wallet_stats(self.private_key, self.account_index)  # 将钱包统计信息保存到配置中，用于事后分析（反向验证脚本可用性）

        elif task == "nad_domains":
            nad_domains = NadDomains(
                self.account_index,
                self.proxy,
                self.private_key,
                self.config,
                self.session,
            )
            await nad_domains.register_random_domain()  # 注册随机域名

        elif task == "kintsu":
            kintsu = Kintsu(
                self.account_index,
                self.proxy,
                self.private_key,
                self.config,
                self.session,
            )
            await kintsu.stake_mon()  # 【慎用】配置文件质押金额【0.01, 0.02】之间，一次性任务可考虑交互，kintsu上面质押MON，这里只有质押操作，没有解除质押操作

        elif task == "lilchogstars":
            lilchogstars = Lilchogstars(
                self.account_index,
                self.proxy,
                self.private_key,
                self.config,
                self.session,
            )
            await lilchogstars.mint()  # mint NFT，需要验证合约地址的有效性

        elif task == "demask":
            demask = Demask(
                self.account_index,
                self.proxy,
                self.private_key,
                self.config,
                self.session,
            )
            await demask.mint()   # mint NFT，需要验证合约地址的有效性

        elif task == "monadking":
            monadking = Monadking(
                self.account_index,
                self.private_key,
                self.config,
            )
            await monadking.mint()  # mint NFT，需要验证合约地址的有效性

        elif task == "monadking_unlocked":
            monadking_unlocked = Monadking(
                self.account_index,
                self.private_key,
                self.config,
            )
            await monadking_unlocked.mint_unlocked()   # monadking unlocked，mint NFT

        elif task == "magiceden":
            magiceden = MagicEden(
                self.account_index,
                self.config,
                self.private_key,
                self.session,
            )
            await magiceden.mint()  # magiceden，mint NFT

        elif task == "aircraft":
            aircraft = Aircraft(
                self.account_index,
                self.proxy,
                self.private_key,
                self.config,
                self.session,
            )
            await aircraft.execute()

        elif task == "dusted":
            dusty = Dusted(
                self.account_index,
                self.proxy,
                self.private_key,
                self.config,
                self.session,
            )
            await dusty.execute()

    async def sleep(self, task_name: str):
        """在动作之间随机暂停"""
        pause = random.randint(
            self.config.SETTINGS.RANDOM_PAUSE_BETWEEN_ACTIONS[0],
            self.config.SETTINGS.RANDOM_PAUSE_BETWEEN_ACTIONS[1],
        )
        logger.info(
            f"[{self.account_index}] Sleeping {pause} seconds after {task_name}"
        )
        await asyncio.sleep(pause)
