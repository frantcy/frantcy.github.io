"""
OpenBlogger 核心渲染引擎。

功能：
  - 解析 Markdown 文件（元数据头 + 正文）
  - 将 Markdown 转为 HTML（支持代码高亮、表格、脚注等扩展）
  - 使用 Jinja2 模板渲染页面
  - 生成首页、目录页、标签页、文章页、RSS、网站地图
  - 增量构建（仅重新渲染变更文件）
  - 自动补全缺失的日期和标题
"""

import os
import re
import json
import shutil
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional

import markdown
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

# ── 项目路径 ──
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "Raw"
RENDERED_DIR = PROJECT_ROOT / "Rendered"
TEMPLATE_ROOT = PROJECT_ROOT / "OpenBlogger" / "template"
IMAGES_DIR = PROJECT_ROOT / "Image"               # 所有静态资源（图片/下载）
FRIENDS_SRC = PROJECT_ROOT / ".archive" / "yhsome.github.io"  # 友链项目源文件
PLUGINS_DIR = PROJECT_ROOT / "Plugins"                       # 博客专属插件
VIEWER_JS_DIR = PROJECT_ROOT / "OpenBlogger" / "Plugins" / "Viewer" / "js"  # 框架自带
PAGE_ID_FILE = PROJECT_ROOT / ".data" / ".viewer_pages.json"
CACHE_FILE = PROJECT_ROOT / ".data" / ".render_cache.json"
PROJECTS_FILE = PLUGINS_DIR / "GitHubProjects" / "projects.json"
UPDATES_FILE = PROJECT_ROOT / "OpenBlogger" / "Plugins" / "GitHubActivity" / "updates.json"

# ── GitHub 语言颜色映射 ──
LANG_COLORS = {
    "Python": "#3572A5", "JavaScript": "#f1e05a", "TypeScript": "#3178c6",
    "HTML": "#e34c26", "CSS": "#563d7c", "Java": "#b07219",
    "C++": "#f34b7d", "C": "#555555", "Go": "#00ADD8", "Rust": "#dea584",
    "Shell": "#89e051", "Vue": "#41b883", "Kotlin": "#A97BFF",
    "Swift": "#F05138", "Dart": "#00B4AB", "Ruby": "#701516",
}

# ── 默认站点配置 ──
DEFAULT_CONFIG = {
    "site_title": "我的博客",
    "site_description": "用文字记录思考与生活。",
    "author": "",
    "language": "zh-CN",
    "posts_per_page": 10,
    "theme": "default",
    "enable_rss": True,
    "enable_sitemap": True,
    "date_format": "%Y年%m月%d日",
    "excerpt_length": 150,
    "viewer": {
        "enable_counter": True,
        "enable_unique": True,
        "enable_global": True,
        "enable_comment": True,
        "user": "aaaaa",
        "secret": "d1bdf09a",
    },
}


