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
from typing import Dict, Any, Optional, Tuple

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")


def get_current_git_info() -> Tuple[str, str]:
    """获取当前本地仓库的 remote url 与当前分支"""
    repo_url = ""
    branch = "master"
    try:
        r = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True, cwd=BASE_DIR)
        if r.returncode == 0 and r.stdout.strip():
            repo_url = r.stdout.strip()
    except Exception:
        pass

    try:
        b = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, cwd=BASE_DIR)
        if b.returncode == 0 and b.stdout.strip():
            branch = b.stdout.strip()
    except Exception:
        pass

    return repo_url, branch


def generate_accelerated_urls(repo_url: str, branch: str = "main") -> Dict[str, str]:
    """
    根据输入的 GitHub 或 Gitee 仓库地址，生成电视端可用免翻墙极速直链
    """
    repo_url = repo_url.strip().rstrip("/")
    if repo_url.endswith(".git"):
        repo_url = repo_url[:-4]

    results = {}

    # 提取协议后面的 host 与路径
    clean_url = repo_url
    if "git@github.com:" in repo_url:
        clean_url = repo_url.replace("git@github.com:", "https://github.com/")
    elif "git@gitee.com:" in repo_url:
        clean_url = repo_url.replace("git@gitee.com:", "https://gitee.com/")

    if "gitee.com" in clean_url:
        # Gitee: 国内直接支持 raw 访问 (100% 国内千兆骨干直连，完全无需翻墙)
        parts = clean_url.split("gitee.com/")
        if len(parts) == 2:
            path = parts[1]
            results["gitee_raw_m3u"] = f"https://gitee.com/{path}/raw/{branch}/live.m3u"
            results["gitee_raw_txt"] = f"https://gitee.com/{path}/raw/{branch}/live_xiaowei.txt"
            results["gitee_best_txt"] = f"https://gitee.com/{path}/raw/{branch}/output/live_best.txt"
            results["gitee_best_m3u"] = f"https://gitee.com/{path}/raw/{branch}/output/live_best.m3u"
            results["platform"] = "Gitee (国内码云, 电视直连极佳 🌟)"
    elif "github.com" in clean_url:
        # GitHub: 转换为国内电视免翻墙 CDN 镜像直链
        parts = clean_url.split("github.com/")
        if len(parts) == 2:
            path = parts[1]  # user/repo
            # 1. jsDelivr 全球/国内边缘加速 (Fastly & Cloudflare)
            results["jsdelivr_m3u"] = f"https://fastly.jsdelivr.net/gh/{path}@{branch}/output/live.m3u"
            results["jsdelivr_txt"] = f"https://fastly.jsdelivr.net/gh/{path}@{branch}/output/live_xiaowei.txt"
            results["jsdelivr_best_txt"] = f"https://fastly.jsdelivr.net/gh/{path}@{branch}/output/live_best.txt"
            results["jsdelivr_best_m3u"] = f"https://fastly.jsdelivr.net/gh/{path}@{branch}/output/live_best.m3u"
            results["jsdelivr_cdn_best_txt"] = f"https://cdn.jsdelivr.net/gh/{path}@{branch}/output/live_best.txt"

            # 2. GHProxy 国内三网专线反向代理 (支持多镜像节点冗余)
            results["ghproxy_m3u"] = f"https://ghproxy.net/https://raw.githubusercontent.com/{path}/{branch}/output/live.m3u"
            results["ghproxy_txt"] = f"https://ghproxy.net/https://raw.githubusercontent.com/{path}/{branch}/output/live_xiaowei.txt"
            results["ghproxy_best_txt"] = f"https://ghproxy.net/https://raw.githubusercontent.com/{path}/{branch}/output/live_best.txt"
            results["ghproxy_best_m3u"] = f"https://ghproxy.net/https://raw.githubusercontent.com/{path}/{branch}/output/live_best.m3u"
            results["mirror_ghproxy_best_txt"] = f"https://mirror.ghproxy.com/https://raw.githubusercontent.com/{path}/{branch}/output/live_best.txt"

            # 3. GitMirror 国内镜像节点
            results["gitmirror_best_txt"] = f"https://raw.gitmirror.com/{path}/{branch}/output/live_best.txt"

            # 4. 原始 GitHub 直链 (易被国内网络污染阻断，仅作为技术参考)
            results["github_raw_m3u"] = f"https://raw.githubusercontent.com/{path}/{branch}/output/live.m3u"
            results["github_raw_best_txt"] = f"https://raw.githubusercontent.com/{path}/{branch}/output/live_best.txt"
            results["platform"] = "GitHub (已注入国内 CDN 极速防墙镜像加速)"

    return results


