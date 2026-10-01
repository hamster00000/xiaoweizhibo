#!/usr/bin/env python3
"""
小薇直播纯净版 - 本地 Web 守护与交付服务 (server.py)
提供前端可视化控制台、小薇专属订阅直链、标准 M3U 直链及自动化调度 API。
"""
import argparse
import http.server
import json
import os
import socketserver
import sys
import threading
import time
from typing import Optional
from urllib.parse import urlparse

from live_crawler.fetcher import SourceFetcher
from live_crawler.normalizer import ChannelNormalizer
from live_crawler.exporter import StreamExporter
from live_crawler.manager import LiveSourceManager

PORT = 8088
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, "web")


class LiveDemoHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP 路由分发处理器 (契合技术设计 4.5 与 API Spec 规范)"""
    manager: Optional[LiveSourceManager] = None
    _refresh_lock = threading.Lock()
    _is_refreshing = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)

        # 1. 小薇直播专属订阅源直链
        if parsed.path == "/live.txt":
            self._handle_live_txt()
            return

        # 2. 通用标准 M3U 直播源直链
        if parsed.path == "/live.m3u":
            self._handle_live_m3u()
            return

        # 3. 获取服务健康状态与统计指标
        if parsed.path == "/api/status":
            self._handle_status()
            return

        # 4. HLS 媒体流跨域代理接口 (供网页端播放器跨域播放直播流)
        if parsed.path == "/api/stream_proxy":
            self._handle_stream_proxy(parsed)
            return

        # 5. 默认首页路由
        if parsed.path in ["", "/"]:
            self.path = "/index.html"

        return super().do_GET()

    def do_HEAD(self):
        parsed = urlparse(self.path)
        if parsed.path in ["/live.txt", "/live.m3u", "/api/status", "/api/stream_proxy"]:
            self.do_GET()
            return
        return super().do_HEAD()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)

        # 1. 触发后台异步刷新与测速管线
        if parsed.path == "/api/refresh":
            self._handle_refresh()
            return

        # 2. 交互式控制台源清洗处理接口
        if parsed.path == "/api/process":
            self._handle_process()
            return

        self.send_error(404, "Not Found")

    def _handle_live_txt(self):
        txt_path = self._get_output_path("xiaowei_txt", "live_xiaowei.txt")
        if not os.path.exists(txt_path):
            # 若主文件尚未生成，尝试降级读取 demo 样例
            fallback = os.path.join(BASE_DIR, "output", "demo_xiaowei.txt")
            if os.path.exists(fallback):
                txt_path = fallback
            else:
                self.send_response(404)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write("直播源尚未生成，请稍后刷新或在控制台触发更新任务。".encode("utf-8"))
                return

        try:
            with open(txt_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, f"Error reading live.txt: {e}")

    def _handle_live_m3u(self):
        m3u_path = self._get_output_path("standard_m3u", "live.m3u")
        if not os.path.exists(m3u_path):
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("M3U 播放列表尚未生成，请稍后刷新。".encode("utf-8"))
            return

        try:
            with open(m3u_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "application/x-mpegurl; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, f"Error reading live.m3u: {e}")

    def _handle_status(self):
        if self.manager:
            status_data = self.manager.get_status()
        else:
            status_data = {
                "status": "ok",
                "channels_count": 0,
                "total_lines": 0,
                "last_updated": "未初始化",
                "avg_latency_ms": 0.0
            }

        status_data["is_refreshing"] = LiveDemoHandler._is_refreshing

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(status_data, ensure_ascii=False).encode("utf-8"))

    def _handle_refresh(self):
        if not self.manager:
            self._send_json(500, {"code": 500, "error": "Manager 未初始化"})
            return

        with LiveDemoHandler._refresh_lock:
            if LiveDemoHandler._is_refreshing:
                self._send_json(200, {
                    "code": 0,
                    "status": "busy",
                    "message": "已有抓取测速任务正在执行中，请稍候..."
                })
                return
            LiveDemoHandler._is_refreshing = True

        def _worker():
            try:
                print("\n[*] 接收到 API 刷新请求，开始在后台执行更新管线...")
                self.manager.run()
                print("[+] 后台更新管线执行完毕！\n")
            except Exception as ex:
                print(f"[!] 后台更新失败: {ex}", file=sys.stderr)
            finally:
                with LiveDemoHandler._refresh_lock:
                    LiveDemoHandler._is_refreshing = False

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

        self._send_json(200, {
            "code": 0,
            "status": "started",
            "message": "已在后台启动新一轮直播源抓取与测速管线"
        })

    def _handle_process(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        try:
            data = json.loads(body) if body else {}
            raw_text = data.get("raw_text", "")
            max_lines = int(data.get("max_lines", 3))

            normalizer = ChannelNormalizer()
            fetcher = SourceFetcher(normalizer=normalizer)
            exporter = StreamExporter(max_lines_per_channel=max_lines)

            items = fetcher.parse(raw_text)
            for idx, it in enumerate(items):
                it.is_valid = True
                it.latency_ms = round(15.0 + (idx * 7.5) % 80, 1)

            grouped = exporter.deduplicate_and_rank(items)
            xiaowei_txt = exporter.export_xiaowei_txt(grouped)
            m3u_text = exporter.export_standard_m3u(grouped)

            resp_payload = {
                "code": 0,
                "total_raw": len(items),
                "xiaowei_txt": xiaowei_txt,
                "m3u_text": m3u_text,
                "channels": [
                    {
                        "raw_name": it.raw_name,
                        "name": it.name,
                        "group": it.group,
                        "url": it.url,
                        "latency_ms": it.latency_ms
                    }
                    for it in items
                ]
            }
            self._send_json(200, resp_payload)
        except Exception as e:
            self._send_json(500, {"code": 500, "error": str(e)})

    def _send_json(self, status_code: int, data: dict):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _handle_stream_proxy(self, parsed):
        import urllib.parse
        import httpx
        qs = urllib.parse.parse_qs(parsed.query)
        target_url = qs.get("url", [""])[0]
        if not target_url or not target_url.startswith(("http://", "https://")):
            self.send_error(400, "Invalid or missing url parameter")
            return

        headers = {
            "User-Agent": "okhttp/3.15 XiaoWeiLive/5.0.0",
            "Accept": "*/*"
        }
        if "Range" in self.headers:
            headers["Range"] = self.headers["Range"]

        try:
            with httpx.Client(timeout=20.0, verify=False, follow_redirects=True, trust_env=False) as client:
                is_m3u8 = ".m3u8" in target_url.lower()

                if is_m3u8:
                    resp = client.get(target_url, headers=headers)
                    if resp.status_code >= 400:
                        self.send_error(resp.status_code, f"Upstream error {resp.status_code}")
                        return

                    content_type = resp.headers.get("Content-Type", "")
                    content_bytes = resp.content

                    # 若是 M3U8 播放列表，重写切片 URL 为经由本地代理的路径
                    if "mpegurl" in content_type or is_m3u8 or b"#EXTM3U" in content_bytes[:100]:
                        try:
                            text = content_bytes.decode("utf-8", errors="replace")
                            base_url = str(resp.url)
                            lines = []
                            for line in text.splitlines():
                                stripped = line.strip()
                                if not stripped or stripped.startswith("#"):
                                    lines.append(line)
                                else:
                                    abs_url = urllib.parse.urljoin(base_url, stripped)
                                    proxied = f"/api/stream_proxy?url={urllib.parse.quote(abs_url)}"
                                    lines.append(proxied)
                            rewritten = "\n".join(lines).encode("utf-8")
                            self.send_response(200)
                            self.send_header("Content-Type", "application/vnd.apple.mpegurl; charset=utf-8")
                            self.send_header("Access-Control-Allow-Origin", "*")
                            self.send_header("Content-Length", str(len(rewritten)))
                            self.end_headers()
                            self.wfile.write(rewritten)
                            return
                        except Exception:
                            pass

                    self.send_response(resp.status_code)
                    self.send_header("Content-Type", content_type or "application/octet-stream")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.send_header("Content-Length", str(len(content_bytes)))
                    self.end_headers()
                    self.wfile.write(content_bytes)
                else:
                    # 流式传输 TS 切片/媒体流，边下载边发送，秒级传输首包
                    with client.stream("GET", target_url, headers=headers) as resp:
                        if resp.status_code >= 400:
                            self.send_error(resp.status_code, f"Upstream error {resp.status_code}")
                            return

                        self.send_response(resp.status_code)
                        content_type = resp.headers.get("Content-Type", "video/mp2t")
                        self.send_header("Content-Type", content_type)
                        self.send_header("Access-Control-Allow-Origin", "*")
                        if "Content-Length" in resp.headers:
                            self.send_header("Content-Length", resp.headers["Content-Length"])
                        if "Content-Range" in resp.headers:
                            self.send_header("Content-Range", resp.headers["Content-Range"])
                        if "Accept-Ranges" in resp.headers:
                            self.send_header("Accept-Ranges", resp.headers["Accept-Ranges"])
                        self.end_headers()

                        try:
                            for chunk in resp.iter_bytes(chunk_size=65536):
                                self.wfile.write(chunk)
                            self.wfile.flush()
                        except (BrokenPipeError, ConnectionResetError):
                            pass
        except Exception as e:
            try:
                self.send_error(502, f"Proxy error: {e}")
            except Exception:
                pass

    def _get_output_path(self, key: str, default_name: str) -> str:
        if self.manager and "output" in self.manager.config:
            out_cfg = self.manager.config["output"]
            out_dir = out_cfg.get("dir", "output")
            filename = out_cfg.get(key, default_name)
            return os.path.join(out_dir, filename)
        return os.path.join(BASE_DIR, "output", default_name)


def start_scheduler(manager: LiveSourceManager, interval_hours: float):
    """后台定时保活守护线程 (契合技术设计 5.1 规范)"""
    if interval_hours <= 0:
        return

    def _loop():
        interval_secs = interval_hours * 3600
        while True:
            time.sleep(interval_secs)
            try:
                print(f"\n[*] [定时守护] 触发轮询任务 (每 {interval_hours} 小时)...")
                manager.run()
                print("[+] [定时守护] 轮询任务完成。\n")
            except Exception as err:
                print(f"[!] [定时守护] 轮询执行出错: {err}", file=sys.stderr)

    t = threading.Thread(target=_loop, daemon=True)
    t.start()
    print(f"[*] 定时保活调度器已启动: 每隔 {interval_hours} 小时自动执行一轮探测与优选重写")


def run_server(port: int = PORT, config_path: str = "config.json", auto_refresh_hours: Optional[float] = None):
    # 初始化管理调度器
    try:
        cfg_file = config_path if os.path.isabs(config_path) else os.path.join(BASE_DIR, config_path)
        manager = LiveSourceManager(config_path=cfg_file)
    except Exception as e:
        print(f"[!] 加载配置失败: {e}，将以轻量降级模式运行", file=sys.stderr)
        manager = None

    LiveDemoHandler.manager = manager

    # 若配置了自动轮询保活守护
    if manager:
        refresh_hours = auto_refresh_hours if auto_refresh_hours is not None else float(manager.config.get("auto_refresh_hours", 0))
        if refresh_hours > 0:
            start_scheduler(manager, refresh_hours)

    socketserver.TCPServer.allow_reuse_address = True
    server_cls = getattr(http.server, "ThreadingHTTPServer", socketserver.TCPServer)
    server_cls.allow_reuse_address = True
    with server_cls(("", port), LiveDemoHandler) as httpd:
        print(f"[*] 小薇直播纯净版交付服务已启动:")
        print(f"    👉 Web 监控控制台: http://localhost:{port}")
        print(f"    👉 小薇电视订阅源: http://localhost:{port}/live.txt")
        print(f"    👉 通用标准 M3U 源: http://localhost:{port}/live.m3u")
        print(f"    👉 健康状态接口: http://localhost:{port}/api/status")
        print("按 Ctrl+C 可停止服务。")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[!] 正在关闭服务...")
            httpd.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="小薇直播纯净版 Web 演示与分发服务")
    parser.add_argument("-p", "--port", type=int, default=PORT, help=f"监听端口 (默认: {PORT})")
    parser.add_argument("-c", "--config", default="config.json", help="配置文件路径 (默认: config.json)")
    parser.add_argument("--auto-refresh", type=float, default=None, help="后台自动轮询探测周期（小时，默认依据配置文件）")
    args = parser.parse_args()
    run_server(port=args.port, config_path=args.config, auto_refresh_hours=args.auto_refresh)
