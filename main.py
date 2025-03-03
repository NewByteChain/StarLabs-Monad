from loguru import logger
import urllib3
import sys
import asyncio

from process import start

import asyncio
import platform

<<<<<<< HEAD
if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy()) # 修复 Windows 下运行时出现的错误
=======
# if platform.system() == "Windows":
#     asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
>>>>>>> dc9243634f530fa1057fbb3d5c377f27e959d0cc


async def main():
    configuration()
    await start()

<<<<<<< HEAD
# 配置日志记录器
=======

log_format = (
    "<light-blue>[</light-blue><yellow>{time:HH:mm:ss}</yellow><light-blue>]</light-blue> | "
    "<level>{level: <8}</level> | "
    "<cyan>{file}:{line}</cyan> | "
    "<level>{message}</level>"
)

>>>>>>> dc9243634f530fa1057fbb3d5c377f27e959d0cc
def configuration():
    urllib3.disable_warnings()  # 禁用警告
    logger.remove() # 移除默认的日志记录器
    logger.add(
        sys.stdout,
        colorize=True,
        format=log_format,
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
