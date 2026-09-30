#!/usr/bin/env python3
"""
小薇直播纯净版 - 本地 Web 演示服务
提供前端静态页面托管及直播源清洗处理 API。
"""
import argparse
import http.server
import json
import os
import socketserver
import sys
from urllib.parse import urlparse
from live_crawler.fetcher import SourceFetcher
from live_crawler.normalizer import ChannelNormalizer
from live_crawler.exporter import StreamExporter

PORT = 8088
WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")


class LiveDemoHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "app": "XiaoWeiLive Web Demo"}).encode("utf-8"))
            return

        # 默认路由到 index.html
        if parsed.path in ["", "/"]:
            self.path = "/index.html"

        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/process":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                data = json.loads(body) if body else {}
                raw_text = data.get("raw_text", "")

                normalizer = ChannelNormalizer()
                fetcher = SourceFetcher(normalizer=normalizer)
                exporter = StreamExporter(max_lines_per_channel=data.get("max_lines", 3))

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
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(resp_payload, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"code": 500, "error": str(e)}).encode("utf-8"))
            return

        self.send_error(404, "Not Found")


def run_server(port: int = PORT):
    handler = LiveDemoHandler
    # 允许端口快速重用
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"[*] 小薇直播纯净版 Web 演示服务已启动:")
        print(f"    👉 http://localhost:{port}")
        print(f"    👉 页面路径: {os.path.join(WEB_DIR, 'index.html')}")
        print("按 Ctrl+C 可停止服务。")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[!] 正在关闭服务...")
            httpd.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="小薇直播纯净版 Web 演示服务")
    parser.add_argument("-p", "--port", type=int, default=PORT, help=f"监听端口 (默认: {PORT})")
    args = parser.parse_args()
    run_server(args.port)
