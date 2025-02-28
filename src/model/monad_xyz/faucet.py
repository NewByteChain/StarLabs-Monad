import asyncio
import secrets
import random
import primp
from loguru import logger
from src.model.help import Capsolver
from src.utils.config import Config
from eth_account import Account


async def faucet(
    session: primp.AsyncClient,
    account_index: int,
    config: Config,
    wallet: Account,
) -> bool:
    for retry in range(config.SETTINGS.ATTEMPTS):
        try:
            # 初始化验证码解决器
            solver = Capsolver(
                config.FAUCET.CAPSOLVER_API_KEY,
                config.FAUCET.PROXY_FOR_CAPTCHA,
                session,
            )
            for _ in range(3):
                # 解决 Cloudflare Turnstile 验证码并返回令牌
                result = await solver.solve_turnstile(
                    "0x4AAAAAAA-3X4Nd7hf3mNGx",
                    "https://testnet.monad.xyz/",
                    True,
                )
                if result:
                    logger.success(f"{wallet.address} | 已解决水龙头的验证码问题") 
                    break
                else:
                    logger.error(
                        f"{wallet.address} | 无法解决水龙头的验证码"
                    )

            if not result:
                raise Exception("水龙头验证码解决失败 3 次")

            headers = {
                "accept": "*/*",
                "accept-language": "fr-CH,fr;q=0.9,en-US;q=0.8,en;q=0.7",
                "content-type": "application/json",
                "origin": "https://testnet.monad.xyz",
                "priority": "u=1, i",
                "referer": "https://testnet.monad.xyz/",
                "sec-ch-ua": '"Not A(Brand";v="8", "Chromium";v="131", "Google Chrome";v="131"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-origin",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            }

            # 生成访客 ID
            visitor_id = secrets.token_hex(16)

            json_data = {
                "address": wallet.address,
                "visitorId": visitor_id,
                "cloudFlareResponseToken": result,
            }

            for _ in range(config.SETTINGS.ATTEMPTS):
                response = await session.post(
                    "https://testnet.monad.xyz/api/claim",
                    headers=headers,
                    json=json_data,
                )

                if "Claimed already" in response.text:
                    logger.success(
                        f"[{account_index}] | 已经从 faucet 领取代币"
                    )
                    return True

                if response.status_code == 200:
                    logger.success(
                        f"[{account_index}] | 成功从 faucet 获取代币"
                    )
                    return True
                else:
                    if "FUNCTION_INVOCATION_TIMEOUT" in response.text:
                        logger.error(
                            f"[{account_index}] | 无法从水龙头获取令牌：服务器没有响应，请等待......"
                        )
                    elif "Server error on QuickNode API" in response.text:
                        logger.error(
                            f"[{account_index}] | 水龙头不工作，QUICKNODE 已关闭"
                        )
                    elif "Over Enterprise free quota" in response.text:
                        logger.error(
                            f"[{account_index}] | MONAD 太烂了，FAUCET 不工作，稍后再试"
                        )
                        return False
                    elif "invalid-keys" in response.text:
                        logger.error(
                            f"[{account_index}] | 请使用 GITHUB 更新机器人"
                        )
                        return False
                    else:
                        logger.error(
                            f"[{account_index}] | 无法从水龙头获取代币"
                        )
                    await asyncio.sleep(3)
                    break

        except Exception as e:
            random_pause = random.randint(
                config.SETTINGS.RANDOM_PAUSE_BETWEEN_ACTIONS[0],
                config.SETTINGS.RANDOM_PAUSE_BETWEEN_ACTIONS[1],
            )
            logger.error(
                f"[{account_index}] | Error faucet to monad.xyz ({retry + 1}/{config.SETTINGS.ATTEMPTS}): {e}. Next faucet in {random_pause} seconds"
            )
            continue
    return False
