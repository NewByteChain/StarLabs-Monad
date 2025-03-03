import asyncio
import random

from loguru import logger

from src.model.disperse_from_one.instance import DisperseFromOneWallet
from src.model.disperse_one_one.instance import DisperseOneOne
import src.utils
from src.utils.logs import report_error, report_success
from src.utils.output import show_dev_info, show_logo
import src.model
from src.utils.statistics import print_wallets_stats

async def start():
    async def launch_wrapper(index, proxy, private_key, discord_token, email):
        async with semaphore:
            await account_flow(
                index,
                proxy,
                private_key,
                discord_token,
                email,
                config,
                lock,
            )

<<<<<<< HEAD
    show_logo() # 显示 logo
    show_dev_info() # 显示开发者信息
=======
    show_logo()
    show_dev_info()

    print("\nAvailable options:\n")
    print("[1] 😈 Start farm")
    print("[2] 🔧 Edit config")
    print("[3] 👋 Exit")
    print()

    try:
        choice = input("Enter option (1-3): ").strip()
    except Exception as e:
        logger.error(f"Input error: {e}")
        return

    if choice == "3" or not choice:
        return
    elif choice == "2":
        config_ui = src.utils.ConfigUI()
        config_ui.run()
        return
    elif choice == "1":
        pass
    else:
        logger.error(f"Invalid choice: {choice}")
        return

>>>>>>> dc9243634f530fa1057fbb3d5c377f27e959d0cc
    config = src.utils.get_config()

    # 读取代理配置文件
    proxies = src.utils.read_txt_file("proxies", "data/proxies.txt")
    if len(proxies) == 0:
        logger.error("No proxies found in data/proxies.txt")  # 没有设置代理信息
        return

    if "disperse_farm_accounts" in config.FLOW.TASKS:
        main_keys = src.utils.read_txt_file("private keys", "data/private_keys.txt")
        farm_keys = src.utils.read_txt_file("private keys", "data/keys_for_faucet.txt")
        disperse_one_one = DisperseOneOne(main_keys, farm_keys, proxies, config)
        await disperse_one_one.disperse()
        return
    elif "disperse_from_one_wallet" in config.FLOW.TASKS:
        main_keys = src.utils.read_txt_file("private keys", "data/private_keys.txt")
        farm_keys = src.utils.read_txt_file("private keys", "data/keys_for_faucet.txt")
        disperse_one_wallet = DisperseFromOneWallet(
            farm_keys[0], main_keys, proxies, config
        )
        await disperse_one_wallet.disperse()
        return

    if "farm_faucet" in config.FLOW.TASKS:
        private_keys = src.utils.read_txt_file(
            "private keys", "data/keys_for_faucet.txt"
        )
    else:
        private_keys = src.utils.read_txt_file("private keys", "data/private_keys.txt")

    # 定义帐户范围
    start_index = config.SETTINGS.ACCOUNTS_RANGE[0]
    end_index = config.SETTINGS.ACCOUNTS_RANGE[1]

    # 如果两者都为 0，请检查 EXACT_ACCOUNTS_TO_USE
    if start_index == 0 and end_index == 0:
        if config.SETTINGS.EXACT_ACCOUNTS_TO_USE:
            # 将帐号转换为索引（数字 - 1）
            selected_indices = [i - 1 for i in config.SETTINGS.EXACT_ACCOUNTS_TO_USE]
            accounts_to_process = [private_keys[i] for i in selected_indices]
            logger.info(
                f"Using specific accounts: {config.SETTINGS.EXACT_ACCOUNTS_TO_USE}"
            )

            # 为了与其他代码兼容
            start_index = min(config.SETTINGS.EXACT_ACCOUNTS_TO_USE)
            end_index = max(config.SETTINGS.EXACT_ACCOUNTS_TO_USE)
        else:
            # 如果列表为空，我们将像以前一样处理所有帐户
            accounts_to_process = private_keys
            start_index = 1
            end_index = len(private_keys)
    else:
        # Python 切片不包含最后一个元素，因此 +1
        accounts_to_process = private_keys[start_index - 1 : end_index]

