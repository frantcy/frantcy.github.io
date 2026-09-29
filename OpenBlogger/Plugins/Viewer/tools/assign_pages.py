#!/usr/bin/env python3
"""
Viewer — 页面编号脚本

扫描目录下所有 .html 文件，为每个页面分配唯一 ID。
已编号的页面保留原编号；新页面获得一个全新的、从未用过的 ID。
即使某个 HTML 文件被删除，其 ID 也永远不会被分配给其他页面。

编号记录持久化存储在 .viewer_pages.json 中。

用法：
    python assign_pages.py [目录路径]
"""

import os
import sys
import re
import json

META_TAG = '<meta name="x-viewer-page-id" content="{page_id}">'

# 记录文件放在脚本自身所在目录（tools/）
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RECORD_FILE = os.path.join(SCRIPT_DIR, '.viewer_pages.json')


def find_html_files(directory):
    """扫描目录下所有 .html 文件，按文件名排序"""
    files = sorted(
        f for f in os.listdir(directory)
        if f.endswith('.html') and os.path.isfile(os.path.join(directory, f))
    )
    return files


def extract_page_id(html_path):
    """从 HTML 的 meta 标签中提取已分配的 page id，没有则返回 None"""
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()
        match = re.search(r'<meta\s+name="x-viewer-page-id"\s+content="(\d+)"\s*/?>', content)
        if match:
            return int(match.group(1))
    except Exception:
        pass
    return None


def load_records():
    """加载持久化编号记录"""
    if os.path.isfile(RECORD_FILE):
        try:
            with open(RECORD_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_records(records):
    """保存编号记录"""
    path = RECORD_FILE
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def inject_page_id(html_path, page_id):
    """在 HTML 的 <head> 中注入/更新 page id meta 标签"""
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()

    if re.search(r'<meta\s+name="x-viewer-page-id"\s+content="\d+"\s*/?>', content):
        content = re.sub(
            r'<meta\s+name="x-viewer-page-id"\s+content="\d+"\s*/?>',
            META_TAG.format(page_id=page_id),
            content
        )
        action = '更新'
    else:
        head_match = re.search(r'<head[^>]*>', content, re.IGNORECASE)
        if head_match:
            pos = head_match.end()
            content = content[:pos] + '\n    ' + META_TAG.format(page_id=page_id) + content[pos:]
            action = '注入'
        else:
            print(f'  跳过: {os.path.basename(html_path)} (找不到 <head>)')
            return False

    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'  {action}: {os.path.basename(html_path)} → page #{page_id}')
    return True


def next_available_id(records):
    """获取下一个可用编号（永不重用已删除的 ID）"""
    if not records:
        return 1
    return max(records.values()) + 1


def main():
    # 默认扫描脚本所在目录的上级（即项目根目录，HTML 文件所在地）
    default_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    directory = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else default_dir)

    if not os.path.isdir(directory):
        print(f'错误："{directory}" 不是有效目录')
        sys.exit(1)

    html_files = find_html_files(directory)

    if not html_files:
        print('当前目录没有 .html 文件。')
        return

    records = load_records()

    print(f'扫描到 {len(html_files)} 个 HTML 文件：\n')

    assigned = 0
    for f in html_files:
        fpath = os.path.join(directory, f)

        # 1. 先看 HTML 里有没有已有的 meta 编号
        meta_id = extract_page_id(fpath)

        if meta_id is not None:
            # HTML 已有编号：同步到记录文件
            if f not in records or records[f] != meta_id:
                records[f] = meta_id
                print(f'  #{meta_id}  {f} (已有，同步记录)')
            else:
                print(f'  #{meta_id}  {f} (已有)')
        elif f in records:
            # HTML 丢失了 meta 标签，但记录中有：恢复原编号
            pid = records[f]
            inject_page_id(fpath, pid)
            assigned += 1
        else:
            # 全新文件：分配一个从未用过的编号
            pid = next_available_id(records)
            inject_page_id(fpath, pid)
            records[f] = pid
            assigned += 1

    # 清理记录中已被删除的文件（但编号永久保留，不复用）
    current_files = set(html_files)
    deleted = [f for f in records if f not in current_files]
    if deleted:
        print(f'\n  注意：{len(deleted)} 个文件已删除，其编号永久保留不复用：')
        for f in deleted:
            print(f'    #{records[f]}  {f}')
        # 不删除 records 中的条目，使编号永不重用

    save_records(records)

    print(f'\n完成：本次分配 {assigned} 个，共 {len(html_files)} 个页面。')
    if records:
        max_id = max(records.values())
        print(f'已使用最大编号：{max_id}（下一个新页面将从 #{max_id + 1} 开始）')


if __name__ == '__main__':
    main()
