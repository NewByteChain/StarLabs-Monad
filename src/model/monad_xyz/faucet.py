import asyncio
from typing import Dict, List
from patchright.async_api import async_playwright
from loguru import logger
import random
import primp
from web3 import AsyncWeb3
from src.utils.config import Config
from eth_account import Account
import os
from pathlib import Path
import tempfile
import uuid
import aiofiles
import aiofiles.os
import re
from asyncio import Lock
import shutil

from src.utils.constants import RPC_URL

# Create file locks for thread safety
capsolver_file_lock = Lock()
config_file_lock = Lock()


def get_profiles_dir() -> str:
    """Get the path to profiles directory and ensure it exists."""
    # Get the path to the main.py directory (project root)
    root_dir = Path(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    )
    profiles_dir = root_dir / "data" / "profiles"

    # Create directories if they don't exist
    os.makedirs(profiles_dir, exist_ok=True)

    return str(profiles_dir)


def cleanup_profile(profile_dir: str) -> None:
    """Safely remove a Chrome profile directory."""
    try:
        if os.path.exists(profile_dir):
            shutil.rmtree(profile_dir, ignore_errors=True)
            logger.debug(f"Successfully cleaned up profile directory: {profile_dir}")
    except Exception as e:
        logger.warning(f"Failed to cleanup profile directory {profile_dir}: {e}")


async def update_capsolver_config(capsolver_path: str, api_key: str) -> None:
    """Updates the API key in both capsolver config files with thread safety."""
    content_script_path = os.path.join(capsolver_path, "my-content-script.js")
    config_js_path = os.path.join(capsolver_path, "assets", "config.js")

    # Update my-content-script.js
    async with capsolver_file_lock:
        try:
            async with aiofiles.open(
                content_script_path, "r", encoding="utf-8"
            ) as file:
                content = await file.read()
            new_content = re.sub(r'apiKey:\s*"[^"]*"', f'apiKey:"{api_key}"', content)
            async with aiofiles.open(
                content_script_path, "w", encoding="utf-8"
            ) as file:
                await file.write(new_content)
            logger.debug("Successfully updated my-content-script.js with API key")
        except Exception as e:
            logger.error(f"Failed to update my-content-script.js API key: {e}")
            raise

    # Update config.js
    async with config_file_lock:
        try:
            async with aiofiles.open(config_js_path, "r", encoding="utf-8") as file:
                content = await file.read()
            new_content = re.sub(r'apiKey:\s*"[^"]*"', f'apiKey: "{api_key}"', content)
            async with aiofiles.open(config_js_path, "w", encoding="utf-8") as file:
                await file.write(new_content)
            logger.debug("Successfully updated config.js with API key")
        except Exception as e:
            logger.error(f"Failed to update config.js API key: {e}")
            raise


def get_random_user_agent():
    chrome_versions = [
        "123.0.0.0",
        "124.0.0.0",
        "125.0.0.0",
        "126.0.0.0",
        "127.0.0.0",
        "128.0.0.0",
        "129.0.0.0",
        "130.0.0.0",
        "131.0.0.0",
        "132.0.0.0",
        "133.0.0.0",
    ]

    platforms = [
        ("Windows NT 10.0; Win64; x64", "Windows"),
        ("Macintosh; Intel Mac OS X 10_15_7", "macOS"),
        ("X11; Linux x86_64", "Linux"),
    ]

    platform, os_name = random.choice(platforms)
    chrome_version = random.choice(chrome_versions)

    return (
        f"Mozilla/5.0 ({platform}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version} Safari/537.36",
        chrome_version,
    )


def get_random_viewport() -> Dict[str, int]:
    resolutions = [
        {"width": 1920, "height": 1080},
        {"width": 1366, "height": 768},
        {"width": 1536, "height": 864},
        {"width": 1440, "height": 900},
        {"width": 1280, "height": 720},
    ]
    return random.choice(resolutions)


def get_random_timezone() -> str:
    timezones = [
        "America/New_York",
        "America/Chicago",
        "America/Los_Angeles",
        "America/Phoenix",
        "Europe/London",
        "Europe/Paris",
        "Europe/Berlin",
        "Asia/Tokyo",
        "Asia/Singapore",
        "Australia/Sydney",
    ]
    return random.choice(timezones)


