#!/usr/bin/env python3
"""
一键把本地博客接入 GitHub。

只做三件事：
  1. 用你的 Token 在 GitHub 上创建仓库
  2. 把本机 SSH 公钥挂到你的账号上，并推送源码到 main
  3. 构建 Rendered/ 并部署到 gh-pages，开启 GitHub Pages

Token 只在内存里使用，绝不写入任何文件、不进 Git 历史。

用法：
    .\\.venv\\Scripts\\python.exe setup_github.py                # 交互式输入 Token
    .\\.venv\\Scripts\\python.exe setup_github.py --token-file <文件>
    set GITHUB_TOKEN=ghp_xxx && .\\.venv\\Scripts\\python.exe setup_github.py
    .\\.venv\\Scripts\\python.exe setup_github.py --repo my-blog  # 自定义仓库名

安全约定：Token 只在内存里使用，绝不写入任何项目文件、不进 Git 历史、不被打印到屏幕上。
"""

import argparse
import getpass
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent
SITE_JSON = PROJECT_ROOT / "site.json"
API = "https://api.github.com"


# ═══════════════════════════════════════════
#  小工具
# ═══════════════════════════════════════════

def api(method: str, path: str, token: str, payload: dict = None) -> tuple[int, dict]:
    """调用 GitHub REST API。返回 (状态码, 响应体)。"""
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        API + path,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "OpenBlogger-Setup",   # GitHub 要求带 UA，缺了会被判 401
            **({"Content-Type": "application/json"} if data else {}),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8", "replace")
            return resp.status, (json.loads(body) if body else {})
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(body)
        except json.JSONDecodeError:
            return e.code, {"message": body}
    except Exception as e:
        return 0, {"message": str(e)}


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """在项目根目录执行 git 命令。"""
    return subprocess.run(
        cmd, cwd=str(PROJECT_ROOT), check=check,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


# ═══════════════════════════════════════════
#  Token 处理（全程脱敏，绝不打印）
# ═══════════════════════════════════════════

_SECRET_CACHE: list[str] = []


def scrub(text: str) -> str:
    """把输出里可能出现的 token 字符串替换成 ***，防止泄露到终端/日志。"""
    if not text:
        return text
    for secret in _SECRET_CACHE:
        if secret:
            text = text.replace(secret, "***")
    return text


def read_token_file(path: str) -> str:
    """从 Token 存放文件里读取：跳过注释行与空行，取第一个有效行。"""
    p = Path(path).expanduser()
    if not p.exists():
        print(f"❌ 找不到 Token 文件: {p}")
        sys.exit(1)
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # 支持 "TOKEN=xxx" / "token: xxx" / 直接一行 xxx 三种写法
        value = re.split(r"[=:]\s*", line, maxsplit=1)[-1].strip().strip('"').strip("'")
        return value.strip()
    print("❌ Token 文件里没有有效内容（去掉注释后是空的）")
    sys.exit(1)


def ask_secret(token_file: str | None) -> str:
    """安全地读取 Token：优先 --token-file > 环境变量 > 交互式输入。"""
    # 1) 指定的 Token 文件
    if token_file:
        tok = read_token_file(token_file)
        print(f"   ✅ 已从 {Path(token_file).name} 读取")
        return tok.strip()

    # 2) 环境变量
    tok = os.environ.get("GITHUB_TOKEN", "").strip()
    if tok:
        print("   ✅ 已从环境变量读取")
        return tok

    # 3) 桌面上的默认 Token 文件（若存在）
    desktop = Path.home() / "Desktop"
    for candidate in ("GitHub令牌.txt", "GitHub_Token.txt", "github_token.txt"):
        p = desktop / candidate
        if p.exists() and read_token_file(str(p)):
            tok = read_token_file(str(p))
            print(f"   ✅ 已从桌面 {candidate} 读取")
            return tok

    # 4) 手动输入
    print()
    print("请粘贴你的 GitHub Personal Access Token（不会显示在屏幕上）：")
    tok = getpass.getpass("  Token > ").strip()
    if tok.startswith(("$env:", "set ")):  # 常见粘贴误操作兜底
        tok = tok.split("=", 1)[-1].strip().strip('"').strip("'")
    return tok.strip()


# ═══════════════════════════════════════════
#  主流程
# ═══════════════════════════════════════════

def main():
    ap = argparse.ArgumentParser(description="把本地 OpenBlogger 博客一键接入 GitHub")
    ap.add_argument("--repo", "-r", default="MyBlog", help="仓库名（默认 MyBlog）")
    ap.add_argument("--private", action="store_true", help="创建私有仓库（默认公开）")
    ap.add_argument("--token-file", "-f", default=None, help="从指定文件读取 Token（推荐，避免手输）")
    args = ap.parse_args()

    repo_name = re.sub(r"[^A-Za-z0-9._-]", "-", args.repo).strip("-") or "MyBlog"

    print("=" * 52)
    print("  OpenBlogger → GitHub 一键接入")
    print("=" * 52)

    # ── Step 0: Token ──
    token = ask_secret(args.token_file)
    if not token:
        print("❌ 没有 Token，无法继续。")
        sys.exit(1)
    _SECRET_CACHE.append(token)   # 注册到脱敏表，后续所有输出自动打码

    # ── Step 1: 确认身份 ──
    print("\n[1/6] 验证 Token …")
    status, me = api("GET", "/user", token)
    if status != 200:
        print(f"❌ Token 无效或无权限（HTTP {status}）：{me.get('message')}")
        print("   请确认 Token 是 classic 类型且勾选了 repo 权限。")
        sys.exit(1)
    login = me["login"]
    print(f"   ✅ 当前身份: {login}")

    # ── Step 2: 创建仓库 ──
    print(f"\n[2/6] 检查仓库 {login}/{repo_name} …")
    status, repo = api("GET", f"/repos/{login}/{repo_name}", token)
    if status == 200:
        print(f"   ✅ 仓库已存在，直接使用")
    else:
        status, repo = api("POST", "/user/repos", token, {
            "name": repo_name,
            "description": "基于 OpenBlogger 的个人博客",
            "private": args.private,
            "auto_init": False,
        })
        if status not in (201, 200):
            print(f"❌ 创建仓库失败（HTTP {status}）：{repo.get('message')}")
            sys.exit(1)
        print(f"   ✅ 仓库已创建")
    ssh_url = repo.get("ssh_url") or f"git@github.com:{login}/{repo_name}.git"
    html_url = repo.get("html_url", f"https://github.com/{login}/{repo_name}")

    # ── Step 3: 挂载 SSH 公钥 ──
    print("\n[3/6] 挂载本机 SSH 公钥 …")
    pubkey_path = Path.home() / ".ssh" / "id_ed25519.pub"
    if not pubkey_path.exists():
        print("   ⚠️  未找到 ~/.ssh/id_ed25519.pub，跳过（将改用 Token 推送）")
        ssh_ready = False
    else:
        pubkey = pubkey_path.read_text(encoding="utf-8").strip()
        fingerprint = pubkey.split()[1][:16]
        status, keys = api("GET", "/user/keys", token)
        already = status == 200 and any(
            k.get("key", "").split()[1][:16] == fingerprint for k in keys if k.get("key")
        )
        if already:
            print("   ✅ 公钥已在账号上")
            ssh_ready = True
        else:
            status, res = api("POST", "/user/keys", token, {
                "title": f"MyBlog-{os.environ.get('COMPUTERNAME', 'PC')}",
                "key": pubkey,
            })
            ssh_ready = status in (201, 200)
            print("   ✅ 公钥已添加" if ssh_ready else f"   ⚠️  添加失败: {res.get('message')}")

    # ── Step 4: 修正 site.json 的真实网址 ──
    print("\n[4/6] 更新 site.json 的站点地址 …")
    if repo_name.lower() == f"{login.lower()}.github.io":
        site_url = f"https://{login.lower()}.github.io"
    else:
        site_url = f"https://{login.lower()}.github.io/{repo_name}"
    try:
        cfg = json.loads(SITE_JSON.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        cfg = {}
    old_url = cfg.get("site_url", "")
    cfg["site_url"] = site_url
    if not cfg.get("author") or cfg.get("author") == "":
        cfg["author"] = login
    SITE_JSON.write_text(json.dumps(cfg, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    print(f"   ✅ {old_url}  →  {site_url}")

    # ── Step 5: 推送源码 ──
    print("\n[5/6] 推送源码到 main …")
    remotes = run(["git", "remote"], check=False).stdout.split()
    if "origin" in remotes:
        run(["git", "remote", "remove", "origin"], check=False)
    run(["git", "remote", "add", "origin", ssh_url])
    run(["git", "add", "-A"])
    run(["git", "commit", "-m", "初始化博客：OpenBlogger 骨架 + 空文章数据"], check=False)
    run(["git", "branch", "-M", "main"], check=False)

    # 先把 GitHub 的主机指纹写进 known_hosts，避免首次 SSH 卡在 yes/no 确认上
    def trust_hosts():
        """预置 GitHub / ssh.github.com 的主机指纹。失败也不致命（GIT_SSH_COMMAND 还有兜底）。"""
        tool = shutil.which("ssh-keyscan")
        if not tool:
            # Windows 上 ssh-keyscan 常常不在 PATH 里，去 OpenSSH 目录捞一下
            for p in (Path(r"C:\Windows\System32\OpenSSH\ssh-keyscan.exe"),
                      Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "OpenSSH" / "ssh-keyscan.exe"):
                if p.exists():
                    tool = str(p)
                    break
        if not tool:
            print("   ⚠️  找不到 ssh-keyscan，改用 SSH 自动接受指纹")
            return False
        kh = Path.home() / ".ssh" / "known_hosts"
        kh.parent.mkdir(parents=True, exist_ok=True)
        try:
            existing = {l.split()[0] for l in kh.read_text(encoding="utf-8", errors="ignore").splitlines() if l.strip()}
        except OSError:
            existing = set()
        new_lines = []
        for host in ("github.com", "ssh.github.com"):
            r = subprocess.run([tool, "-T", "20", "-t", "rsa,ecdsa,ed25519", host],
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
            for line in r.stdout.splitlines():
                if line.strip() and not line.startswith("#") and line.split()[0] not in existing:
                    new_lines.append(line)
        if new_lines:
            with kh.open("a", encoding="utf-8") as f:
                f.write("\n".join(new_lines) + "\n")
        return bool(new_lines)

    try:
        trust_hosts()
    except Exception:
        pass

    # 兜底：让 SSH 自动接受并保存未知主机指纹，避免非交互式场景卡死
    os.environ["GIT_SSH_COMMAND"] = "ssh -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=15"

    pushed = False
    working_url = ssh_url
    attempts = []
    if ssh_ready:
        attempts.append(("SSH 22 端口", ssh_url))
        attempts.append(("SSH 443 端口（穿透用）", f"ssh://git@ssh.github.com:443/{login}/{repo_name}.git"))
    attempts.append(("HTTPS（带 Token）", f"https://{login}:{token}@github.com/{login}/{repo_name}.git"))

    for label, url in attempts:
        run(["git", "remote", "set-url", "origin", url], check=False)
        r = run(["git", "push", "-u", "origin", "main"], check=False)
        if r.returncode == 0:
            pushed = True
            if label.startswith("SSH"):
                # 干净的地址，长期保留
                working_url = ssh_url
                run(["git", "remote", "set-url", "origin", ssh_url], check=False)
            else:
                # 含 Token，先留着推完 gh-pages，最后再换掉
                working_url = url
            print(f"   ✅ 源码已推送（{label}）")
            break
        print(f"   ⚠️  {label} 推送失败：{scrub(r.stderr.strip())[:200]}")

    if not pushed:
        print("❌ 三种通道都推不动。多半是本机到 GitHub 的网络被干扰，换个网络再试一次即可。")
        sys.exit(1)

    # ── Step 6: 构建 + 部署 gh-pages ──
    print("\n[6/6] 构建并部署 gh-pages …")
    env = {**os.environ, "PYTHONPATH": str(PROJECT_ROOT), "PYTHONIOENCODING": "utf-8"}
    b = subprocess.run(
        [sys.executable, "-m", "OpenBlogger.cli", "build", "--force"],
        cwd=str(PROJECT_ROOT), env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    if b.returncode != 0:
        print(f"❌ 构建失败: {b.stderr[-500:]}")
        sys.exit(1)
    print("   ✅ 构建完成")

    run(["git", "add", "-f", "Rendered/"], check=False)
    run(["git", "commit", "-m", "gh-pages deploy [auto]"], check=False)
    run(["git", "subtree", "split", "--prefix", "Rendered", "-b", "_ghp_tmp"], check=False)
    run(["git", "remote", "set-url", "origin", working_url], check=False)
    p = run(["git", "push", "origin", "_ghp_tmp:gh-pages", "--force"], check=False)
    run(["git", "branch", "-D", "_ghp_tmp"], check=False)
    run(["git", "reset", "--soft", "HEAD~1"], check=False)
    run(["git", "reset", "HEAD", "Rendered/"], check=False)
    # 清掉可能含 Token 的远端地址，确保 .git/config 里不留任何凭据
    run(["git", "remote", "set-url", "origin", ssh_url], check=False)
    if p.returncode != 0:
        print(f"   ⚠️  gh-pages 推送失败: {scrub(p.stderr.strip())[:300]}")
    else:
        print("   ✅ gh-pages 已部署")

    # 开启 GitHub Pages（可能需要几分钟生效）
    status, res = api("PUT", f"/repos/{login}/{repo_name}/pages", token,
                      {"source": {"branch": "gh-pages", "path": "/"}})
    if status in (201, 200, 204):
        print(f"   ✅ GitHub Pages 已开启")
    else:
        print(f"   ⚠️  Pages 未能自动开启，请到 {html_url}/settings/pages 手动选择 gh-pages 分支")

    print()
    print("=" * 52)
    print("  🎉 完成")
    print(f"     仓库:  {html_url}")
    print(f"     博客:  {site_url}")
    print("     Pages 首次发布需要等待 1~3 分钟")
    print()
    print("  以后每天写完日志，双击「控制台.bat」按 7 即可")
    print("=" * 52)


if __name__ == "__main__":
    main()
