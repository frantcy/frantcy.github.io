# MyBlog

基于 [OpenBlogger](https://github.com/YHSome/OpenBlogger) 的轻量级静态博客。**文章数据已清空**，从今天起你可以每天在这里写日志。

## 目录结构

```
MyBlog/
├── Raw/                  ← 你的 Markdown 原文（唯一需要你动手的地方）
│   └── 日记/2026年09月29日.md    子目录名会自动变成标签
├── Image/                ← 图片等静态资源（含 favicon.jpg）
├── Rendered/             ← 构建输出，不用管（已 gitignore）
├── OpenBlogger/          ← 渲染引擎 + 模板（一般不用改）
├── site.json             ← 站点配置（标题 / 作者 / 简介 / 网址）
├── .venv/                ← 本机 Python 虚拟环境，已装好依赖
├── 控制台.bat             ← 日常操作面板（推荐）
├── serve.bat             ← 本地预览
├── build.bat             ← 只构建不预览
└── deploy.bat            ← 发布到 GitHub Pages
```

## 每天写日志

1. 双击 **`控制台.bat`**，按 `1` 打开 `Raw` 文件夹
2. 新建 `.md` 文件，按下面格式写：

```
time: 2026.9.29
tag: 日记
title: 今天做了什么

正文从这里开始写。
```

3. 回到控制台按 `3` 预览，浏览器会自动打开 http://localhost:8080
4. 满意后按 `7`（源码 + 线上一起推送）

## Markdown 头部字段

| 字段 | 说明 | 缺省时 |
| --- | --- | --- |
| `time` | 日期，支持 `2026.9.29` / `2026-09-29` / `2026.09.29` | 自动填今天 |
| `tag` | 标签，逗号或空格分隔 | 用上层目录名，都没有则「未分类」 |
| `title` | 标题 | 自动取正文第一句（超 20 字加省略号） |
| `author` | 作者 | 取 `site.json` 里的 `author` |

只有前两种字段是必须由你写的 —— 其实一个都不写也能渲染，引擎会自己补全。

## 换主题

`site.json` 里改 `"theme"`：`default`（米色暖调，默认）或 `scifi`（科技风）。

## 发布到 GitHub Pages

仓库需开启 Pages，分支选 `gh-pages`。`deploy.bat` 会把 `Rendered/` 用 subtree 推到该分支。

第一次部署前，把 `site.json` 里的 `"site_url"` 改成你的真实地址。

## 可选增强

- **GitHub 活动时间线**：在 `site.json` 配好后运行
  `.\.venv\Scripts\python.exe OpenBlogger\Plugins\GitHubActivity\fetch.py --user 你的GitHub用户名`
  在 `site.json` 的 `github_token` 填 token 可提高 API 限额。
- **站点图标**：放一张 `favicon.jpg` 到 `Image/` 目录。
- **访问统计 / 评论**：`site.json` 的 `viewer` 段。

## 命令行等价操作

```bat
.\.venv\Scripts\python.exe -m OpenBlogger.cli build --force   :: 构建
.\.venv\Scripts\python.exe -m OpenBlogger.cli serve           :: 预览
.\.venv\Scripts\python.exe -m OpenBlogger.cli watch           :: 改文件自动重建
```
