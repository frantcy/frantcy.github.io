#!/usr/bin/env python3
"""
从 Hexo 渲染后的 HTML 逆向提取 Markdown 源文件。

用法:
    python OpenBlogger/import_legacy.py

输入: legacy/blog-master/YYYY/MM/DD/标题/index.html
输出: Raw/*.md

提取内容:
  - title:  <h1 class="article-title"> 中的文本
  - time:   目录路径中的 YYYY/MM/DD
  - tag:    从标题前缀提取（如"时评-xxx" → tag: 时评）
  - body:   <div class="article-entry"> → Markdown
"""

import re
import sys
from pathlib import Path

# Windows 控制台编码修复
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("请先安装: pip install beautifulsoup4 html2text")
    sys.exit(1)

try:
    import html2text
    H2T = html2text.HTML2Text()
    H2T.body_width = 0           # 不自动换行
    H2T.ignore_links = False
    H2T.ignore_images = False
    H2T.ignore_emphasis = False
    H2T.protect_links = True
    H2T.unicode_snob = True
except ImportError:
    H2T = None
    print("⚠️  html2text 未安装，将使用简易纯文本提取 (pip install html2text 可获得更好的结果)")


PROJECT_ROOT = Path(__file__).resolve().parent.parent
LEGACY_DIR = PROJECT_ROOT / ".archive" / "Legacy" / "blog-master"
RAW_DIR = PROJECT_ROOT / "Raw"

# 可识别的标题前缀 → 标签映射
TAG_PREFIXES = {
    "时评": "时评",
    "征文": "征文",
    "随笔": "随笔",
    "笔记": "笔记",
    "实验报告": "实验报告",
    "转载": "转载",
}


def extract_posts(legacy_root: Path) -> list[dict]:
    """扫描 legacy 目录，返回所有文章数据。"""
    posts = []
    for html_path in sorted(legacy_root.glob("????/??/??/*/index.html")):
        # 跳过归档/翻页目录
        dir_name = html_path.parent.name
        if re.match(r'^\d+$', dir_name) or dir_name == "page":
            continue

        rel = html_path.relative_to(legacy_root)
        parts = rel.parts
        date_str = f"{int(parts[0])}.{int(parts[1])}.{int(parts[2])}"
        raw_title = parts[3]  # 目录名即文章标题

        try:
            soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")

            # 1) 标题
            title_el = soup.select_one("h1.article-title")
            title = title_el.get_text(strip=True) if title_el else raw_title

            # 2) 时间（优先用 <time datetime>）
            time_el = soup.select_one("time[datetime]")
            if time_el and time_el.get("datetime"):
                dt = time_el["datetime"][:10]  # "2023-04-09"
                date_str = dt.replace("-0", ".").replace("-", ".")
                # 去掉前导零: "2023.04.09" → "2023.4.9"
                date_str = re.sub(r'\.0(\d)', r'.\1', date_str)

            # 3) 标签
            tags = extract_tags(title)

            # 4) 正文
            body_el = soup.select_one("div.article-entry")
            if body_el:
                # 移除"打赏"按钮等非正文元素
                for junk in body_el.select("#reword-out, #reward-btn, .declare, script, style"):
                    junk.decompose()
                # 移除 Hexo 的 <!-- more --> 注释（替换为空白）
                body_html = str(body_el)
                body_html = re.sub(r'<!--\s*more\s*-->', '', body_html, flags=re.IGNORECASE)
                # 转换 HTML → 正文
                if H2T:
                    body_md = H2T.handle(body_html).strip()
                else:
                    body_md = soup_to_text(body_el)
            else:
                body_md = ""

            posts.append({
                "title": title,
                "date": date_str,
                "tags": tags,
                "body": body_md,
                "source": str(rel),
                "slug": sanitize_slug(raw_title),
            })

        except Exception as e:
            print(f"  ❌ {rel}: {e}")

    return posts


def extract_tags(title: str) -> list[str]:
    """从标题前缀提取标签。如 '时评-五一调休' → ['时评']"""
    # 已知标签前缀（精确匹配）
    for prefix, tag in TAG_PREFIXES.items():
        if title.startswith(prefix + "-") or title.startswith(prefix + "——") or title.startswith(prefix + "—"):
            return [tag]
    # "XX-" 通用前缀（但排除明显不是标签的情况）
    match = re.match(r'^([\w一-鿿]{1,4})[-–—]', title)
    if match:
        candidate = match.group(1)
        # 排除：数字、纯英文软件名、非标签描述词
        if re.match(r'^\d+$', candidate):          # 纯数字
            return []
        if candidate in ("几个", "一些", "免费", "图片", "哗哩哗哩", "蓝灯",
                         "终南", "猫猫", "录屏", "弹球", "比特", "喜德盛",
                         "我的", "关于", "综合", "研究", "西柚", "红楼",
                         "美术", "EaseUS", "Bandizip", "altale", "BongoCat",
                         "bitcoment", "bandicam", "rc200", "pixelqx", "xiyou",
                         "Pinball", "myhtml", "Final", "Shcedule", "Rsearch",
                         "EaseUS", "coc", "bandizip"):
            return []
    return []


def sanitize_slug(title: str) -> str:
    """从标题生成安全的文件名。"""
    slug = re.sub(r'[<>:"/\\|?*]', '-', title)
    slug = re.sub(r'\s+', '-', slug)
    slug = re.sub(r'-+', '-', slug).strip('-')
    return slug[:80] if len(slug) > 80 else slug


def soup_to_text(el) -> str:
    """简易 HTML→文本（html2text 不可用时的回退方案）。"""
    text = el.get_text(separator="\n", strip=True)
    # 压缩多余空行
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text


def build_md(post: dict) -> str:
    """将文章数据组合为 OpenBlogger 格式的 Markdown。"""
    lines = []
    lines.append(f"time: {post['date']}")
    if post["tags"]:
        lines.append(f"tag: {', '.join(post['tags'])}")
    lines.append(f"title: {post['title']}")
    lines.append("")  # 空行分隔元数据与正文
    lines.append(post["body"].strip())
    return "\n".join(lines) + "\n"


def main():
    if not LEGACY_DIR.exists():
        print(f"❌ 找不到 legacy 目录: {LEGACY_DIR}")
        print("   请将 Hexo 博客文件放在 legacy/blog-master/ 下")
        sys.exit(1)

    posts = extract_posts(LEGACY_DIR)
    if not posts:
        print("❌ 未找到任何文章")
        sys.exit(1)

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    imported = 0
    for post in posts:
        md_content = build_md(post)
        out_path = RAW_DIR / f"{post['slug']}.md"

        # 避免覆盖
        if out_path.exists():
            out_path = RAW_DIR / f"{post['slug']}-legacy.md"

        out_path.write_text(md_content, encoding="utf-8")
        imported += 1
        tag_str = f" [{', '.join(post['tags'])}]" if post['tags'] else ""
        print(f"  ✅ {post['date']}{tag_str} {post['title']}")

    print(f"\n🎉 导入完成: {imported} 篇文章 → {RAW_DIR}/")
    print(f"   运行 python -m OpenBlogger.cli build --force 来重新构建站点")


if __name__ == "__main__":
    main()
