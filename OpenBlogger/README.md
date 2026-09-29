# OpenBlogger

一个轻量级静态博客渲染引擎。Markdown 写文章，Python 一键生成完整站点。

## 快速开始

```bash
git clone --recurse-submodules https://github.com/YHSome/yhsome.github.io.git
cd yhsome.github.io
pip install -r requirements.txt
双击 控制台.bat → [3] 本地预览
```

## 项目结构

```
OpenBlogger/
├── renderer.py              # 核心渲染引擎
├── cli.py                   # 命令行工具
├── import_legacy.py         # Hexo 旧博客导入工具
├── Template/Default/        # HTML 模板（6 页）
│   ├── Homepage.html        # 首页：三栏布局 + 弹幕
│   ├── Directory.html       # 目录：搜索 + 标签过滤 + 年月分组
│   ├── Post.html            # 文章：侧栏 + 正文 + 评论
│   ├── Tag.html             # 标签：悬停展开文章列表
│   ├── Projects.html        # 项目：GitHub 仓库展示
│   └── Links.html           # 友链：旧项目导航
└── Plugins/Viewer/          # 内置插件
    ├── js/                  # 访问计数 + 评论系统
    └── tools/               # 页面编号管理
```

## 功能

| 功能 | 说明 |
|------|------|
| Markdown 渲染 | extra/codehilite/toc/sane_lists/smarty 扩展 |
| 元数据解析 | 文章头部 `key: value` 格式，自动补全日期/标题 |
| 增量构建 | 文件哈希缓存，只重建变更页面 |
| RSS + Sitemap | 自动生成 |
| 暗色模式 | 零闪屏（head 同步脚本） |
| 页面转场 | CSS cubic-bezier 弹入飞出 |
| 代码高亮 | Pygments |
| 友链项目 | 构建时自动复制 |
| 弹幕 | 全站评论滚动 |

## 模板变量

所有模板使用 Jinja2 语法。以下是各页面可用的主要变量：

**Post.html**
```
{{ title }} {{ date }} {{ tags }} {{ content }} {{ author }}
{{ prev_post }} {{ next_post }} {{ relative_root }}
{{ total_posts }} {{ total_words }} {{ sidebar_tags }}
{{ page_id }} {{ viewer_user }} {{ viewer_secret }}
```

**Homepage.html**
```
{{ site_title }} {{ site_description }}
{{ recent_posts }} {{ all_tags }} {{ total_posts }} {{ total_words }}
{{ max_page_id }} {{ relative_root }}
```

**Directory.html**
```
{{ all_posts }} {{ all_tags }} {{ active_tag }}
```

**Tag.html**
```
{{ tags_with_count }}  ← 含 posts 列表用于悬停弹出
```

**Projects.html**
```
{{ projects }}  ← 从 projects.json 加载
```

**Links.html**
```
{{ link_sections }}  ← 硬编码在 renderer 中
```

## 插件系统

插件放在 `Plugins/` 目录（博客项目根），与 OpenBlogger 框架分离。

内置插件：
- **Viewer** (`OpenBlogger/Plugins/Viewer/`)：纯前端访问计数 + 评论，基于 TinyWebDB

博客专属插件示例：
- **GitHubProjects** (`Plugins/GitHubProjects/`)：拉取 GitHub 仓库列表展示

## CLI 命令

```bash
python -m OpenBlogger.cli build                # 构建站点
python -m OpenBlogger.cli build --force        # 强制全量重建
python -m OpenBlogger.cli build --theme modern # 使用指定主题
python -m OpenBlogger.cli serve                # 预览站点
python -m OpenBlogger.cli serve --port 9090    # 指定端口
python -m OpenBlogger.cli clean                # 清空输出
```

## 部署

```bash
# 将 Rendered/ 推送到 GitHub Pages
git subtree push --prefix Rendered origin gh-pages
```

或使用博客项目自带的 `deploy.bat` 一键部署。

## 依赖

- Python 3.9+
- markdown
- Jinja2
- Pygments
- beautifulsoup4（仅 import_legacy.py 需要）
- html2text（仅 import_legacy.py 需要）

## 许可

MIT
