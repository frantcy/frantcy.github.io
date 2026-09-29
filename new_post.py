#!/usr/bin/env python3
r"""
新建今天的日记。

会自动创建：Raw/日记/2026年09月29日.md
——已经写过了就直接打开，不会覆盖你的内容。

模板：
    time: 2026.9.29
    tag: 日记
    title: 2026年09月29日

用法：
    .\.venv\Scripts\python.exe new_post.py              # 今天的日记
    .\.venv\Scripts\python.exe new_post.py --title 出差第一天
    .\.venv\Scripts\python.exe new_post.py --dir 随笔    # 换个子目录（子目录名会变成标签）
"""

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent
RAW_DIR = PROJECT_ROOT / "Raw"


def main():
    ap = argparse.ArgumentParser(description="新建今天的日记")
    ap.add_argument("--dir", "-d", default="日记", help="子目录名，默认「日记」（子目录名会自动成为标签）")
    ap.add_argument("--title", "-t", default="", help="日记标题，默认是今天日期")
    ap.add_argument("--tag", default="日记", help="标签，默认「日记」")
    args = ap.parse_args()

    today = datetime.now()
    filename = today.strftime("%Y年%m月%d日") + ".md"
    title = args.title.strip() or today.strftime("%Y年%m月%d日")
    time_value = f"{today.year}.{today.month}.{today.day}"

    target_dir = RAW_DIR / args.dir
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / filename

    if path.exists():
        print(f"📖 今天这篇已经存在了，直接帮你打开：{path.name}")
    else:
        content = f"time: {time_value}\ntag: {args.tag}\ntitle: {title}\n\n今天……\n"
        path.write_text(content, encoding="utf-8")
        print(f"✅ 已创建：{path.relative_to(PROJECT_ROOT)}")

    # 用系统默认程序打开（没关联就用记事本）
    try:
        import os
        os.startfile(str(path))
    except Exception:
        try:
            subprocess.Popen(["notepad", str(path)])
        except Exception as e:
            print(f"⚠️  打开失败，请手动打开文件：{path}")

    print()
    print("写完保存后，回到「控制台.bat」按 3 预览，按 7 发布。")


if __name__ == "__main__":
    main()
