#!/usr/bin/env python3
"""
清风直播 - 小米电视/Android TV 应用打包与准备工具
支持为小米电视准备适配的电视端直播 APK（小薇直播纯净版 / MyTV 电视版），
输出至 output/tv_app/ 目录，供 U 盘安装、局域网下载或 ADB 一键安装。
"""
import os
import sys
import shutil
import urllib.request
from typing import Dict, Any, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TV_APP_DIR = os.path.join(BASE_DIR, "output", "tv_app")

# 经过实测兼容小米电视(MIUI TV/Android 5.0+)的稳定电视端应用资源
TV_APPS = {
    "xiaowei": {
        "name": "小薇直播纯净版 (推荐, 极契合 live_xiaowei.txt)",
        "filename": "QingFeng_XiaoWei_TV.apk",
        "url": "https://raw.githubusercontent.com/52liulian/tvapp_store/main/app/live/%E5%B0%8F%E8%96%87%E7%9B%B4%E6%92%AD/%E5%B0%8F%E8%96%87%E7%9B%B4%E6%92%AD--v2.7.0.1-v7a-%E5%8E%BB%E5%B9%BF%E5%91%8A%E7%89%88.apk",
        "size_expected_approx": 18 * 1024 * 1024,
    },
    "mytv": {
        "name": "MyTV 电视极速版 (现代原生 Android TV 播放器, 契合 live.m3u)",
        "filename": "QingFeng_MyTV_TV.apk",
        "url": "https://raw.githubusercontent.com/52liulian/tvapp_store/main/app/live/MyTV/mytv-android-tv-1.3.0.172-all-sdk21-%E6%AD%A3%E5%B8%B8%E7%89%88.apk",
        "size_expected_approx": 30 * 1024 * 1024,
    }
}


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def download_file(url: str, dest_path: str, timeout: int = 30) -> bool:
    """下载指定文件，带超时与进度反馈"""
    temp_dest = dest_path + ".tmp"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    req = urllib.request.Request(url, headers=headers)
    
    print(f"[*] 开始下载电视应用包: {os.path.basename(dest_path)}...")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response, open(temp_dest, "wb") as out_file:
            total_size = int(response.headers.get("Content-Length", 0))
            downloaded = 0
            chunk_size = 64 * 1024
            
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                out_file.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    percent = downloaded * 100 // total_size
                    print(f"\r    进度: {percent}% ({downloaded // (1024*1024)}MB / {total_size // (1024*1024)}MB)", end="")
            print()
            
        if os.path.exists(dest_path):
            os.remove(dest_path)
        os.rename(temp_dest, dest_path)
        print(f"[+] 下载成功: {dest_path} (大小: {os.path.getsize(dest_path)} 字节)")
        return True
    except Exception as e:
        print(f"\n[!] 下载失败 ({url}): {e}")
        if os.path.exists(temp_dest):
            try:
                os.remove(temp_dest)
            except OSError:
                pass
        return False


def get_tv_app_status() -> Dict[str, Any]:
    """检查当前电视端应用打包/准备状态"""
    ensure_dir(TV_APP_DIR)
    status = {}
    for key, item in TV_APPS.items():
        apk_path = os.path.join(TV_APP_DIR, item["filename"])
        exists = os.path.exists(apk_path) and os.path.getsize(apk_path) > 1024 * 1024
        size_mb = round(os.path.getsize(apk_path) / (1024 * 1024), 2) if exists else 0
        status[key] = {
            "name": item["name"],
            "filename": item["filename"],
            "path": apk_path,
            "ready": exists,
            "size_mb": size_mb
        }
    
    default_apk = os.path.join(TV_APP_DIR, "tv-app.apk")
    status["default"] = {
        "filename": "tv-app.apk",
        "path": default_apk,
        "ready": os.path.exists(default_apk) and os.path.getsize(default_apk) > 1024 * 1024,
        "size_mb": round(os.path.getsize(default_apk) / (1024 * 1024), 2) if os.path.exists(default_apk) else 0
    }
    return status


def prepare_tv_apps(target: str = "xiaowei") -> bool:
    """拉取并准备小米电视可安装应用"""
    ensure_dir(TV_APP_DIR)
    
    targets = [target] if target in TV_APPS else list(TV_APPS.keys())
    success = False
    
    for t in targets:
        info = TV_APPS[t]
        dest = os.path.join(TV_APP_DIR, info["filename"])
        if os.path.exists(dest) and os.path.getsize(dest) > 1024 * 1024:
            print(f"[+] 电视应用已存在且有效: {info['filename']} ({round(os.path.getsize(dest)/(1024*1024), 2)}MB)")
            success = True
        else:
            if download_file(info["url"], dest):
                success = True
                
    # 建立默认的 tv-app.apk 符号链接或副本
    primary_file = os.path.join(TV_APP_DIR, TV_APPS["xiaowei"]["filename"])
    default_link = os.path.join(TV_APP_DIR, "tv-app.apk")
    if os.path.exists(primary_file):
        try:
            if os.path.exists(default_link) or os.path.islink(default_link):
                os.remove(default_link)
            try:
                os.symlink(TV_APPS["xiaowei"]["filename"], default_link)
            except OSError:
                shutil.copy2(primary_file, default_link)
        except Exception as e:
            print(f"[!] 创建默认 tv-app.apk 快捷方式提示: {e}")
            
    return success


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else "xiaowei"
    print("=" * 65)
    print("       📺 清风直播 - 小米电视应用打包与下载准备工具")
    print("=" * 65)
    ok = prepare_tv_apps(choice)
    status = get_tv_app_status()
    print("\n当前应用准备就绪状态:")
    for k, v in status.items():
        state_icon = "✅ 就绪" if v["ready"] else "❌ 未就绪"
        print(f"  - {v['filename']}: {state_icon} ({v['size_mb']} MB)")
    if ok:
        print("\n[+] 小米电视应用包已准备完成！")
        print(f"    存放路径: {TV_APP_DIR}")
        print("    可通过 U 盘拷贝至小米电视，或在网页控制台一键下载。")
    sys.exit(0 if ok else 1)