def get_random_launch_args(capsolver_path: str) -> List[str]:
    base_args = [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--password-store=basic",
        # "--use-mock-keychain",
        # "--disable-software-rasterizer",
        # "--disable-gpu-sandbox",
        "--no-default-browser-check",
        # "--allow-running-insecure-content",
    ]

    optional_args = [
        "--disable-web-security",
        "--disable-features=IsolateOrigins,site-per-process,OptimizationGuideModelDownloading,OptimizationHintsFetching,OptimizationTargetPrediction,OptimizationHints",
        "--disable-site-isolation-trials",
        "--disable-setuid-sandbox",
        "--ignore-certificate-errors",
        # "--disable-accelerated-2d-canvas",
        # "--disable-bundled-ppapi-flash",
        "--disable-logging",
        "--disable-notifications",
    ]

        
    # Randomly select 2-4 optional arguments
    selected_optional = random.sample(optional_args, random.randint(2, 4))

    # Add extension-specific arguments
    extension_args = [
        f"--disable-extensions-except={capsolver_path}",
        f"--load-extension={capsolver_path}",
        "--lang=en-US",
    ]

    viewport = get_random_viewport()
    window_size_arg = [f"--window-size={viewport['width']},{viewport['height']}"]

    return base_args + selected_optional + extension_args + window_size_arg


