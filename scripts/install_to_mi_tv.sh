#!/usr/bin/env bash
# ==============================================================================
# 清风直播 - 小米电视/Android TV 无线一键安装工具 (install_to_mi_tv.sh)
#
# 功能说明:
#   通过局域网无线 ADB 调试功能，一键将清风电视直播 APK 推送安装到小米电视上，
#   免去插拔 U 盘和繁琐操作。
#
# 使用方法:
#   ./scripts/install_to_mi_tv.sh [小米电视IP]
#   例如: ./scripts/install_to_mi_tv.sh 192.168.1.108
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
TV_APP_DIR="$ROOT_DIR/output/tv_app"
APK_FILE="$TV_APP_DIR/tv-app.apk"

TV_IP="$1"

echo "======================================================================"
echo "        📺 清风直播 - 小米电视局域网无线一键安装助手"
echo "======================================================================"

# 1. 检查 APK 文件是否存在，不存在则先执行下载准备
if [ ! -f "$APK_FILE" ]; then
    echo "[*] 未检测到电视安装包，正在自动准备..."
    python3 "$SCRIPT_DIR/package_tv_app.py" xiaowei
fi

if [ ! -f "$APK_FILE" ]; then
    echo "[-] 错误: 电视应用安装包未能成功生成，请检查网络。"
    exit 1
fi

echo "[+] 待安装的电视端应用: $APK_FILE ($(du -h "$APK_FILE" | cut -f1))"

# 2. 检查 adb 命令行工具
if ! command -v adb &> /dev/null; then
    echo ""
    echo "[!] 提示: 本机尚未安装 adb (Android 调试桥工具)。"
    echo "    若需在 Linux 上无线直推安装，可执行: sudo apt-get install -y adb"
    echo ""
    echo "======================================================================"
    echo "💡 您也可以使用最简单的【U 盘安装法】或【网页下载】直接安装:"
    echo "  1. 将安装包拷贝至 U 盘:"
    echo "     cp $APK_FILE /media/您的U盘路径/"
    echo "  2. 小米电视开启【安装未知来源应用】:"
    echo "     进入【设置】 -> 【账号与安全】 -> 【安装未知来源的应用】 -> 开启为【允许】"
    echo "  3. 将 U 盘插入小米电视 USB 接口，电视弹出提示后点击安装，或在【高清播放器】中打开 APK 安装即可！"
    echo "======================================================================"
    exit 0
fi

# 3. 若未传 IP 参数，提示输入
if [ -z "$TV_IP" ]; then
    echo ""
    echo "【小米电视开启 ADB 调试步骤】:"
    echo "  1. 遥控器进入电视【设置】 -> 【关于】 -> 连续按 5 次【产品型号】或【系统版本】，激活开发者选项。"
    echo "  2. 返回上一层进入【账号与安全】（或开发者选项），将【ADB 调试】设为【开启】。"
    echo "  3. 查看电视【网络设置】中的电视局域网 IP 地址。"
    echo ""
    read -r -p "请输入您的小米电视 IP 地址 (例如 192.168.1.100): " TV_IP
fi

if [ -z "$TV_IP" ]; then
    echo "[-] 未输入电视 IP，操作已取消。"
    exit 1
fi

echo ""
echo "[*] 正在尝试无线连接小米电视 ($TV_IP:5555)..."
adb disconnect "$TV_IP:5555" 2>/dev/null || true
CONNECT_RES=$(adb connect "$TV_IP:5555" 2>&1)
echo "    -> $CONNECT_RES"

if [[ "$CONNECT_RES" =~ "connected" ]]; then
    echo "[+] 成功建立无线调试连接！正在向小米电视推送并安装应用..."
    adb -s "$TV_IP:5555" install -r "$APK_FILE"
    echo ""
    echo "======================================================================"
    echo "🎉 恭喜！应用已成功安装到您的小米电视！"
    echo "👉 拿起遥控器在小米电视【我的应用】中打开即可畅享极速电视直播！"
    echo "======================================================================"
else
    echo "[-] 无法连接到小米电视 ($TV_IP:5555)，请检查:"
    echo "    1. 电视与电脑是否处于同一个 Wi-Fi / 局域网路由器下；"
    echo "    2. 电视端【ADB 调试】是否已设为开启；"
    echo "    3. 电视屏幕是否弹出了【允许 USB 调试吗？】的遥控器授权确认框（若有请勾选始终允许并确定）。"
fi
