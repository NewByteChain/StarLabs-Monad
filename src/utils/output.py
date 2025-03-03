import os
from rich.console import Console
from rich.text import Text
from tabulate import tabulate
from rich.table import Table
from rich import box
from typing import List
from prompt_toolkit import Application
from prompt_toolkit.layout import Layout, Window, HSplit
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.styles import Style
import questionary
from questionary import Style as QuestionaryStyle
import asyncio
import sys


def show_logo():
    """显示时尚的 STARLABS 徽标"""
    # Очищаем экран
    os.system("cls" if os.name == "nt" else "clear")

    console = Console()

    # 用风格化的徽标创建星空
    logo_text = """
✦ ˚ . ⋆   ˚ ✦  ˚  ✦  . ⋆ ˚   ✦  . ⋆ ˚   ✦ ˚ . ⋆   ˚ ✦  ˚  ✦  . ⋆   ˚ ✦  ˚  ✦  . ⋆ ✦ ˚ 
. ⋆ ˚ ✧  . ⋆ ˚  ✦ ˚ . ⋆  ˚ ✦ . ⋆ ˚  ✦ ˚ . ⋆  ˚ ✦ . ⋆ ˚  ✦ ˚ . ⋆  ˚ ✦ . ⋆  ˚ ✦ .✦ ˚ . 
·˚ ⋆｡⋆｡. ★ ·˚ ★ ·˚ ⋆｡⋆｡. ★ ·˚ ★ ·˚ ⋆｡⋆｡. ★ ·˚ ★ ·˚ ⋆｡⋆｡. ★ ·˚ ⋆｡⋆｡. ★ ·˚ ★ ·˚ ·˚ ★ ·˚
✧ ⋆｡˚✦ ⋆｡  ███████╗████████╗ █████╗ ██████╗ ██╗      █████╗ ██████╗ ███████╗  ⋆｡ ✦˚⋆｡ 
★ ·˚ ⋆｡˚   ██╔════╝╚══██╔══╝██╔══██╗██╔══██╗██║     ██╔══██╗██╔══██╗██╔════╝  ✦˚⋆｡ ˚· 
⋆｡✧ ⋆ ★    ███████╗   ██║   ███████║██████╔╝██║     ███████║██████╔╝███████╗   ˚· ★ ⋆
˚· ★ ⋆｡    ╚════██║   ██║   ██╔══██║██╔══██╗██║     ██╔══██║██╔══██╗╚════██║   ⋆ ✧｡⋆ 
✧ ⋆｡ ˚·    ███████║   ██║   ██║  ██║██║  ██║███████╗██║  ██║██████╔╝███████║   ★ ·˚ ｡
★ ·˚ ✧     ╚══════╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═════╝ ╚══════╝   ｡⋆ ✧ 
·˚ ⋆｡⋆｡. ★ ·˚ ★ ·˚ ⋆｡⋆｡. ★ ·˚ ★ ·˚ ⋆｡⋆｡. ★ ·˚ ★ ·˚ ⋆｡⋆｡. ★ ·˚ ⋆｡⋆｡. ★ ·˚ ★ ·˚·˚ ⋆｡⋆｡.
. ⋆ ˚ ✧  . ⋆ ˚  ✦ ˚ . ⋆  ˚ ✦ . ⋆ ˚  ✦ ˚ . ⋆  ˚ ✦ . ⋆ ˚  ✦ ˚ . ⋆  ˚ ✦ . ⋆  ˚ ✦ .. ⋆  ˚ 
✦ ˚ . ⋆   ˚ ✦  ˚  ✦  . ⋆ ˚   ✦  . ⋆ ˚   ✦ ˚ . ⋆   ˚ ✦  ˚  ✦  . ⋆   ˚ ✦  ˚  ✦  . ⋆  ✦"""

    # 创建渐变文本
    gradient_logo = Text(logo_text)
    gradient_logo.stylize("bold bright_cyan")

    # 带缩进的输出
    console.print(gradient_logo)
    print()


def show_dev_info():
    """显示开发和版本信息"""
    console = Console()

    # 让我们创建一个美丽的餐桌
    table = Table(
        show_header=False,
        box=box.DOUBLE,
        border_style="bright_cyan",
        pad_edge=False,
        width=49,
        highlight=True,
    )

    # 添加列
    table.add_column("Content", style="bright_cyan", justify="center")

    # 添加联系人线路
    table.add_row("✨ StarLabs Monad Bot 1.8 ✨")
    table.add_row("─" * 43)
    table.add_row("")
    table.add_row("⚡ GitHub: [link]https://github.com/0xStarLabs[/link]")
    table.add_row("👤 Dev: [link]https://t.me/StarLabsTech[/link]")
    table.add_row("💬 Chat: [link]https://t.me/StarLabsChat[/link]")
    table.add_row("")

    # 输出带缩进的表格
    print("   ", end="")
    print()
    console.print(table)
    print()


async def show_menu(title: str, options: List[str]) -> str:
    """
    Displays an interactive menu with the given options and returns the selected option.
    """
    try:
        # Add empty lines for spacing
        print("\n")

        # Create custom style with larger text
        custom_style = QuestionaryStyle(
            [
                ("question", "fg:#B8860B bold"),  # Title color - muted gold
                ("answer", "fg:#ffffff bold"),  # Selected option color - white
                ("pointer", "fg:#B8860B bold"),  # Pointer color - muted gold
                (
                    "highlighted",
                    "fg:#B8860B bold",
                ),  # Highlighted option color - muted gold
                ("instruction", "fg:#666666"),  # Instruction text color - gray
            ]
        )

        print()

        # Show the menu with custom style
        result = await questionary.select(
            title,
            choices=options,  # Используем options напрямую, так как эмодзи уже есть
            style=custom_style,
            qmark="🎯",  # Custom pointer
            instruction="(Use arrow keys and Enter to select)",
        ).ask_async()

        return result

    except KeyboardInterrupt:
        print("\n\nExiting program... Goodbye! 👋")
        sys.exit(0)
