#!/usr/bin/env python3
"""
OpenBlogger 命令行工具。

用法:
    python -m OpenBlogger.cli build              # 构建站点
    python -m OpenBlogger.cli build --theme my   # 使用指定主题
    python -m OpenBlogger.cli build --force      # 强制全量重建
    python -m OpenBlogger.cli serve              # 启动本地预览服务器
    python -m OpenBlogger.cli watch              # 监视文件变化，自动重建
    python -m OpenBlogger.cli clean              # 清空渲染输出
"""

import argparse
import http.server
import os
import socketserver
import sys
import time
from pathlib import Path

# ── Windows 控制台编码修复 ──
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 确保项目根在 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from OpenBlogger.renderer import BlogRenderer, RENDERED_DIR, RAW_DIR


def cmd_build(args):
    """构建站点。"""
    print(f"🔨 OpenBlogger 正在构建站点…")
    print(f"   主题: {args.theme}")
    print(f"   源文件: {RAW_DIR}")
    print(f"   输出: {RENDERED_DIR}")
    print()

    renderer = BlogRenderer(theme=args.theme, config=_load_config(args.config))
    stats = renderer.build(force=args.force)

    print()
    print(f"✅ 构建完成 — 渲染 {stats['rendered']} 篇，跳过 {stats['skipped']} 篇")
    if stats["errors"]:
        print(f"⚠️  {len(stats['errors'])} 个错误")
        for err in stats["errors"]:
            print(f"   - {err}")
    print(f"📂 输出目录: {RENDERED_DIR}")


def cmd_serve(args):
    """启动本地预览服务器，自动在浏览器中打开。"""
    # 先构建站点
    print("🔨 预览前先构建…")
    renderer = BlogRenderer(theme=args.theme, config=_load_config(args.config))
    stats = renderer.build(force=False)
    print(f"   渲染 {stats['rendered']} 篇，跳过 {stats['skipped']} 篇\n")

    os.chdir(RENDERED_DIR)

    port = args.port or 8080
    handler = http.server.SimpleHTTPRequestHandler

    # 尝试绑定端口，被占用则自动选择下一个
    max_attempts = 10
    for attempt in range(max_attempts):
        try:
            with socketserver.TCPServer(("", port), handler) as httpd:
                local_url = f"http://localhost:{port}"
                print(f"🚀 本地服务器已启动: {local_url}")
                print(f"   按 Ctrl+C 停止服务器")
                print(f"   正在尝试打开浏览器…")

                # 尝试打开浏览器
                _open_browser(local_url)

                try:
                    httpd.serve_forever()
                except KeyboardInterrupt:
                    print("\n👋 服务器已停止")
                return
        except OSError:
            if attempt < max_attempts - 1:
                print(f"⚠️  端口 {port} 被占用，尝试 {port + 1}…")
                port += 1
            else:
                print(f"❌ 端口 {args.port}—{port} 均被占用，请手动指定端口")
                sys.exit(1)


def cmd_watch(args):
    """监视源文件变化，自动重建。"""
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler

    class RebuildHandler(FileSystemEventHandler):
        def __init__(self, renderer):
            self.renderer = renderer
            self._last_build = 0
            self._debounce = 1.0  # 防抖秒数

        def on_any_event(self, event):
            if event.is_directory:
                return
            # 只关注 .md 和 .html 文件
            path = Path(event.src_path)
            if path.suffix not in (".md", ".html"):
                return
            now = time.time()
            if now - self._last_build < self._debounce:
                return
            self._last_build = now
            print(f"\n🔁 检测到变化: {path.name}")
            self.renderer.build(force=True)
            print("✅ 重建完成\n👀 继续监视…")

    renderer = BlogRenderer(theme=args.theme, config=_load_config(args.config))
    renderer.build(force=True)  # 先构建一次

    handler = RebuildHandler(renderer)
    observer = Observer()
    observer.schedule(handler, str(RAW_DIR), recursive=True)
    # 同时监视模板目录
    template_dir = renderer.template_dir
    if template_dir.exists():
        observer.schedule(handler, str(template_dir), recursive=True)

    observer.start()
    print(f"👀 正在监视 {RAW_DIR} 和 {template_dir}…")
    print("   按 Ctrl+C 停止\n")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\n👋 监视已停止")
    observer.join()


def cmd_clean(args):
    """清空渲染输出目录和缓存。"""
    renderer = BlogRenderer(theme=args.theme)
    renderer.clean()
    print("✅ 清理完成")


def _load_config(config_path: str = None) -> dict:
    """加载 site.json 站点配置。如果不存在则返回默认值。"""
    import json
    if config_path:
        path = Path(config_path)
    else:
        path = Path(__file__).resolve().parent.parent / "site.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            print(f"⚠️  读取配置文件失败: {e}，使用默认配置")
    return {}


def _open_browser(url: str):
    """尝试在默认浏览器中打开 URL。"""
    import webbrowser
    try:
        webbrowser.open(url)
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(
        description="OpenBlogger — 轻量级静态博客渲染引擎",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m OpenBlogger.cli build                    # 构建站点
  python -m OpenBlogger.cli build --theme modern     # 使用 modern 主题
  python -m OpenBlogger.cli build --force            # 强制全量重建
  python -m OpenBlogger.cli serve                    # 预览站点
  python -m OpenBlogger.cli serve --port 9090        # 指定端口预览
  python -m OpenBlogger.cli watch                    # 监视变化自动重建
  python -m OpenBlogger.cli clean                    # 清空输出
        """,
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # ── build ──
    build_parser = subparsers.add_parser("build", help="构建站点")
    build_parser.add_argument("--theme", "-t", default="default", help="模板主题名称 (默认: default)")
    build_parser.add_argument("--force", "-f", action="store_true", help="强制全量重建（忽略缓存）")
    build_parser.add_argument("--config", "-c", default=None, help="站点配置文件路径 (JSON)")
    build_parser.set_defaults(func=cmd_build)

    # ── serve ──
    serve_parser = subparsers.add_parser("serve", help="启动本地预览服务器")
    serve_parser.add_argument("--port", "-p", type=int, default=8080, help="服务器端口 (默认: 8080)")
    serve_parser.add_argument("--theme", "-t", default="default", help="模板主题名称 (默认: default)")
    serve_parser.add_argument("--config", "-c", default=None, help="站点配置文件路径 (JSON)")
    serve_parser.set_defaults(func=cmd_serve)

    # ── watch ──
    watch_parser = subparsers.add_parser("watch", help="监视文件变化自动重建")
    watch_parser.add_argument("--theme", "-t", default="default", help="模板主题名称 (默认: default)")
    watch_parser.add_argument("--config", "-c", default=None, help="站点配置文件路径 (JSON)")
    watch_parser.set_defaults(func=cmd_watch)

    # ── clean ──
    clean_parser = subparsers.add_parser("clean", help="清空渲染输出")
    clean_parser.add_argument("--theme", "-t", default="default", help="模板主题名称 (默认: default)")
    clean_parser.set_defaults(func=cmd_clean)

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