<<<<<<< HEAD
    
    discord_tokens = [""] * len(accounts_to_process) # 为每个帐户准备 Discord 令牌
    emails = [""] * len(accounts_to_process) # 为每个帐户准备电子邮件
=======
    discord_tokens = [""] * len(accounts_to_process)
    emails = [""] * len(accounts_to_process)
>>>>>>> dc9243634f530fa1057fbb3d5c377f27e959d0cc

    threads = config.SETTINGS.THREADS  # 线程数

    # 我们为选定的账户准备代理
    cycled_proxies = [
        proxies[i % len(proxies)] for i in range(len(accounts_to_process))
    ]

    # 创建索引列表并对其进行打乱
    shuffled_indices = list(range(len(accounts_to_process)))
    random.shuffle(shuffled_indices)

    # 创建按帐户顺序排列的行
    account_order = " ".join(str(start_index + idx) for idx in shuffled_indices)
    logger.info(
        f"Starting with accounts {start_index} to {end_index} in random order..."
    )
    logger.info(f"Accounts order: {account_order}")

    lock = asyncio.Lock()
    semaphore = asyncio.Semaphore(value=threads)
    tasks = []

    # 使用随机索引创建任务
    for shuffled_idx in shuffled_indices:
        tasks.append(
            asyncio.create_task(
                launch_wrapper(
                    start_index + shuffled_idx,
                    cycled_proxies[shuffled_idx],
                    accounts_to_process[shuffled_idx],
                    discord_tokens[shuffled_idx],
                    emails[shuffled_idx],
                )
            )
        )

    await asyncio.gather(*tasks)

    logger.success("Saved accounts and private keys to a file.")

    print_wallets_stats(config)

# 单账户工作流程
async def account_flow(
    account_index: int,
    proxy: str,
    private_key: str,
    discord_token: str,
    email: str,
    config: src.utils.config.Config,
    lock: asyncio.Lock,
):
    try:
        pause = random.randint(
            config.SETTINGS.RANDOM_INITIALIZATION_PAUSE[0],
            config.SETTINGS.RANDOM_INITIALIZATION_PAUSE[1],
        )
        logger.info(f"[{account_index}] Sleeping for {pause} seconds before start...")
        await asyncio.sleep(pause)

        report = False
        #  选择要运行的模型
        instance = src.model.Start(
            account_index, proxy, private_key, discord_token, email, config
        )
        # 初始化账户客户端
        result = await wrapper(instance.initialize, config)
        if not result:
            report = True
        # 执行工作流程
        result = await wrapper(instance.flow, config)
        if not result:
            report = True

        if report:
            await report_error(lock, private_key, proxy, discord_token)
        else:
            await report_success(lock, private_key, proxy, discord_token)

        pause = random.randint(
            config.SETTINGS.RANDOM_PAUSE_BETWEEN_ACCOUNTS[0],
            config.SETTINGS.RANDOM_PAUSE_BETWEEN_ACCOUNTS[1],
        )
        logger.info(f"Sleeping for {pause} seconds before next account...")
        await asyncio.sleep(pause)

    except Exception as err:
        logger.error(f"{account_index} | Account flow failed: {err}")


async def wrapper(function, config: src.utils.config.Config, *args, **kwargs):
    attempts = config.SETTINGS.ATTEMPTS
    for attempt in range(attempts):
        result = await function(*args, **kwargs)
        if isinstance(result, tuple) and result and isinstance(result[0], bool): # 如果返回的是元组，且第一个元素是布尔值
            if result[0]:
                return result
        elif isinstance(result, bool): # 如果返回的是布尔值
            if result:
                return True

        if attempt < attempts - 1:  # 最后一次尝试后不要休眠
            pause = random.randint(
                config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.info(
                f"Sleeping for {pause} seconds before next attempt {attempt+1}/{config.SETTINGS.ATTEMPTS}..."
            )
            await asyncio.sleep(pause)

    return result


def task_exists_in_config(task_name: str, tasks_list: list) -> bool:
    """递归检查任务列表中是否存在任务，包括嵌套列表"""
    for task in tasks_list:
        if isinstance(task, list):
            if task_exists_in_config(task_name, task):
                return True
        elif task == task_name:
            return True
    return False