async def faucet(
    session: primp.AsyncClient,
    account_index: int,
    config: Config,
    wallet: Account,
    proxy: str,
) -> bool:
    profile_dir = None
    for retry in range(config.SETTINGS.ATTEMPTS):
        try:
            my_web3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(RPC_URL))
            capsolver_path = os.path.join(os.path.dirname(__file__), "capsolver")

            # Update the capsolver API key in both files before launching the browser
            await update_capsolver_config(
                capsolver_path, config.FAUCET.CAPSOLVER_API_KEY
            )

            proxy_parts = proxy.split("@")
            auth = proxy_parts[0].split(":")
            proxy_options = {
                "server": f"http://{proxy_parts[1]}",
                "username": auth[0],
                "password": auth[1],
            }

            # Get random browser settings
            user_agent, chrome_version = get_random_user_agent()
            viewport = get_random_viewport()
            launch_args = get_random_launch_args(capsolver_path)

            async with async_playwright() as p:
                # 在 data/profiles 中创建一个唯一的配置文件目录
                profile_dir = os.path.join(
                    get_profiles_dir(), f"chrome_profile_{str(uuid.uuid4())}"
                )

                # 使用增强设置启动浏览器
                browser = await p.chromium.launch_persistent_context(
                    user_data_dir=profile_dir,
                    channel="chrome",
                    proxy=proxy_options,
                    viewport=viewport,
                    user_agent=user_agent,
                    headless=False,
                    args=launch_args,
                    ignore_https_errors=True,
                    locale="en-US",
                    timezone_id="UTC",
                    bypass_csp=True,
                    accept_downloads=True,
                    timeout=int(30000 * config.SETTINGS.BROWSER_PAUSE_MULTIPLIER),
                )

                # 创建新页面并导航
                page = await browser.new_page()

                # Set custom headers
                await page.set_extra_http_headers(
                    {
                        "accept": "*/*",
                        "accept-language": "en-US,en;q=0.9",
                        "sec-ch-ua": f'"Chromium";v="{chrome_version}", "Google Chrome";v="{chrome_version}"',
                        "sec-ch-ua-mobile": "?0",
                        "sec-ch-ua-platform": '"Windows"',
                        "sec-fetch-dest": "empty",
                        "sec-fetch-mode": "cors",
                        "sec-fetch-site": "cross-site",
                    }
                )

                await page.goto("https://testnet.monad.xyz/")

                await asyncio.sleep(5 * config.SETTINGS.BROWSER_PAUSE_MULTIPLIER)

                # 1. Click terms checkbox
                await page.click(
                    'button[role="checkbox"][aria-label="Accept terms and conditions"]',
                    timeout=int(30000 * config.SETTINGS.BROWSER_PAUSE_MULTIPLIER),
                )
                await asyncio.sleep(2 * config.SETTINGS.BROWSER_PAUSE_MULTIPLIER)

                # 2. Click Continue button
                await page.click(
                    'button:has-text("Continue")',
                    timeout=int(5000 * config.SETTINGS.BROWSER_PAUSE_MULTIPLIER),
                )
                await asyncio.sleep(5 * config.SETTINGS.BROWSER_PAUSE_MULTIPLIER)

                solved = False
                # # 3. 等待验证码解决
                logger.success(
                    f"[{account_index}] [{wallet.address}] | Wait 30 sec for captcha solving..."
                )
                for _ in range(6):
                    await asyncio.sleep(10)
                    stack_element = await page.wait_for_selector(
                        "//*[@id='capsolver-solver-tip-button']/div[2]",
                        state="visible",
                        timeout=int(20000 * config.SETTINGS.BROWSER_PAUSE_MULTIPLIER),
                    )
                    text = await stack_element.inner_text()
                    if text == "Solving...":
                        logger.info(
                            f"[{account_index}] [{wallet.address}] | Captcha is solving... Wait 10 sec..."
                        )
                        continue
                    if text == "Captcha solved!" or text == "Капча решена!":
                        logger.success(
                            f"[{account_index}] [{wallet.address}] | Captcha solved."
                        )
                        solved = True
                        break

                if not solved:
                    raise Exception("Captcha not solved")

                # # 3. Click Get Started button
                # await page.click(
                #     'button:has-text("Get Started")',
                #     timeout=int(5000 * config.SETTINGS.BROWSER_PAUSE_MULTIPLIER)
                # )

                # 4. Input wallet address
                await page.fill(
                    'input[placeholder*="0x8ce78"]',
                    wallet.address,
                    timeout=int(15000 * config.SETTINGS.BROWSER_PAUSE_MULTIPLIER),
                )

                # 5. Wait before clicking Get Testnet MON
                await asyncio.sleep(2 * config.SETTINGS.BROWSER_PAUSE_MULTIPLIER)

                # Get initial balance
                initial_balance = await my_web3.eth.get_balance(wallet.address)
                logger.info(
                    f"[{account_index}] [{wallet.address}] | Initial balance: {initial_balance}"
                )

                await page.click(
                    'button:has-text("Get Testnet MON")',
                    timeout=int(30000 * config.SETTINGS.BROWSER_PAUSE_MULTIPLIER),
                )

                await asyncio.sleep(5 * config.SETTINGS.BROWSER_PAUSE_MULTIPLIER)

                text = ""

                for _ in range(10):
                    try:
                        stack_element = await page.wait_for_selector(
                            "//ol/li/div[2]/div[@data-title]",
                            state="visible",
                            timeout=int(3000),
                        )
                        text = await stack_element.inner_text()
                        if text == "Success":
                            pass
                        if text == "Sending tokens...":
                            logger.info(
                                f"[{account_index}] [{wallet.address}] | Faucet is sending tokens... Wait 2 sec..."
                            )
                            await asyncio.sleep(
                                2 * config.SETTINGS.BROWSER_PAUSE_MULTIPLIER
                            )
                            continue
                        if "Unexpected token 'A'" in text or "QuickNode" in text:
                            logger.error(
                                f"[{account_index}] [{wallet.address}] | Faucet does not work now, try again later..."
                            )
                            return False
                        if "Claimed already" in text:
                            logger.success(
                                f"[{account_index}] [{wallet.address}] | Faucet already claimed..."
                            )
                            return True
                        if "CloudFlare process failed" in text:
                            raise Exception("Captcha is not solved, try again later...")

                        if "successful" in text:
                            logger.success(
                                f"[{account_index}] [{wallet.address}] | Got tokens from faucet monad.xyz."
                            )
                            return True
                    except Exception as e:
                        pass

                logger.info(
                    f"[{account_index}] [{wallet.address}] | Faucet is sending tokens... Wait 60 sec..."
                )
                await asyncio.sleep(60)
                # Get final balance and compare
                final_balance = await my_web3.eth.get_balance(wallet.address)
                logger.info(
                    f"[{account_index}] [{wallet.address}] | Final balance: {final_balance}"
                )

                if final_balance <= initial_balance:
                    raise Exception("Balance hasn't changed after faucet attempt!")

                logger.success(
                    f"[{account_index}] [{wallet.address}] | Faucet success!"
                )
                await asyncio.sleep(5 * config.SETTINGS.BROWSER_PAUSE_MULTIPLIER)

                await browser.close()
                cleanup_profile(
                    profile_dir
                )  # Clean up profile after successful completion
                return True

        except Exception as e:
            try:
                await browser.close()
            except:
                pass

            if profile_dir:  # Clean up profile on error
                cleanup_profile(profile_dir)

            random_pause = random.randint(
                config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"[{account_index}] | Error faucet to monad.xyz ({retry + 1}/{config.SETTINGS.ATTEMPTS}): {e}. Next faucet in {random_pause} seconds"
            )
            await asyncio.sleep(random_pause)
            continue

    if profile_dir:  # Final cleanup if all attempts failed
        cleanup_profile(profile_dir)
    return False