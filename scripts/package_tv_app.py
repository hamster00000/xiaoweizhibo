#!/usr/bin/env python3
"""
清风直播 - 小米电视/Android TV 应用打包与准备工具
支持为小米电视准备适配的电视端直播 APK:
1. 清风直播专属 TV 版 (推荐! 独立包名 com.qingfeng.live.tv, 绝不覆盖小薇直播, 可双应用共存)
2. 小薇直播纯净版 (原始包名 com.live.zd, 供需要单应用替换的用户)
3. MyTV 现代版 (独立包名 com.github.mytv.android)

输出至 output/tv_app/ 目录，供 U 盘安装、局域网下载或 ADB 一键安装。
"""
import os
import sys
import shutil
import urllib.request
from typing import Dict, Any, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
TV_APP_DIR = os.path.join(BASE_DIR, "output", "tv_app")

# 经过实测兼容小米电视(MIUI TV/Android 5.0+)的电视端应用资源配置
TV_APPS = {
    "qingfeng": {
        "name": "清风直播专属 TV 版 (推荐 🌟, 独立包名: com.qingfeng.live.tv, 绝不覆盖小薇直播)",
        "filename": "QingFeng_Live_TV.apk",
        "package": "com.qingfeng.live.tv",
        "app_label": "清风直播",
        "base_src": "xiaowei",
    },
    "xiaowei": {
        "name": "小薇直播纯净版 (原版包名: com.live.zd, 若已安装同名版会产生覆盖)",
        "filename": "QingFeng_XiaoWei_TV.apk",
        "package": "com.live.zd",
        "app_label": "小薇直播",
        "url": "https://raw.githubusercontent.com/52liulian/tvapp_store/main/app/live/%E5%B0%8F%E8%96%87%E7%9B%B4%E6%92%AD/%E5%B0%8F%E8%96%87%E7%9B%B4%E6%92%AD--v2.7.0.1-v7a-%E5%8E%BB%E5%B9%BF%E5%91%8A%E7%89%88.apk",
        "size_expected_approx": 18 * 1024 * 1024,
    },
    "mytv": {
        "name": "MyTV 电视极速版 (现代原生 Android TV 播放器, 独立包名: com.github.mytv.android)",
        "filename": "QingFeng_MyTV_TV.apk",
        "package": "com.github.mytv.android",
        "app_label": "MyTV",
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
            "package": item.get("package", ""),
            "app_label": item.get("app_label", ""),
            "path": apk_path,
            "ready": exists,
            "size_mb": size_mb,
            "is_isolated": item.get("package") != "com.live.zd"
        }

    default_apk = os.path.join(TV_APP_DIR, "tv-app.apk")
    status["default"] = {
        "filename": "tv-app.apk",
        "path": default_apk,
        "ready": os.path.exists(default_apk) and os.path.getsize(default_apk) > 1024 * 1024,
        "size_mb": round(os.path.getsize(default_apk) / (1024 * 1024), 2) if os.path.exists(default_apk) else 0,
        "target_package": "com.qingfeng.live.tv",
        "notice": "独立包名，绝不覆盖小薇直播"
    }
    return status


def prepare_tv_apps(target: str = "qingfeng") -> bool:
    """拉取并准备小米电视可安装应用"""
    ensure_dir(TV_APP_DIR)
    from scripts.repackage_tv_app import repackage_to_qingfeng_tv

    # 1. 确保基础应用包已就绪
    base_file = os.path.join(TV_APP_DIR, TV_APPS["xiaowei"]["filename"])
    if not os.path.exists(base_file) or os.path.getsize(base_file) < 1024 * 1024:
        download_file(TV_APPS["xiaowei"]["url"], base_file)

    success = False

    # 2. 生成清风直播专属独立包 (com.qingfeng.live.tv)
    qingfeng_dest = os.path.join(TV_APP_DIR, TV_APPS["qingfeng"]["filename"])
    if os.path.exists(base_file) and os.path.getsize(base_file) > 1024 * 1024:
        if not os.path.exists(qingfeng_dest) or os.path.getsize(qingfeng_dest) < 1024 * 1024:
            ok = repackage_to_qingfeng_tv(
                base_file,
                qingfeng_dest,
                new_package=TV_APPS["qingfeng"]["package"],
                new_app_name=TV_APPS["qingfeng"]["app_label"]
            )
            if ok:
                success = True
        else:
            print(f"[+] 清风直播专属 APK 已就绪: {qingfeng_dest}")
            success = True

    # 3. 若用户明确要求拉取其他应用 (如 mytv)
    if target == "mytv":
        mytv_dest = os.path.join(TV_APP_DIR, TV_APPS["mytv"]["filename"])
        if not os.path.exists(mytv_dest) or os.path.getsize(mytv_dest) < 1024 * 1024:
            download_file(TV_APPS["mytv"]["url"], mytv_dest)

    # 4. 建立默认 tv-app.apk 指向独立包名的 QingFeng_Live_TV.apk
    default_link = os.path.join(TV_APP_DIR, "tv-app.apk")
    if os.path.exists(qingfeng_dest):
        try:
            if os.path.exists(default_link) or os.path.islink(default_link):
                os.remove(default_link)
            try:
                os.symlink(TV_APPS["qingfeng"]["filename"], default_link)
            except OSError:
                shutil.copy2(qingfeng_dest, default_link)
            print(f"[+] 默认电视安装包指向: QingFeng_Live_TV.apk (包名: com.qingfeng.live.tv)")
        except Exception as e:
            print(f"[!] 创建默认 tv-app.apk 快捷方式提示: {e}")

    return success


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else "qingfeng"
    print("=" * 68)
    print("       📺 清风直播 - 小米电视应用打包与独立共存构建工具")
    print("=" * 68)
    ok = prepare_tv_apps(choice)
    status = get_tv_app_status()
    print("\n当前应用就绪状态与包名隔离情况:")
    for k, v in status.items():
        state_icon = "✅ 就绪" if v["ready"] else "❌ 未就绪"
        pkg_info = f" [包名: {v['package']}]" if "package" in v and v['package'] else ""
        print(f"  - {v['filename']}: {state_icon} ({v['size_mb']} MB){pkg_info}")
    if ok:
        print("\n[+] 清风直播专属电视端应用已生成就绪！")
        print(f"    存放路径: {TV_APP_DIR}")
        print("    重要提示: 本应用包名为 com.qingfeng.live.tv，绝不覆盖已有的小薇直播，支持双应用并存！")
    sys.exit(0 if ok else 1)
