#!/usr/bin/env python3
"""
GitHubActivity 插件 — 抓取指定用户近七天的 GitHub 公开活动记录。

用法:
    python OpenBlogger/Plugins/GitHubActivity/fetch.py              # 抓取 YHSome 的活动
    python OpenBlogger/Plugins/GitHubActivity/fetch.py --user  xxx  # 抓取指定用户
    python OpenBlogger/Plugins/GitHubActivity/fetch.py --days  14   # 指定天数（默认 7）

输出:
    updates.json — 保存至本插件文件夹
"""

import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timezone, timedelta

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── 项目根路径 ──
PROJECT_ROOT = Path(__file__).resolve().parents[3]
SITE_CONFIG  = PROJECT_ROOT / "site.json"
PLUGIN_DIR   = Path(__file__).resolve().parent
OUTPUT_FILE  = PLUGIN_DIR / "updates.json"
CACHE_FILE   = PLUGIN_DIR / ".fetch_cache.json"

# ═══════════════════════════════════════════════════════
#  工具函数
# ═══════════════════════════════════════════════════════

EVENT_LABELS = {
    "PushEvent":          "📤 推送了代码",
    "CreateEvent":        "🆕 创建了",
    "DeleteEvent":        "🗑️ 删除了",
    "PullRequestEvent":   "🔀 PR",
    "PullRequestReviewEvent": "👀 审查了 PR",
    "IssuesEvent":        "📝 Issue",
    "IssueCommentEvent":  "💬 评论了 Issue",
    "WatchEvent":         "⭐ Star 了",
    "ForkEvent":          "🍴 Fork 了",
    "ReleaseEvent":       "🎉 发布了",
    "PublicEvent":        "🌐 公开了仓库",
    "MemberEvent":        "👥 协作者",
    "GollumEvent":        "📚 Wiki",
}

EVENT_ICONS = {
    "PushEvent":          "📤",
    "CreateEvent":        "🆕",
    "DeleteEvent":        "🗑️",
    "PullRequestEvent":   "🔀",
    "PullRequestReviewEvent": "👀",
    "IssuesEvent":        "📝",
    "IssueCommentEvent":  "💬",
    "WatchEvent":         "⭐",
    "ForkEvent":          "🍴",
    "ReleaseEvent":       "🎉",
    "PublicEvent":        "🌐",
    "MemberEvent":        "👥",
    "GollumEvent":        "📚",
}


def load_token() -> str:
    """从 site.json 加载 github_token。"""
    if not SITE_CONFIG.exists():
        return ""
    try:
        cfg = json.loads(SITE_CONFIG.read_text(encoding="utf-8"))
        return cfg.get("github_token", "")
    except Exception:
        return ""


