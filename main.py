from loguru import logger
import urllib3
import sys
import asyncio

from process import start

import asyncio
import platform

if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy()) # 修复 Windows 下运行时出现的错误


async def main():
    configuration()
    await start()

# 配置日志记录器
def configuration():
    urllib3.disable_warnings()  # 禁用警告
    logger.remove() # 移除默认的日志记录器
    logger.add(
        sys.stdout,
        colorize=True,
        format="<light-cyan>{time:HH:mm:ss}</light-cyan> | <level>{level: <8}</level> | <fg #ffffff>{name}:{line}</fg #ffffff> - <bold>{message}</bold>",
    )
    logger.add(
        "logs/app.log",
        rotation="10 MB",
        retention="1 month",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{line} - {message}",
        level="INFO",
    )


if __name__ == "__main__":
    asyncio.run(main())
