#!/usr/bin/env python3
"""
清风直播 - 直播源云端发布与电视极速加速链生成工具 (publish_to_cloud.py)

功能:
  1. 为 GitHub 托管的直播源生成国内智能电视可秒开的 CDN 加速链接 (jsDelivr / ghproxy)；
  2. 支持 Gitee (码云) 国内直连仓库链接生成；
  3. 提供一键 git push 到指定远端仓库的命令指引与辅助；
  4. 解决国内家庭电视直连 GitHub 容易被墙、DNS 污染导致转圈超时的问题。
"""
import os
import sys
import subprocess
from typing import Dict, Any, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")


def generate_accelerated_urls(repo_url: str, branch: str = "main") -> Dict[str, str]:
    """
    根据输入的 GitHub 或 Gitee 仓库地址，生成电视端可用免翻墙极速直链
    """
    repo_url = repo_url.strip().rstrip("/")
    if repo_url.endswith(".git"):
        repo_url = repo_url[:-4]

    results = {}

    if "gitee.com" in repo_url:
        # Gitee: 国内直接支持 raw 访问
        parts = repo_url.split("gitee.com/")
        if len(parts) == 2:
            path = parts[1]
            results["gitee_raw_m3u"] = f"https://gitee.com/{path}/raw/{branch}/live.m3u"
            results["gitee_raw_txt"] = f"https://gitee.com/{path}/raw/{branch}/live_xiaowei.txt"
            results["platform"] = "Gitee (国内码云, 电视直连极佳 🌟)"
    elif "github.com" in repo_url:
        # GitHub: 转换为国内电视免翻墙 CDN 镜像直链
        parts = repo_url.split("github.com/")
        if len(parts) == 2:
            path = parts[1]  # user/repo
            # 1. jsDelivr 全球加速 (国内直连)
            results["jsdelivr_m3u"] = f"https://fastly.jsdelivr.net/gh/{path}@{branch}/output/live.m3u"
            results["jsdelivr_txt"] = f"https://fastly.jsdelivr.net/gh/{path}@{branch}/output/live_xiaowei.txt"
            # 2. ghproxy 镜像加速 (国内电视极速稳定)
            results["ghproxy_m3u"] = f"https://ghproxy.net/https://raw.githubusercontent.com/{path}/{branch}/output/live.m3u"
            results["ghproxy_txt"] = f"https://ghproxy.net/https://raw.githubusercontent.com/{path}/{branch}/output/live_xiaowei.txt"
            # 3. 原始 GitHub 直链 (易被国内网络污染)
            results["github_raw_m3u"] = f"https://raw.githubusercontent.com/{path}/{branch}/output/live.m3u"
            results["platform"] = "GitHub (已附带国内 CDN 极速镜像加速)"

    return results


def print_cloud_sharing_guide(repo_url: Optional[str] = None):
    print("=" * 72)
    print("        📺 清风直播 - 直播源云端托管与电视秒开加速指引")
    print("=" * 72)

    if repo_url:
        urls = generate_accelerated_urls(repo_url)
        print(f"\n[+] 检测到仓库: {repo_url} ({urls.get('platform', '')})")
        print("\n👉 请直接将下方链接填入电视端【链接】输入框中 (免开电脑、关机照看不卡顿):")
        for k, v in urls.items():
            if "m3u" in k:
                print(f"   📡 M3U 电视直链 [{k}]:\n      👉 {v}\n")
        return

    print("""
【国内智能电视云端托管 2 种最佳实践】:

方案 A：Gitee (码云 - 最推荐 🌟，国内千兆直连，红米电视秒开)
----------------------------------------------------------------------
1. 打开 https://gitee.com 登录并点击右上角【+】->【新建仓库】；
2. 仓库名称填写: live，设为【开源 (公开)】；
3. 将本项目 output/live.m3u 文件上传或新建同名文件粘贴保存；
4. 电视端【链接】直接填入您的 Gitee 直链:
   👉 https://gitee.com/<您的用户名>/live/raw/master/live.m3u
   (免开电脑、国内三网 BGP 秒开，手机电脑随时在网页上改台)

方案 B：GitHub + jsDelivr / ghproxy 国内免翻墙加速 (极客方案)
----------------------------------------------------------------------
由于国内家庭宽带直接连 raw.githubusercontent.com 容易被 DNS 污染超时，
若放在 GitHub 上，电视端请使用自带的 CDN 加速直链：
   👉 https://fastly.jsdelivr.net/gh/<用户名>/<仓库>@main/output/live.m3u
   或
   👉 https://ghproxy.net/https://raw.githubusercontent.com/<用户名>/<仓库>/main/output/live.m3u
""")


if __name__ == "__main__":
    target_repo = sys.argv[1] if len(sys.argv) > 1 else None
    print_cloud_sharing_guide(target_repo)
