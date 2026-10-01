#!/usr/bin/env bash
# ==============================================================================
# 跟风直播 (XiaoWei Live Clean Edition) - 一键运行与管理脚本
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PORT="${PORT:-8088}"
CONFIG_FILE="${CONFIG_FILE:-config.json}"
PID_FILE="$SCRIPT_DIR/.server.pid"
LOG_FILE="$SCRIPT_DIR/output/server.log"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# 获取本机局域网 IP
get_lan_ip() {
    local ip=""
    if command -v hostname >/dev/null 2>&1; then
        ip=$(hostname -I 2>/dev/null | awk '{print $1}')
    fi
    if [ -z "$ip" ] && command -v ip >/dev/null 2>&1; then
        ip=$(ip route get 1.1.1.1 2>/dev/null | awk '{print $7}')
    fi
    if [ -z "$ip" ]; then
        ip="127.0.0.1"
    fi
    echo "$ip"
}

# 检查端口占用情况
get_pid_on_port() {
    local p="$1"
    local pid=""
    if command -v lsof >/dev/null 2>&1; then
        pid=$(lsof -i :"$p" -sTCP:LISTEN -t 2>/dev/null | head -n1)
    fi
    if [ -z "$pid" ] && command -v fuser >/dev/null 2>&1; then
        pid=$(fuser "$p/tcp" 2>/dev/null | awk '{print $1}')
    fi
    if [ -z "$pid" ] && command -v ss >/dev/null 2>&1; then
        pid=$(ss -lptn "sport = :$p" 2>/dev/null | grep -o 'pid=[0-9]*' | cut -d= -f2 | head -n1)
    fi
    echo "$pid"
}

# 打印横幅与访问指引
print_banner() {
    local lan_ip
    lan_ip=$(get_lan_ip)
    echo -e "${CYAN}======================================================================${NC}"
    echo -e "${BOLD}${GREEN}        📺 跟风直播 (XiaoWei Live Clean Edition) ${NC}"
    echo -e "${CYAN}======================================================================${NC}"
    echo -e "  ${BOLD}🖥️  本机控制台:${NC}      ${BLUE}http://localhost:${PORT}${NC}"
    echo -e "  ${BOLD}🌐 局域网控制台:${NC}    ${BLUE}http://${lan_ip}:${PORT}${NC}"
    echo ""
    echo -e "  ${BOLD}📡 小薇直播专用直链 (电视端【网络自定义源】直接填入):${NC}"
    echo -e "     👉 ${YELLOW}http://${lan_ip}:${PORT}/live.txt${NC}"
    echo ""
    echo -e "  ${BOLD}📱 标准通用 M3U 订阅 (TiviMate / Kodi / VLC / 手机播放器):${NC}"
    echo -e "     👉 ${YELLOW}http://${lan_ip}:${PORT}/live.m3u${NC}"
    echo -e "${CYAN}======================================================================${NC}"
}

# 预检与依赖检查
check_environment() {
    if ! command -v python3 >/dev/null 2>&1; then
        echo -e "${RED}[错误] 未检测到 python3，请先安装 Python 3.8 及以上版本。${NC}"
        exit 1
    fi

    # 检查核心依赖 httpx
    if ! python3 -c "import httpx" 2>/dev/null; then
        echo -e "${YELLOW}[*] 检测到缺少 httpx 依赖，正在尝试自动安装...${NC}"
        python3 -m pip install -r requirements.txt || {
            echo -e "${RED}[错误] 自动安装依赖失败，请手动执行: pip3 install -r requirements.txt${NC}"
            exit 1
        }
    fi

    # 确保输出目录就绪
    mkdir -p "$SCRIPT_DIR/output"
    mkdir -p "$SCRIPT_DIR/web/videos"

    # 若尚未生成基础输出文件，自动执行演示样例生成
    if [ ! -f "$SCRIPT_DIR/output/live_xiaowei.txt" ] && [ ! -f "$SCRIPT_DIR/output/demo_xiaowei.txt" ]; then
        echo -e "${YELLOW}[*] 首次运行：生成初始纯净直播源...${NC}"
        python3 demo.py >/dev/null 2>&1 || true
    fi

    # 若缺少仿真视频文件，自动生成
    if [ ! -f "$SCRIPT_DIR/web/videos/cctv1.mp4" ]; then
        echo -e "${YELLOW}[*] 正在准备电视频道广播仿真画面...${NC}"
        python3 scripts/generate_broadcast_videos.py >/dev/null 2>&1 || true
    fi
}

# 尝试在系统默认浏览器中打开页面
open_browser() {
    local url="http://localhost:${PORT}"
    (
        sleep 1
        if [ -n "$DISPLAY" ] || [ -n "$WAYLAND_DISPLAY" ]; then
            if command -v xdg-open >/dev/null 2>&1; then
                xdg-open "$url" >/dev/null 2>&1 &
            elif command -v sensible-browser >/dev/null 2>&1; then
                sensible-browser "$url" >/dev/null 2>&1 &
            elif command -v open >/dev/null 2>&1; then
                open "$url" >/dev/null 2>&1 &
            fi
        fi
    ) &
}