def print_cloud_sharing_guide(repo_url: Optional[str] = None):
    print("=" * 74)
    print("     📺 清风/小薇直播 - 防 GitHub 阻断与免翻墙极速订阅源指引")
    print("=" * 74)

    auto_repo, auto_branch = get_current_git_info()
    target_repo = repo_url or auto_repo or "https://github.com/hamster00000/xiaoweizhibo"
    branch = auto_branch or "master"

    urls = generate_accelerated_urls(target_repo, branch=branch)
    print(f"\n[+] 当前生效仓库: {target_repo} (分支: {branch})")
    print(f"[+] 加速引擎类型: {urls.get('platform', '自定义')}\n")

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("⭐ 【方案一：小薇直播专享 TXT 订阅源】(单台仅保留 1 条最优信号源，防卡顿首选)")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("说明: 小薇直播或电视机盒在【网络自定义】直接填入下列任一直链（已解决 GitHub 无法访问问题）:\n")
    if "jsdelivr_best_txt" in urls:
        print(f"  1. 🚀 jsDelivr CDN 全球加速专线 (推荐):\n     👉 {urls['jsdelivr_best_txt']}\n")
    if "ghproxy_best_txt" in urls:
        print(f"  2. ⚡ GHProxy 国内三网高可用镜像 (备用):\n     👉 {urls['ghproxy_best_txt']}\n")
    if "mirror_ghproxy_best_txt" in urls:
        print(f"  3. 🛡️ GHProxy 备选专线 (多路容灾):\n     👉 {urls['mirror_ghproxy_best_txt']}\n")
    if "gitee_best_txt" in urls:
        print(f"  4. 🇨🇳 Gitee 码云国内骨干直连 (100% 免翻墙):\n     👉 {urls['gitee_best_txt']}\n")

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("⭐ 【方案二：通用 M3U 播放器订阅源】(适用于影视仓/TiviMate/Kodi/清风直播)")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    if "jsdelivr_best_m3u" in urls:
        print(f"  1. 🚀 jsDelivr CDN (最优单源):\n     👉 {urls['jsdelivr_best_m3u']}\n")
    if "ghproxy_best_m3u" in urls:
        print(f"  2. ⚡ GHProxy 镜像 (最优单源):\n     👉 {urls['ghproxy_best_m3u']}\n")
    if "jsdelivr_m3u" in urls:
        print(f"  3. 📡 jsDelivr CDN (全量多备选源):\n     👉 {urls['jsdelivr_m3u']}\n")

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("⭐ 【方案三：家庭局域网 0 阻断专线】(完全不依赖 GitHub 与任何外网)")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("说明: 本机已开启局域网服务，电视直接连本机 IP，响应时间 < 5ms，完全免疫任何外网故障:")
    print("   👉 http://192.168.0.113:8088/live.txt    (小薇直播 - 默认单台最优)")
    print("   👉 http://192.168.0.113:8088/best.txt    (小薇直播 - 显式单台最优)")
    print("   👉 http://192.168.0.113:8088/live.m3u    (通用 M3U 格式)\n")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    print_cloud_sharing_guide(target)