class BlogRenderer:
    """博客渲染器：读取 Raw 中的 .md 文件，渲染为静态 HTML 站点。"""

    def __init__(self, theme: str = "default", config: Optional[dict] = None):
        self.theme = theme
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self.template_dir = TEMPLATE_ROOT / theme.capitalize() if theme != "default" else TEMPLATE_ROOT / "Default"
        self.template_dir = self.template_dir.resolve()

        if not self.template_dir.exists():
            raise FileNotFoundError(f"模板目录不存在: {self.template_dir}")

        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=True,
        )
        # 自定义过滤器
        self.env.filters["urlencode"] = lambda s: _url_encode(str(s))

        self.posts: list[dict] = []
        self.cache: dict = self._load_cache()
        self._page_ids: dict[str, int] = self._load_page_ids()    # Viewer 页面编号记录

    # ═══════════════════════════════════════════════
    #  缓存管理
    # ═══════════════════════════════════════════════

    def _load_cache(self) -> dict:
        """加载渲染缓存，用于增量构建。"""
        if CACHE_FILE.exists():
            try:
                return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _save_cache(self):
        """保存渲染缓存。"""
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps(self.cache, ensure_ascii=False, indent=2), encoding="utf-8")

    def _file_hash(self, path: Path) -> str:
        """计算文件内容的 MD5 哈希。"""
        return hashlib.md5(path.read_bytes()).hexdigest()

    def _is_changed(self, path: Path) -> bool:
        """检查文件是否自上次渲染后发生了变化。"""
        key = str(path.relative_to(PROJECT_ROOT))
        current_hash = self._file_hash(path)
        if self.cache.get(key) != current_hash:
            self.cache[key] = current_hash
            return True
        return False

    # ═══════════════════════════════════════════════
    #  Viewer 页面编号管理
    # ═══════════════════════════════════════════════

    def _load_page_ids(self) -> dict[str, int]:
        """加载 Viewer 页面编号记录（永不重用已删页面的 ID）。"""
        if PAGE_ID_FILE.exists():
            try:
                return json.loads(PAGE_ID_FILE.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _save_page_ids(self):
        """保存页面编号记录。"""
        PAGE_ID_FILE.parent.mkdir(parents=True, exist_ok=True)
        PAGE_ID_FILE.write_text(json.dumps(self._page_ids, ensure_ascii=False, indent=2), encoding="utf-8")

    def _next_page_id(self) -> int:
        """获取下一个可用编号（永不重用）。"""
        return max(self._page_ids.values()) + 1 if self._page_ids else 1

    def _get_page_id(self, out_path: Path) -> int:
        """为指定输出文件获取或分配 Viewer 页面编号。"""
        key = str(out_path.relative_to(RENDERED_DIR))
        if key in self._page_ids:
            return self._page_ids[key]
        pid = self._next_page_id()
        self._page_ids[key] = pid
        return pid

    # ═══════════════════════════════════════════════
    #  Markdown 解析
    # ═══════════════════════════════════════════════

    @staticmethod
    def parse_md(file_path: Path) -> dict:
        """
        解析 Markdown 文件，提取元数据和正文。

        元数据格式 (文件头部，key: value)：
            time: 2026.6.18
            tag: 模板, 博客
            title: 我的文章标题
            author: 张三

        第一行空行之后为正文 (Markdown)。

        若缺少 time 或 title，会自动补全：
          - time → 当前日期
          - title → 正文第一句（超过20字加省略号）
        """
        raw_text = file_path.read_text(encoding="utf-8")
        lines = raw_text.splitlines()

        metadata = {}
        body_start = 0

        # 逐行解析元数据头
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                body_start = i + 1
                break
            match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*[:：]\s*(.*)", line)
            if match:
                key = match.group(1).strip().lower()
                value = match.group(2).strip()
                metadata[key] = value
            else:
                # 不是合法的元数据行 → 从这里开始是正文
                body_start = i
                break

        # 提取正文
        body_lines = lines[body_start:]
        while body_lines and not body_lines[0].strip():
            body_lines.pop(0)  # 去掉头部空行
        body_md = "\n".join(body_lines).strip()

        # ── 自动补全 ──
        # 1) 标题：若无 → 取正文第一句
        if not metadata.get("title"):
            metadata["title"] = BlogRenderer._extract_title_from_body(body_md)

        # 2) 时间：若无 → 当前日期
        if not metadata.get("time"):
            metadata["time"] = datetime.now().strftime("%Y.%-m.%-d" if os.name != "nt" else "%Y.%#m.%#d")

        # 3) 标准化日期格式
        metadata["time"] = BlogRenderer._normalize_date(metadata["time"])

        # 4) 标签 → 列表
        raw_tags = metadata.get("tag", "")
        metadata["tags"] = [t.strip() for t in re.split(r"[,，、\s]+", raw_tags) if t.strip()]
        # 子目录名自动作为标签（Raw/项目/a.md → 自动加标签"项目"）
        parent_dir = file_path.parent.relative_to(RAW_DIR)
        if str(parent_dir) != ".":
            folder_tag = str(parent_dir).replace("\\", "/").split("/")[0]  # 只取第一层目录名
            if folder_tag and folder_tag not in metadata["tags"]:
                metadata["tags"].append(folder_tag)
        if not metadata["tags"]:
            metadata["tags"] = ["未分类"]           # 无标签时默认"未分类"

        # 5) 摘要
        metadata["excerpt"] = BlogRenderer._make_excerpt(body_md)

        return {
            "metadata": metadata,
            "body_md": body_md,
            "body_html": "",  # 稍后填充
            "slug": BlogRenderer._slugify(file_path.stem),
            "source_file": str(file_path.relative_to(PROJECT_ROOT)),
        }

    @staticmethod
    def _extract_title_from_body(body_md: str, max_len: int = 20) -> str:
        """从正文中提取标题：取第一句（以 。！？.!? 换行 为界），超出截断+省略号。"""
        # 去除开头的 # 标记
        body = body_md.lstrip("# ").strip()
        # 取第一句
        sentence = re.split(r"[。！？\n.!?]", body)[0].strip()
        if not sentence:
            sentence = body[:max_len]
        if len(sentence) > max_len:
            sentence = sentence[:max_len] + "…"
        return sentence or "未命名文章"

    @staticmethod
    def _normalize_date(date_str: str) -> str:
        """统一日期格式为 YYYY.M.D。"""
        date_str = date_str.strip()
        for fmt in ["%Y.%m.%d", "%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日", "%Y.%-m.%-d", "%Y.%#m.%#d"]:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime("%Y.%-m.%-d") if os.name != "nt" else dt.strftime("%Y.%#m.%#d")
            except ValueError:
                continue
        # 尝试仅年月日数字
        match = re.match(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", date_str)
        if match:
            return f"{match.group(1)}.{int(match.group(2))}.{int(match.group(3))}"
        return date_str  # 保留原样

    @staticmethod
    @staticmethod
    def _make_excerpt(body_md: str, max_len: int = 150) -> str:
        """生成纯文本摘要：MD→HTML→剥标签，干净无语法残留。"""
        try:
            # 用轻量 markdown 转 HTML（不用代码高亮等重扩展）
            md = markdown.Markdown(extensions=["extra"], output_format="html")
            html = md.convert(body_md)
            # 剥 HTML 标签
            clean = re.sub(r'<[^>]+>', '', html)
            # 解 HTML 实体
            clean = clean.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"').replace('&#39;', "'")
            # 压缩空白
            clean = re.sub(r'\s+', ' ', clean).strip()
        except Exception:
            clean = re.sub(r'[#*>`~\[\]()!_|]', ' ', body_md)
            clean = re.sub(r'\s+', ' ', clean).strip()
        if len(clean) > max_len:
            clean = clean[:max_len].rstrip() + '…'
        return clean

    @staticmethod
    def _slugify(text: str) -> str:
        """生成 URL 安全的文件名 slug。"""
        # 对中文等非 ASCII 字符，保留原样（URL 编码由模板处理）
        slug = re.sub(r"[^\w一-鿿\-]", "-", text)
        slug = re.sub(r"-{2,}", "-", slug).strip("-")
        return slug or "post"

    # ═══════════════════════════════════════════════
    #  Markdown → HTML
    # ═══════════════════════════════════════════════

    @staticmethod
    @staticmethod
    def md_to_html(md_text: str) -> str:
        """将 Markdown 文本转换为 HTML（支持代码高亮、表格、脚注等扩展）。

        特别处理：<details> 标签内的 Markdown 会被单独渲染。
        Python markdown 库的 md_in_html 不完全支持 <details>/<summary>。
        """
        # ── 预处理 <details> 块：单独提取内容渲染 ──
        text = md_text
        def _render_details(m):
            tag_attrs = m.group(1) or ''
            summary_match = re.search(r'<summary(\s[^>]*)?>(.*?)</summary>', m.group(2), re.DOTALL)
            if summary_match:
                summary_attrs = summary_match.group(1) or ''
                summary_text = summary_match.group(2).strip()
                body = m.group(2)[summary_match.end():].strip()
            else:
                summary_attrs = ''
                summary_text = 'Details'
                body = m.group(2).strip()
            # 递归渲染 body 中的 Markdown
            from markdown import Markdown as MD
            _md = MD(extensions=['extra','codehilite','sane_lists','smarty'], output_format='html')
            rendered_body = _md.convert(body)
            return f'<details{tag_attrs}><summary{summary_attrs}>{summary_text}</summary>{rendered_body}</details>'

        text = re.sub(r'<details(\s[^>]*)?>(.*?)</details>', _render_details, text, flags=re.DOTALL)

        extensions = [
            "extra",              # 表格、定义列表、脚注、缩写等
            "codehilite",         # 代码语法高亮
            "toc",                # 目录
            "nl2br",              # 换行转 <br>
            "sane_lists",         # 更合理的列表处理
            "smarty",             # 智能引号
            "md_in_html",         # 处理 HTML 标签内的 Markdown
        ]
        extension_configs = {
            "codehilite": {
                "css_class": "highlight",
                "guess_lang": True,
                "use_pygments": True,
            },
            "toc": {
                "permalink": " ¶",
                "permalink_class": "toc-link",
            },
        }
        try:
            md = markdown.Markdown(
                extensions=extensions,
                extension_configs=extension_configs,
                output_format="html",
            )
            html = md.convert(text)
            return html
        except Exception:
            md = markdown.Markdown(extensions=["extra", "nl2br", "sane_lists"], output_format="html")
            return md.convert(text)

    # ═══════════════════════════════════════════════
    #  构建流程
    # ═══════════════════════════════════════════════

    def build(self, force: bool = False) -> dict:
        """
        执行完整构建。

        参数:
            force: 若为 True，强制重新渲染所有文件（忽略缓存）。

        返回:
            dict: {"rendered": int, "skipped": int, "errors": list}
        """
        stats = {"rendered": 0, "skipped": 0, "errors": []}

        # Step 1: 扫描 Raw/ 目录中的 .md 文件
        raw_files = sorted(RAW_DIR.rglob("*.md"))  # 递归扫描子目录
        if not raw_files:
            print("⚠️  Raw/ 目录中没有找到 .md 文件，将只生成空的列表页")

        # Step 2: 解析所有文章
        self.posts = []
        for md_path in raw_files:
            try:
                if not force and not self._is_changed(md_path):
                    stats["skipped"] += 1
                    # 仍需从缓存恢复文章数据用于列表页渲染
                    cached_post = self._restore_from_cache(str(md_path.relative_to(PROJECT_ROOT)))
                    if cached_post:
                        self.posts.append(cached_post)
                        continue

                post = self.parse_md(md_path)
                post["body_html"] = self.md_to_html(post["body_md"])
                stats["rendered"] += 1
                self.posts.append(post)

            except Exception as e:
                stats["errors"].append(f"解析 {md_path.name} 失败: {e}")
                print(f"❌ 解析 {md_path.name} 失败: {e}")

        if not self.posts:
            print("⚠️  没有可渲染的文章，将只生成空的列表页")

        # Step 3: 按时间排序（最新在前）
        # 按日期排序（解析为元组避免字符串比较 "10" < "4" 的问题）
        # 按日期排序 → 同日按源文件修改时间倒序（晚写的排前面）
        self.posts.sort(
            key=lambda p: (_parse_date_tuple(p["metadata"]["time"]),
                           (PROJECT_ROOT / p["source_file"]).stat().st_mtime if p.get("source_file") else 0),
            reverse=True,
        )

        # Step 4: 渲染文章页
        RENDERED_DIR.mkdir(parents=True, exist_ok=True)
        posts_dir = RENDERED_DIR / "posts"
        posts_dir.mkdir(exist_ok=True)

        for i, post in enumerate(self.posts):
            try:
                prev_post = self.posts[i - 1] if i > 0 else None
                next_post = self.posts[i + 1] if i < len(self.posts) - 1 else None

                out_path = posts_dir / f"{post['slug']}.html"
                context = self._build_post_context(post, prev_post, next_post, out_path)
                html = self._render_template("Post.html", context)

                out_path.write_text(html, encoding="utf-8")
                post["url"] = f"posts/{post['slug']}.html"

            except Exception as e:
                stats["errors"].append(f"渲染文章 {post['metadata'].get('title', '?')} 失败: {e}")
                print(f"❌ 渲染文章失败: {e}")

        # Step 5: 渲染列表页
        list_pages = [
            ("index.html", "Homepage.html", self._build_homepage_context()),
            ("directory.html", "Directory.html", self._build_directory_context()),
            ("tags.html", "Tag.html", self._build_tags_context()),
            ("resources.html", "Resources.html", self._build_resources_context()),
            ("friendlinks.html", "FriendLinks.html", self._build_friendlinks_context()),
            ("updates-page.html", "Updates.html", self._build_updates_context()),
        ]

        for filename, template, context in list_pages:
            try:
                out_path = RENDERED_DIR / filename
                context.update(self._viewer_context(out_path))
                html = self._render_template(template, context)
                out_path.write_text(html, encoding="utf-8")
                stats["rendered"] += 1
            except TemplateNotFound:
                print(f"⚠️  模板 {template} 不存在，跳过")
            except Exception as e:
                stats["errors"].append(f"渲染 {filename} 失败: {e}")
                print(f"❌ 渲染 {filename} 失败: {e}")

        # Step 6: RSS & Sitemap
        if self.config.get("enable_rss"):
            self._generate_rss()
        if self.config.get("enable_sitemap"):
            self._generate_sitemap()

        # Step 7: 复制图片
        self._copy_images()

        # Step 7.5: 复制友链项目
        self._copy_friends()

        # Step 8: 复制 Viewer 插件 JS
        self._copy_viewer_js()

        # Step 9: 保存缓存 & 页面编号
        self._save_cache()
        self._save_page_ids()

        return stats

    # ═══════════════════════════════════════════════
    #  上下文构建
    # ═══════════════════════════════════════════════

    def _build_post_context(self, post: dict, prev_post: Optional[dict],
                             next_post: Optional[dict], out_path: Path) -> dict:
        """构建文章页的模板上下文（位于 posts/ 子目录）。"""
        meta = post["metadata"]
        return {
            "title": meta["title"],
            "date": self._format_date(meta["time"]),
            "tags": meta.get("tags", []),
            "author": meta.get("author", self.config.get("author", "")),
            "content": post["body_html"],
            "site_title": self.config["site_title"],
            "current_year": datetime.now().year,
            "relative_root": "../",               # 文章页需要 ../ 回到根目录
            "prev_post": self._nav_post(prev_post) if prev_post else None,
            "next_post": self._nav_post(next_post) if next_post else None,
            "excerpt": meta.get("excerpt", ""),   # 给评论区做文章标识
            "total_posts": len(self.posts),        # 侧栏统计
            "total_words": self._count_total_words(),  # 全站总字数
            "all_tags": self._collect_tags(),      # 侧栏标签（全量，目录页用）
            "sidebar_tags": self._random_sidebar_tags(),  # 精选标签（侧栏展示）
            "max_page_id": max(self._page_ids.values()) if self._page_ids else 0,
            **self._viewer_context(out_path),      # Viewer: page_id + 配置
        }

    def _build_homepage_context(self) -> dict:
        """构建首页模板上下文。"""
        all_posts = [self._summary(p) for p in self.posts]
        recent = all_posts[:3]  # 首页展示最近 3 篇
        # 项目标签的文章
        projects = [s for p in self.posts
                    if "项目" in p["metadata"].get("tags", [])
                    for s in [self._summary(p)]]
        all_tags = self._collect_tags()
        return {
            "site_title": self.config["site_title"],
            "site_description": self.config["site_description"],
            "recent_posts": recent,
            "project_posts": projects,             # 项目展示区
            "all_tags": all_tags,
            "sidebar_tags": self._random_sidebar_tags(),  # 精选标签（侧栏展示）
            "total_posts": len(self.posts),       # 全站文章总数（侧栏统计用）
            "total_words": self._count_total_words(),  # 全站总字数
            "updates": self._load_updates(),  # 首页侧栏（模板内限制 5 条）
            "max_page_id": max(self._page_ids.values()) if self._page_ids else 0,  # 弹幕用
            "current_year": datetime.now().year,
            "relative_root": "",                  # 首页在根目录
        }

    def _build_directory_context(self, active_tag: str = "") -> dict:
        """构建目录页模板上下文（文章按年月分组）。"""
        all_tags = self._collect_tags()
        posts = []
        last_month = ""
        for p in self.posts:
            s = self._summary(p)
            # 提取年月标签 (如 "2023年4月")
            m = re.match(r'(\d{4})\D+(\d{1,2})', s["date"])
            month_label = f"{m.group(1)}年{int(m.group(2))}月" if m else ""
            s["month_label"] = month_label
            s["show_month"] = (month_label != last_month)   # 月份变化时显示分隔
            last_month = month_label
            posts.append(s)
        # 收集有文章的日期（"YYYY-MM-DD" 集合，日历用）
        post_dates = sorted(set(
            f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
            for p in self.posts
            if (m := re.match(r'(\d{4})\D+(\d{1,2})\D+(\d{1,2})', p["metadata"]["time"]))
        ))
        return {
            "site_title": self.config["site_title"],
            "all_posts": posts,
            "all_tags": all_tags,
            "active_tag": active_tag,
            "post_dates": post_dates,              # 日历高亮数据
            "current_year": datetime.now().year,
            "relative_root": "",                  # 目录页在根目录
        }

    def _build_tags_context(self) -> dict:
        """构建标签页模板上下文。"""
        tags_with_count = self._collect_tags()
        # 对于 Tag.html，需要更丰富的数据
        tags_data = []
        tag_post_map = {}
        for post in self.posts:
            for tag in post["metadata"].get("tags", []):
                if tag not in tag_post_map:
                    tag_post_map[tag] = []
                tag_post_map[tag].append(post)

        for tc in tags_with_count:
            summaries = [self._summary(p) for p in tag_post_map.get(tc["name"], [])]
            tags_data.append({
                "name": tc["name"],
                "count": tc["count"],
                "posts": summaries,
            })

        return {
            "site_title": self.config["site_title"],
            "tags_with_count": tags_data,
            "current_year": datetime.now().year,
            "relative_root": "",                  # 标签页在根目录
        }

    def _build_resources_context(self) -> dict:
        """构建资源页上下文（GitHub 项目 + 近期更新 + 友链工具合并）。"""
        gh_token = self.config.get("github_token", "")
        return {
            "site_title": self.config["site_title"],
            "github_token": gh_token,          # GitHub API 认证 token（空则无认证请求）
            "projects": self._load_projects(),
            "updates": self._load_updates(),    # 近七天 GitHub 活动
            "link_sections": [
                {
                    "title": "🎮 在线小工具",
                    "links": [
                        {"name": "弹球挑战", "desc": "浏览器弹球游戏，30分挑战成功有红包", "icon": "🕹️", "tag": "游戏", "url": "friends/PinballChallenge/"},
                        {"name": "三国杀记牌工具", "desc": "三国杀在线记牌辅助", "icon": "🃏", "tag": "桌游", "url": "friends/sgsrecord/"},
                        {"name": "假邮件生成器", "desc": "恭喜你，你被坑了——在线整蛊页面", "icon": "📧", "tag": "整活", "url": "friends/fakemail/"},
                        {"name": "西柚搜索工具", "desc": "西柚英语在线信息搜索工具", "icon": "🔍", "tag": "学习", "url": "friends/xiyou/"},
                    ],
                },
                {
                    "title": "🧪 实验性项目",
                    "links": [
                        {"name": "原神启动页", "desc": "原神风格网页还原练习", "icon": "✨", "tag": "前端", "url": "friends/genshin/"},
                    ],
                },
                {
                    "title": "📚 参考资源",
                    "links": [
                        {"name": "3500 词研究器", "desc": "英语 3500 词汇研究与数据库", "icon": "📊", "tag": "数据", "url": "friends/3500researcher/"},
                    ],
                },
            ],
            "current_year": datetime.now().year,
            "relative_root": "",
        }

    def _build_friendlinks_context(self) -> dict:
        """构建友情链接页面上下文。"""
        return {
            "site_title": self.config["site_title"],
            "friend_link_sections": [
                {
                    "title": "👥 好友链接",
                    "links": [
                        {"name": "MKrari", "desc": "个人博客", "icon": "<img src=\"images/ksm1.webp\" style=\"width:36px;height:36px;border-radius:50%\">", "url": "https://mkrari.cn/"},
                    ],
                },
                {
                    "title": "🛠️ 开发工具",
                    "links": [
                        {"name": "GitHub", "desc": "全球最大的代码托管平台", "icon": "🐙", "url": "https://github.com"},
                        {"name": "TinyWebDB", "desc": "轻量级云数据库，Viewer 插件的数据后端", "icon": "☁️", "url": "https://tinywebdb.appinventor.space"},
                        {"name": "jsDelivr", "desc": "免费 CDN，加速静态资源加载", "icon": "🚀", "url": "https://www.jsdelivr.com"},
                        {"name": "Carbon", "desc": "代码截图美化工具", "icon": "🎨", "url": "https://carbon.now.sh"},
                        {"name": "Regex101", "desc": "正则表达式在线测试与调试", "icon": "🔍", "url": "https://regex101.com"},
                    ],
                },
                {
                    "title": "🤖 AI 工具",
                    "links": [
                        {"name": "Claude", "desc": "Anthropic 的 AI 助手，OpenBlogger 的幕后搭档", "icon": "🧠", "url": "https://claude.ai"},
                        {"name": "ChatGPT", "desc": "OpenAI 的对话 AI", "icon": "💬", "url": "https://chat.openai.com"},
                        {"name": "Hugging Face", "desc": "开源 AI 模型社区，西柚英语翻译模型来源", "icon": "🤗", "url": "https://huggingface.co"},
                        {"name": "Poe", "desc": "多模型 AI 聚合平台", "icon": "📱", "url": "https://poe.com"},
                    ],
                },
                {
                    "title": "📖 学习资源",
                    "links": [
                        {"name": "MDN Web Docs", "desc": "Web 开发权威文档", "icon": "📘", "url": "https://developer.mozilla.org/zh-CN/"},
                        {"name": "Python 官方文档", "desc": "Python 语言标准库参考", "icon": "🐍", "url": "https://docs.python.org/zh-cn/3/"},
                        {"name": "Markdown 指南", "desc": "Markdown 语法速查", "icon": "📝", "url": "https://www.markdownguide.org"},
                        {"name": "Can I Use", "desc": "浏览器特性兼容性查询", "icon": "🌐", "url": "https://caniuse.com"},
                    ],
                },
            ],
            "current_year": datetime.now().year,
            "relative_root": "",
        }

    def _build_updates_context(self) -> dict:
        """构建 GitHub 更新记录独立页上下文。"""
        return {
            "site_title": self.config["site_title"],
            "updates": self._load_updates(),
            "current_year": datetime.now().year,
            "relative_root": "",
        }

    def _load_projects(self) -> list[dict]:
        """从 projects.json 加载 GitHub 仓库数据，格式化为模板用的结构。"""
        if not PROJECTS_FILE.exists():
            return []
        try:
            raw = json.loads(PROJECTS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        result = []
        for r in raw:
            name = r.get("name", "")
            # 图标根据语言/主题选择
            icon = "📂"
            lang = r.get("language", "")
            if "Python" in lang: icon = "🐍"
            elif "JavaScript" in lang or "TypeScript" in lang: icon = "📜"
            elif "HTML" in lang: icon = "🌐"
            elif "Vue" in lang: icon = "💚"
            elif "Go" in lang: icon = "🔵"
            elif "Rust" in lang: icon = "🦀"
            elif "Java" in lang: icon = "☕"
            # 链接：有 GitHub Pages 则链向 pages，否则链向仓库
            has_pages = r.get("has_pages", False)
            if has_pages:
                # GitHub Pages URL: https://YHSome.github.io/{repo}/
                link = f"https://yhsome.github.io/{name}/"
            else:
                link = r.get("html_url", f"https://github.com/YHSome/{name}")
            result.append({
                "name": name,
                "description": r.get("description", ""),
                "language": lang,
                "lang_color": LANG_COLORS.get(lang, "#8b8b8b"),
                "stars": r.get("stars", 0),
                "forks": r.get("forks", 0),
                "has_pages": has_pages,
                "link": link,
                "icon": icon,
            })
        return result

    def _load_updates(self) -> dict:
        """从 GitHubActivity 插件目录加载全部更新记录。"""
        if not UPDATES_FILE.exists():
            return {}
        try:
            data = json.loads(UPDATES_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        meta = data.get("meta", {})
        return {
            "fetched_at": meta.get("fetched_at", ""),
            "summary": meta.get("summary", {}),
            "timeline": data.get("timeline", []),
            "by_repo": data.get("by_repo", {}),
        }

    def _count_total_words(self) -> int:
        """统计全站文章总字数（去除 Markdown 标记后的纯文本字数）。"""
        total = 0
        for post in self.posts:
            # 用简易方式剥 markdown，统计有效字符数
            clean = re.sub(r'[#*>`~\[\]()!_|`\-]', ' ', post.get("body_md", ""))
            clean = re.sub(r'\s+', '', clean)  # 去掉所有空白
            total += len(clean)
        return total

    def _collect_tags(self) -> list[dict]:
        """收集所有标签并统计出现次数（按数量降序排列）。"""
        tag_counts: dict[str, int] = {}
        for post in self.posts:
            for tag in post["metadata"].get("tags", []):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        return [{"name": k, "count": v} for k, v in sorted(tag_counts.items(), key=lambda x: (-x[1], x[0]))]

    def _random_sidebar_tags(self, count: int = 10) -> list[dict]:
        """从全站标签中随机选取若干（仅限文章数 ≥2 的标签），供侧栏精选展示。"""
        import random
        all_tags = [t for t in self._collect_tags() if t["count"] >= 2]
        if len(all_tags) <= count:
            return all_tags
        return random.sample(all_tags, count)

    def _summary(self, post: dict) -> dict:
        """生成文章摘要数据。"""
        meta = post["metadata"]
        m = re.match(r'(\d{4})\D+(\d{1,2})\D+(\d{1,2})', meta["time"])
        raw_date = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else ""
        return {
            "title": meta["title"],
            "date": self._format_date(meta["time"]),
            "raw_date": raw_date,                # YYYY-MM-DD，日历筛选用
            "url": post.get("url", f"posts/{post['slug']}.html"),
            "tags": meta.get("tags", []),
            "excerpt": meta.get("excerpt", ""),
        }

    def _nav_post(self, post: dict) -> dict:
        """生成上下篇导航数据（同目录内，仅文件名）。"""
        meta = post["metadata"]
        return {
            "title": meta["title"],
            "url": f"{post['slug']}.html",       # 文章都在 posts/ 下，相对链接无需前缀
        }

    def _format_date(self, date_str: str) -> str:
        """使用配置的日期格式。"""
        fmt = self.config.get("date_format", "%Y年%m月%d日")
        # 尝试解析标准化日期
        for py_fmt in ["%Y.%m.%d", "%Y.%#m.%#d", "%Y.%-m.%-d"]:
            try:
                dt = datetime.strptime(date_str, py_fmt)
                return dt.strftime(fmt)
            except ValueError:
                continue
        return date_str

    def _restore_from_cache(self, cache_key: str) -> Optional[dict]:
        """尝试从缓存恢复文章数据。（简化实现：下次总是重新解析）"""
        return None  # 增量模式下跳过已渲染文件，列表页总是全量重建

    # ═══════════════════════════════════════════════
    #  模板渲染
    # ═══════════════════════════════════════════════

    def _render_template(self, template_name: str, context: dict) -> str:
        """加载并渲染 Jinja2 模板。"""
        template = self.env.get_template(template_name)
        return template.render(**context)

    # ═══════════════════════════════════════════════
    #  RSS & Sitemap
    # ═══════════════════════════════════════════════

    def _generate_rss(self):
        """生成 RSS 2.0 Feed。"""
        site_url = self.config.get("site_url", "http://localhost")
        items = []
        for post in self.posts[:20]:
            meta = post["metadata"]
            rfc_date = self._to_rfc2822(meta["time"])
            item = f"""    <item>
      <title>{_xml_escape(meta['title'])}</title>
      <link>{site_url}/posts/{post['slug']}.html</link>
      <description>{_xml_escape(meta.get('excerpt', ''))}</description>
      <pubDate>{rfc_date}</pubDate>
      <guid isPermaLink="true">{site_url}/posts/{post['slug']}.html</guid>
    </item>"""
            items.append(item)

        now_rfc = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0800")
        rss_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{_xml_escape(self.config['site_title'])}</title>
    <link>{site_url}</link>
    <description>{_xml_escape(self.config['site_description'])}</description>
    <language>{self.config.get('language', 'zh-CN')}</language>
    <lastBuildDate>{now_rfc}</lastBuildDate>
    <atom:link href="{site_url}/feed.xml" rel="self" type="application/rss+xml"/>
{chr(10).join(items)}
  </channel>
</rss>"""
        (RENDERED_DIR / "feed.xml").write_text(rss_xml, encoding="utf-8")
        print("📡 RSS feed → feed.xml")

    def _generate_sitemap(self):
        """生成 sitemap.xml。"""
        site_url = self.config.get("site_url", "http://localhost")
        today = datetime.now().strftime("%Y-%m-%d")
        urls = [
            f"  <url><loc>{site_url}/index.html</loc><lastmod>{today}</lastmod><priority>1.0</priority></url>",
            f"  <url><loc>{site_url}/directory.html</loc><lastmod>{today}</lastmod><priority>0.8</priority></url>",
            f"  <url><loc>{site_url}/tags.html</loc><lastmod>{today}</lastmod><priority>0.6</priority></url>",
        ]
        for post in self.posts:
            urls.append(
                f"  <url><loc>{site_url}/posts/{post['slug']}.html</loc>"
                f"<lastmod>{today}</lastmod><priority>0.9</priority></url>"
            )

        sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n'
        sitemap += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        sitemap += "\n".join(urls)
        sitemap += "\n</urlset>"
        (RENDERED_DIR / "sitemap.xml").write_text(sitemap, encoding="utf-8")
        print("🗺️  Sitemap → sitemap.xml")

    @staticmethod
    def _to_rfc2822(date_str: str) -> str:
        """将 YYYY.M.D 格式的日期转为 RFC 2822 格式。"""
        for fmt in ["%Y.%m.%d", "%Y.%#m.%#d", "%Y.%-m.%-d"]:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime("%a, %d %b %Y 00:00:00 +0800")
            except ValueError:
                continue
        return datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0800")

    # ═══════════════════════════════════════════════
    #  静态资源 & 图片
    # ═══════════════════════════════════════════════

    def _copy_images(self):
        """将 Image/ 目录复制到 Rendered/images/（图片 → images/posts/，其他留根）。"""
        dest = RENDERED_DIR / "images"
        if not IMAGES_DIR.exists():
            return
        dest.mkdir(parents=True, exist_ok=True)
        total = 0
        posts_img = dest / "posts"
        for item in IMAGES_DIR.iterdir():
            if item.name.startswith(".") or item.name == "README.md":
                continue
            # 日期子目录 → images/posts/YYYY-M-DD/
            target = posts_img / item.name if item.is_dir() else dest / item.name
            try:
                if item.is_dir():
                    if target.exists():
                        shutil.rmtree(target)
                    shutil.copytree(item, target)
                else:
                    shutil.copy2(item, target)
                total += len(list(target.rglob("*"))) if item.is_dir() else 1
            except Exception as e:
                print(f"⚠️  复制 {item.name} 失败: {e}")
        if total:
            print(f"🖼️  复制了 {total} 个资源文件 → images/")

    def _copy_friends(self):
        """将友链项目文件复制到 Rendered/friends/。"""
        if not FRIENDS_SRC.exists():
            return
        dest = RENDERED_DIR / "friends"
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True)
        # 只复制有效子项目（排除 pyignore 和内部目录）
        copy_dirs = {
            "PinballChallenge", "sgsrecord", "fakemail", "xiyou", "genshin",
        }
        total = 0
        for name in copy_dirs:
            src = FRIENDS_SRC / name
            if not src.exists():
                continue
            try:
                shutil.copytree(src, dest / name)
                total += len(list((dest / name).rglob("*")))
            except Exception as e:
                print(f"⚠️  复制友链 {name} 失败: {e}")
        # 3500researcher 单独复制
        researcher_src = FRIENDS_SRC / "projects" / "3500researcher"
        if researcher_src.exists():
            try:
                shutil.copytree(researcher_src, dest / "3500researcher")
                total += len(list((dest / "3500researcher").rglob("*")))
            except Exception as e:
                print(f"⚠️  复制 3500researcher 失败: {e}")
        if total:
            print(f"🔗 友链项目: {len(copy_dirs)+1} 个子项目 → friends/")

    # ═══════════════════════════════════════════════
    #  Viewer 插件支持
    # ═══════════════════════════════════════════════

    def _copy_viewer_js(self):
        """将 Viewer 插件的 JS 文件复制到 Rendered/js/viewer/。"""
        if not VIEWER_JS_DIR.exists():
            return
        dest = RENDERED_DIR / "js" / "viewer"
        if dest.exists():
            shutil.rmtree(dest)
        try:
            shutil.copytree(VIEWER_JS_DIR, dest)
            count = len(list(dest.rglob("*.js")))
            print(f"📊 Viewer 插件: {count} 个 JS 文件 → js/viewer/")
        except Exception as e:
            print(f"⚠️  Viewer 插件复制失败: {e}")

    def _viewer_config(self) -> dict:
        """获取 Viewer 插件配置。"""
        return self.config.get("viewer", DEFAULT_CONFIG["viewer"])

    def _viewer_context(self, out_path: Path) -> dict:
        """构建 Viewer 相关的模板上下文。"""
        vc = self._viewer_config()
        pid = self._get_page_id(out_path)
        return {
            "page_id": pid,
            "viewer_user": vc.get("user", "aaaaa"),
            "viewer_secret": vc.get("secret", "d1bdf09a"),
            "viewer_counter": vc.get("enable_counter", True),
            "viewer_unique": vc.get("enable_unique", True),
            "viewer_global": vc.get("enable_global", True),
            "viewer_comment": vc.get("enable_comment", True),
        }

    # ═══════════════════════════════════════════════
    #  清理
    # ═══════════════════════════════════════════════

    def clean(self):
        """清空 Rendered 目录和缓存。"""
        if RENDERED_DIR.exists():
            shutil.rmtree(RENDERED_DIR)
        if CACHE_FILE.exists():
            CACHE_FILE.unlink()
        self.cache = {}
        print("🧹 已清空渲染目录和缓存")


# ── 工具函数 ──

def _parse_date_tuple(date_str: str) -> tuple:
    """将 'YYYY.M.D' 字符串解析为 (year, month, day) 元组用于正确排序。"""
    m = re.match(r'(\d{4})\D+(\d{1,2})\D+(\d{1,2})', str(date_str))
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return (0, 0, 0)


def _url_encode(s: str) -> str:
    """URL 编码（保留中文等非 ASCII 字符）。"""
    import urllib.parse
    return urllib.parse.quote(s, safe="/")


def _xml_escape(s: str) -> str:
    """转义 XML 特殊字符。"""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;")