# 启动服务
start_server() {
    local mode="$1" # "foreground" or "daemon"
    check_environment

    local existing_pid
    existing_pid=$(get_pid_on_port "$PORT")

    if [ -n "$existing_pid" ]; then
        echo -e "${YELLOW}[!] 端口 ${PORT} 已有服务在运行 (PID: ${existing_pid})。${NC}"
        print_banner
        echo -e "${GREEN}服务处于就绪状态，已为您打开浏览器。${NC}"
        open_browser
        echo -e "若需重启，请执行: ${BOLD}./start.sh restart${NC}"
        echo -e "若需停止，请执行: ${BOLD}./start.sh stop${NC}"
        return 0
    fi

    print_banner

    if [ "$mode" = "daemon" ]; then
        echo -e "${GREEN}[+] 正在以守护模式后台启动服务...${NC}"
        PYTHONUNBUFFERED=1 nohup python3 -u server.py -p "$PORT" -c "$CONFIG_FILE" > "$LOG_FILE" 2>&1 &
        local new_pid=$!
        disown "$new_pid" 2>/dev/null || true
        echo "$new_pid" > "$PID_FILE"
        sleep 0.8
        if kill -0 "$new_pid" 2>/dev/null; then
            echo -e "${GREEN}[✓] 服务启动成功！进程 PID: ${new_pid}${NC}"
            echo -e "  - 查看实时日志: ${BOLD}tail -f ${LOG_FILE}${NC}"
            echo -e "  - 停止后台服务: ${BOLD}./start.sh stop${NC}"
            echo -e "  - 检查健康状态: ${BOLD}./start.sh status${NC}"
            open_browser
        else
            echo -e "${RED}[错误] 服务启动异常，请查看日志: cat ${LOG_FILE}${NC}"
            rm -f "$PID_FILE"
            exit 1
        fi
    else
        echo -e "${GREEN}[+] 正在以前台交互模式启动服务...${NC}"
        echo -e "提示: 按 ${BOLD}Ctrl+C${NC} 可安全停止服务；如需后台运行请使用 ${BOLD}./start.sh -d${NC}\n"
        open_browser
        python3 server.py -p "$PORT" -c "$CONFIG_FILE"
    fi
}

# 停止服务
stop_server() {
    local stopped=0
    local target_pid=""

    if [ -f "$PID_FILE" ]; then
        target_pid=$(cat "$PID_FILE" 2>/dev/null || true)
    fi

    if [ -z "$target_pid" ]; then
        target_pid=$(get_pid_on_port "$PORT")
    fi

    if [ -n "$target_pid" ]; then
        echo -e "${YELLOW}[*] 正在停止服务进程 (PID: ${target_pid})...${NC}"
        kill -15 "$target_pid" 2>/dev/null || true
        for _ in {1..15}; do
            if ! kill -0 "$target_pid" 2>/dev/null; then
                stopped=1
                break
            fi
            sleep 0.2
        done
        if [ "$stopped" -eq 0 ]; then
            echo -e "${YELLOW}[!] 进程未响应 SIGTERM，尝试强制停止...${NC}"
            kill -9 "$target_pid" 2>/dev/null || true
        fi
        echo -e "${GREEN}[✓] 服务已停止。${NC}"
    else
        echo -e "${YELLOW}[i] 未检测到端口 ${PORT} 正在运行的小薇直播服务。${NC}"
    fi

    rm -f "$PID_FILE"
}

# 状态检查
status_server() {
    local pid
    pid=$(get_pid_on_port "$PORT")
    if [ -n "$pid" ]; then
        echo -e "${GREEN}[● 在线] 小薇直播服务正常运行中 (PID: ${pid}, 端口: ${PORT})${NC}"
        if command -v curl >/dev/null 2>&1; then
            echo -e "${CYAN}--- API 状态响应 ---${NC}"
            curl -s "http://127.0.0.1:${PORT}/api/status" || true
            echo ""
        fi
        print_banner
    else
        echo -e "${RED}[○ 离线] 小薇直播服务当前未运行。${NC}"
        echo -e "可执行 ${BOLD}./start.sh${NC} 或 ${BOLD}./start.sh -d${NC} 启动服务。"
    fi
}

# 重启服务
restart_server() {
    local mode="$1"
    stop_server
    sleep 0.5
    start_server "$mode"
}

# 运行自动化测试
run_tests() {
    echo -e "${CYAN}[*] 正在执行全套自动化单元与集成测试...${NC}"
    python3 -m unittest discover tests
}

# 打印帮助信息
show_help() {
    echo -e "${BOLD}使用说明:${NC} ./start.sh [命令] [选项]"
    echo ""
    echo -e "${BOLD}常用命令:${NC}"
    echo -e "  ${GREEN}./start.sh${NC}          一键运行服务 (前台模式，自动打开浏览器)"
    echo -e "  ${GREEN}./start.sh -d${NC}       后台守护模式运行 (推荐长时间运行使用)"
    echo -e "  ${GREEN}./start.sh stop${NC}     停止运行中的服务"
    echo -e "  ${GREEN}./start.sh restart${NC}  重启服务"
    echo -e "  ${GREEN}./start.sh status${NC}   查看当前服务运行状态与 API 探针"
    echo -e "  ${GREEN}./start.sh test${NC}     执行完整的自动化测试套件"
    echo -e "  ${GREEN}./start.sh help${NC}     显示本帮助信息"
    echo ""
    echo -e "${BOLD}环境变量支持:${NC}"
    echo -e "  PORT=8088 ./start.sh        自定义监听端口 (默认: 8088)"
    echo -e "  CONFIG_FILE=config.json     自定义配置文件路径"
}

# 主参数分发
case "$1" in
    start)
        shift
        if [ "$1" = "-d" ] || [ "$1" = "--daemon" ]; then
            start_server "daemon"
        else
            start_server "foreground"
        fi
        ;;
    -d|--daemon|daemon)
        start_server "daemon"
        ;;
    stop)
        stop_server
        ;;
    restart)
        shift
        if [ "$1" = "-d" ] || [ "$1" = "--daemon" ]; then
            restart_server "daemon"
        else
            restart_server "daemon"
        fi
        ;;
    status)
        status_server
        ;;
    test)
        run_tests
        ;;
    -h|--help|help)
        show_help
        ;;
    *)
        start_server "foreground"
        ;;
esac
