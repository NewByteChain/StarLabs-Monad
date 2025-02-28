from tabulate import tabulate
from typing import List, Optional
from loguru import logger

from src.utils.config import Config, WalletInfo


def print_wallets_stats(config: Config):
    """
    在表格中显示所有钱包的统计信息
    """
    try:
        # 按索引对钱包进行排序
        sorted_wallets = sorted(config.WALLETS.wallets, key=lambda x: x.account_index)

        # 准备表格数据
        table_data = []
        total_balance = 0
        total_transactions = 0

        for wallet in sorted_wallets:
            # 屏蔽私钥（最后 5 个字符）
            masked_key = "•" * 3 + wallet.private_key[-5:]

            total_balance += wallet.balance
            total_transactions += wallet.transactions

            row = [
                str(wallet.account_index),  # 只是一个没有前导零的数字。
                wallet.address,  # 详细地址
                masked_key,
                f"{wallet.balance:.4f} MON",
                f"{wallet.transactions:,}",  # 使用分隔符格式化数字
            ]
            table_data.append(row)

        # 如果有数据，我们将显示表格和统计数据
        if table_data:
            # 让我们为表格创建标题
            headers = [
                "№ Account",
                "Wallet Address",
                "Private Key",
                "Balance (MON)",
                "Total Txs",
            ]

            # 形成具有改进格式的表格
            table = tabulate(
                table_data,
                headers=headers,
                tablefmt="double_grid",  # Более красивые границы
                stralign="center",  # 居中线
                numalign="center",  # 居中数字
            )

            # 我们计算平均值
            wallets_count = len(sorted_wallets)
            avg_balance = total_balance / wallets_count
            avg_transactions = total_transactions / wallets_count

            # 我们输出表格和统计数据
            logger.info(
                f"\n{'='*50}\n"
                f"         Wallets Statistics ({wallets_count} wallets)\n"
                f"{'='*50}\n"
                f"{table}\n"
                f"{'='*50}\n"
                f"{'='*50}"
            )

            logger.info(f"Average balance: {avg_balance:.4f} MON")
            logger.info(f"Average transactions: {avg_transactions:.1f}")
            logger.info(f"Total balance: {total_balance:.4f} MON")
            logger.info(f"Total transactions: {total_transactions:,}")
        else:
            logger.info("\nNo wallet statistics available")

    except Exception as e:
        logger.error(f"Error while printing statistics: {e}")
