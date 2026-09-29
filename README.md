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

## 每天写日志（推荐流程）

1. 双击 **`控制台.bat`**，按 **`1`**
2. 自动建好 `Raw\日记\2026年09月29日.md` 并打开编辑器，直接开写：

```
time: 2026.9.29
tag: 日记
title: 2026年09月29日

今天……
```

头部三行（`time` / `tag` / `title`）不用管，脚本已经填好，**你只写正文**。

3. 保存 → 回到控制台按 **`3`** 预览，浏览器自动打开 http://localhost:8080
4. 满意后按 **`7`** —— 源码推 GitHub + 线上同步更新，1~3 分钟生效

> `Raw` 下的**子目录名会自动变成标签**：放 `Raw\日记\` 里的文章自动带「日记」标签，
> 放 `Raw\技术\` 就自动带「技术」标签，不用手动归类。
>
> 同一天写第二篇？再按一次 `1`，脚本检测到今天的文件已存在，会直接打开而不覆盖。
> 想换个分类写，用 `.\.venv\Scripts\python.exe new_post.py --dir 随笔`。

## 在手机上写日志

用手机打开博客 → 点底部导航栏 **目录** → 标题右边有个 **＋ 写今天** 按钮
（右下角还有一个悬浮的圆形 ＋ 按钮，同一个入口）：

1. 第一次用会让你填一次 GitHub 令牌，之后这台手机就记住了
2. 选日期、分类（决定标签）、写标题和正文 → 点 **保存并上传**
3. 文件直接以 `Raw/分类/YYYY年MM月DD日.md` 提交到 GitHub 的 `main` 分支
4. GitHub Actions 自动接管：构建 → 推到 `gh-pages`，**约 1~2 分钟**后线上就能看到

> 令牌只存在你自己手机的浏览器 localStorage 里，不会发到任何第三方。
> 建议用 **fine-grained token**，只勾本仓库的 `Contents: Read and write`。
> 要换令牌：写文章页面最下面有「换一个令牌」。

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

仓库需开启 Pages，分支选 `gh-pages`。

两种方式发布，推荐第一种：

- **自动（推荐）**：`.github/workflows/deploy.yml` 已经在跑。任何推送到 `main` 的动作
  （电脑上双击 `deploy.bat` / 控制台 `7`，或手机端写文章上传）都会触发
  Actions 自动 `build` → 推 `gh-pages`，不用手工操作.
- **手动**：`控制台.bat` → `7`（源码推 GitHub + 本地构建 + subtree 推 gh-pages）。

第一次部署前，把 `site.json` 里的 `"site_url"` 改成你的真实地址。

## 可选增强

- **GitHub 活动时间线**：在 `site.json` 配好后运行
  `.\.venv\Scripts\python.exe OpenBlogger\Plugins\GitHubActivity\fetch.py --user 你的GitHub用户名`
  在 `site.json` 的 `github_token` 填 token 可提高 API 限额。
- **站点图标**：放一张 `favicon.jpg` 到 `Image/` 目录。
- **访问统计**：`site.json` 的 `viewer` 段，`enable_counter / enable_unique / enable_global`
  分别对应页脚的「次阅读 / 位访客 / 次全站浏览」。
  数据来自 **不蒜子**（`busuanzi.js`），按你的域名独立统计，是本站自己的真实数据，
  不用注册账号；拿不到数据时会显示 `—`，不影响其它功能。
- **评论（giscus / GitHub Discussions）**：评论存在仓库的 Discussions 里，免后端、免注册。
  配置在 `site.json` 的 `giscus` 段（仓库名、仓库 ID、分类名、分类 ID 都已填好），
  开关是 `viewer.enable_comment`。giscus 应用已安装完成，可以直接用。
  > 用 `data-mapping="specific"` + 文章**固定链接**做映射（不是 pathname）。
  > 这样本地预览和线上访问同一篇文章会落到同一篇讨论里，改了文件名评论也不会丢。
- **弹幕栏**：原「精选发言」依赖可读的评论正文，giscus 跑在跨域 iframe 里读不到，
  所以默认关闭（`viewer.enable_danmaku`）。HTML/CSS 都还在，将来有可读评论源时打开即可。
- **友链**：编辑 `Plugins/FriendLinks/links.json`，格式见文件里的 `_说明`。

## 命令行等价操作

```bat
.\.venv\Scripts\python.exe -m OpenBlogger.cli build --force   :: 构建
.\.venv\Scripts\python.exe -m OpenBlogger.cli serve           :: 预览
.\.venv\Scripts\python.exe -m OpenBlogger.cli watch           :: 改文件自动重建
```