def api_request(url: str, token: str = "") -> dict | list:
    """发送 GitHub API 请求，返回解析后的 JSON。"""
    headers = {"User-Agent": "OpenBlogger-GitHubActivity", "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def paginated_fetch(url_base: str, token: str, max_pages: int = 5) -> list:
    """分页抓取 GitHub API，合并结果。"""
    all_items = []
    page = 1
    while page <= max_pages:
        url = f"{url_base}&per_page=100&page={page}"
        try:
            items = api_request(url, token)
        except urllib.error.HTTPError as e:
            print(f"⚠️  API 错误 (第{page}页): {e.code} {e.reason}")
            break
        if not isinstance(items, list) or not items:
            break
        all_items.extend(items)
        if len(items) < 100:
            break    # 最后一页
        page += 1
    return all_items


def format_ref(ref: str) -> str:
    """格式化 Git ref 为简短可读形式。"""
    if not ref:
        return ""
    for prefix in ("refs/heads/", "refs/tags/"):
        if ref.startswith(prefix):
            return ref[len(prefix):]
    return ref


def format_event(e: dict) -> dict:
    """将原始 API 事件格式化为紧凑可读的结构。"""
    etype = e.get("type", "")
    repo  = e["repo"]["name"] if "repo" in e else ""
    ts    = e.get("created_at", "")
    payload = e.get("payload", {})

    # 解析时间
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        dt = datetime.now(timezone.utc)

    result = {
        "type": etype,
        "icon": EVENT_ICONS.get(etype, "❓"),
        "label": EVENT_LABELS.get(etype, etype),
        "repo": repo,
        "repo_url": f"https://github.com/{repo}" if repo else "",
        "time": dt.strftime("%Y-%m-%d %H:%M UTC"),
        "timestamp": dt.isoformat(),
        "id": e.get("id", ""),
    }

    # ── 根据事件类型提取额外信息 ──
    if etype == "PushEvent":
        commits = payload.get("commits", [])
        result["ref"] = format_ref(payload.get("ref", ""))
        result["commit_count"] = len(commits)
        result["messages"] = [c.get("message", "").split("\n")[0] for c in commits]

    elif etype == "CreateEvent":
        result["ref_type"] = payload.get("ref_type", "")
        result["ref"] = format_ref(payload.get("ref", ""))
        result["detail"] = f"{result['ref_type']} {result['ref']}" if result['ref'] else result['ref_type']

    elif etype == "DeleteEvent":
        result["ref_type"] = payload.get("ref_type", "")
        result["ref"] = format_ref(payload.get("ref", ""))

    elif etype == "PullRequestEvent":
        pr = payload.get("pull_request", {})
        result["action"] = payload.get("action", "")
        result["title"] = pr.get("title", "")
        result["pr_url"] = pr.get("html_url", "")
        result["merged"] = pr.get("merged", False)

    elif etype == "IssuesEvent":
        issue = payload.get("issue", {})
        result["action"] = payload.get("action", "")
        result["title"] = issue.get("title", "")
        result["issue_url"] = issue.get("html_url", "")

    elif etype == "IssueCommentEvent":
        issue = payload.get("issue", {})
        result["action"] = payload.get("action", "")
        result["title"] = issue.get("title", "")
        result["issue_url"] = issue.get("html_url", "")

    elif etype == "ReleaseEvent":
        rel = payload.get("release", {})
        result["action"] = payload.get("action", "")
        result["tag_name"] = rel.get("tag_name", "")
        result["release_url"] = rel.get("html_url", "")
        result["release_name"] = rel.get("name", "")
        result["prerelease"] = rel.get("prerelease", False)

    elif etype == "WatchEvent":
        result["action"] = payload.get("action", "")

    elif etype == "ForkEvent":
        forkee = payload.get("forkee", {})
        result["fork_name"] = forkee.get("full_name", "")

    return result


def filter_recent(events: list, days: int) -> list:
    """筛出近 N 天的事件。"""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    filtered = []
    for e in events:
        try:
            dt = datetime.fromisoformat(e.get("created_at", "").replace("Z", "+00:00"))
        except Exception:
            dt = datetime.now(timezone.utc)
        if dt >= cutoff:
            filtered.append(e)
    return filtered


def group_by_repo(events: list) -> dict:
    """按仓库分组事件。"""
    groups: dict[str, list] = {}
    for e in events:
        repo = e.get("repo", "unknown")
        groups.setdefault(repo, []).append(e)
    return groups


def summarize(events: list) -> dict:
    """汇总统计。"""
    types = {}
    repos_set = set()
    total_commits = 0
    for e in events:
        t = e.get("type", "")
        types[t] = types.get(t, 0) + 1
        repos_set.add(e.get("repo", ""))
        total_commits += e.get("commit_count", 0)
    return {
        "total_events": len(events),
        "total_repos": len(repos_set),
        "total_commits": total_commits,
        "by_type": [{ "type": k, "count": v } for k, v in sorted(types.items(), key=lambda x: -x[1])],
        "repos": sorted(repos_set),
    }


def enrich_push_events(events: list, token: str, days: int) -> list:
    """对于 messages 为空的 PushEvent，通过 Commits API 补全提交消息。"""
    # 收集需要补全的仓库
    repos_need = set()
    for e in events:
        if e.get("type") == "PushEvent" and not e.get("messages"):
            repos_need.add(e.get("repo", ""))

    if not repos_need:
        return events

    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    repo_commits: dict[str, list[dict]] = {}

    for repo in repos_need:
        url = f"https://api.github.com/repos/{repo}/commits?since={since}&per_page=30"
        try:
            raw = api_request(url, token)
        except Exception:
            continue
        if not isinstance(raw, list):
            continue
        commits = []
        for c in raw:
            sha = c.get("sha", "")[:8]
            msg = (c.get("commit", {}).get("message", "") or "").split("\n")[0]
            date = c.get("commit", {}).get("author", {}).get("date", "")
            commits.append({"sha": sha, "message": msg, "date": date})
        repo_commits[repo] = commits

    # 按日期匹配：给同一天内的 PushEvent 补上 commits
    for e in events:
        if e.get("type") != "PushEvent" or e.get("messages"):
            continue
        repo = e.get("repo", "")
        commits = repo_commits.get(repo, [])
        if not commits:
            continue
        event_date = e.get("time", "")[:10]  # YYYY-MM-DD
        matched = [c for c in commits if c["date"][:10] == event_date]
        if matched:
            e["messages"] = [c["message"] for c in matched]
            e["commit_count"] = len(matched)

    return events


# ═══════════════════════════════════════════════════════
#  主流程
# ═══════════════════════════════════════════════════════

def fetch_all_commits(user: str, token: str) -> list[dict]:
    """拉取用户所有仓库的全部 commits（分页遍历每仓库最多 10 页），
    生成时间线条目（与 Events API 格式一致）。"""
    # 1. 获取所有仓库
    repos_url = f"https://api.github.com/users/{user}/repos?sort=updated&per_page=100"
    try:
        repos = paginated_fetch(repos_url, token, max_pages=2)
    except Exception as e:
        print(f"   ⚠️  获取仓库列表失败: {e}")
        return []

    if not isinstance(repos, list):
        return []

    print(f"   📦 共 {len(repos)} 个仓库，正在拉取全部 commit 记录…")
    all_entries = []
    seen_shas = set()

    for i, repo in enumerate(repos):
        repo_name = repo.get("full_name", "")
        if not repo_name:
            continue
        try:
            commits = paginated_fetch(
                f"https://api.github.com/repos/{repo_name}/commits?",
                token, max_pages=10,
            )
        except Exception:
            continue
        if not isinstance(commits, list):
            continue
        if (i + 1) % 5 == 0:
            print(f"   ... {i+1}/{len(repos)} 仓库已处理")

        for c in commits:
            sha = c.get("sha", "")
            if sha in seen_shas:
                continue
            seen_shas.add(sha)

            commit_data = c.get("commit", {})
            author_data = commit_data.get("author", {})
            date_str = author_data.get("date", "")
            try:
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except Exception:
                continue

            msg = (commit_data.get("message", "") or "").split("\n")[0]
            entry = {
                "type": "PushEvent",
                "icon": "📤",
                "label": "📤 推送了代码",
                "repo": repo_name,
                "repo_url": f"https://github.com/{repo_name}",
                "time": dt.strftime("%Y-%m-%d %H:%M UTC"),
                "timestamp": dt.isoformat(),
                "id": sha[:8],
                "ref": "",
                "commit_count": 1,
                "messages": [msg],
            }
            all_entries.append(entry)

    # 按时间倒序
    all_entries.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
    return all_entries


def fetch(user: str = "YHSome", force: bool = False):
    """抓取 GitHub 全部公开活动事件并保存。"""

    # 检查缓存（10 分钟内不重复请求，除非 --force）
    if not force and CACHE_FILE.exists():
        try:
            cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            if time.time() - cache.get("ts", 0) < 600:
                print(f"⏭️  上次抓取于 {datetime.fromtimestamp(cache['ts']).strftime('%H:%M:%S')}，跳过（--force 可强制）")
                return
        except Exception:
            pass

    token = load_token()
    if token:
        print("   🔑 使用 token 认证（5000 次/小时）")
    else:
        print("   ⚠️  未配置 token（60 次/小时），将只拉取公开数据")

    # ── 阶段 1：拉取全部 commits（主力数据源，覆盖 180 天） ──
    print(f"🔍 正在拉取 {user} 的全部 commit 记录…")
    commit_entries = fetch_all_commits(user, token)
    print(f"   📥 获取 {len(commit_entries)} 条 commit（去重后）")

    # ── 阶段 2：拉取 Events API（补充 PR/Issue/Star/Fork 等非 commit 事件） ──
    events_url = f"https://api.github.com/users/{user}/events?sort=created"
    print(f"🔍 正在拉取事件 API（PR/Issue/Star…）")
    try:
        raw_events = paginated_fetch(events_url, token, max_pages=10)
    except Exception as e:
        print(f"   ⚠️  Events API 失败: {e}，继续")
        raw_events = []
    print(f"   📥 获取 {len(raw_events)} 条事件")

    # 格式化非 Push 类事件
    event_entries = []
    for e in raw_events:
        if e.get("type") != "PushEvent":
            event_entries.append(format_event(e))
    print(f"   📥 其中非 Push 事件: {len(event_entries)} 条")

    # ── 合并并去重 ──
    seen_ids = set()
    # 先在 commit 条目中记录 id
    for ce in commit_entries:
        seen_ids.add(ce["id"])

    # 事件条目中的 PushEvent 已经由 commits 覆盖，只保留非 Push
    merged = list(commit_entries)
    for ev in event_entries:
        eid = ev.get("id", "")
        if eid not in seen_ids:
            seen_ids.add(eid)
            merged.append(ev)

    # 按时间倒序
    merged.sort(key=lambda e: e.get("timestamp", ""), reverse=True)

    if not merged:
        output = {
            "meta": {"user": user, "fetched_at": datetime.now(timezone.utc).isoformat(), "summary": summarize([])},
            "events": [],
        }
        OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✅ 无活动，已保存空记录 → {OUTPUT_FILE}")
        return

    formatted = merged

    # 按仓库分组
    by_repo = group_by_repo(formatted)

    # 构建输出
    output = {
        "meta": {
            "user": user,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "summary": summarize(formatted),
        },
        "by_repo": {
            repo: {
                "url": f"https://github.com/{repo}",
                "event_count": len(evs),
                "events": evs,
            }
            for repo, evs in sorted(by_repo.items())
        },
        "timeline": formatted,
    }

    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ 已保存 {len(formatted)} 条活动记录 → {OUTPUT_FILE}")

    # 摘要
    s = output["meta"]["summary"]
    print(f"\n📊 摘要：{s['total_events']} 条事件 · {s['total_repos']} 个仓库 · {s['total_commits']} 次提交")
    for item in s["by_type"]:
        icon = EVENT_ICONS.get(item["type"], "❓")
        print(f"   {icon} {item['type']:30s} × {item['count']}")

    # 保存缓存时间戳
    CACHE_FILE.write_text(json.dumps({"ts": time.time()}), encoding="utf-8")


# ═══════════════════════════════════════════════════════
#  命令行入口
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="GitHubActivity — 抓取 GitHub 用户全部公开活动记录",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python OpenBlogger/Plugins/GitHubActivity/fetch.py
  python OpenBlogger/Plugins/GitHubActivity/fetch.py --user torvalds --force
""",
    )
    parser.add_argument("--user", "-u", default="YHSome", help="GitHub 用户名 (默认: YHSome)")
    parser.add_argument("--days", "-d", type=int, help=argparse.SUPPRESS)  # 已废弃，保留兼容
    parser.add_argument("--force", "-f", action="store_true", help="忽略 10 分钟缓存，强制重新抓取")
    args = parser.parse_args()

    fetch(user=args.user, force=args.force)
