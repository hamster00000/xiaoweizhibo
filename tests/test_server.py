import json
import os
import socketserver
import tempfile
import threading
import time
import unittest
import urllib.request
from server import LiveDemoHandler
from live_crawler.manager import LiveSourceManager

TEST_PORT = 18099


class TestLiveDemoServer(unittest.TestCase):
    httpd = None
    server_thread = None
    temp_dir = None

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        sample_txt = os.path.join(cls.temp_dir, "test_xw.txt")
        with open(sample_txt, "w", encoding="utf-8") as f:
            f.write("央视频道,#genre#\nCCTV-1,http://live.test/cctv1.m3u8\n")

        sample_m3u = os.path.join(cls.temp_dir, "test.m3u")
        with open(sample_m3u, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n#EXTINF:-1 group-title=\"央视频道\",CCTV-1\nhttp://live.test/cctv1.m3u8\n")

        test_cfg = os.path.join(cls.temp_dir, "test_config.json")
        cfg_data = {
            "sources": [],
            "checker": {"timeout": 1.0, "concurrency": 2},
            "output": {
                "dir": cls.temp_dir,
                "xiaowei_txt": "test_xw.txt",
                "standard_m3u": "test.m3u"
            }
        }
        with open(test_cfg, "w", encoding="utf-8") as f:
            json.dump(cfg_data, f)

        mgr = LiveSourceManager(config_path=test_cfg)
        LiveDemoHandler.manager = mgr

        socketserver.TCPServer.allow_reuse_address = True
        cls.httpd = socketserver.TCPServer(("", TEST_PORT), LiveDemoHandler)
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.3)

    @classmethod
    def tearDownClass(cls):
        if cls.httpd:
            cls.httpd.shutdown()
            cls.httpd.server_close()

    def test_status_api(self):
        url = f"http://127.0.0.1:{TEST_PORT}/api/status"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertIn("status", data)
            self.assertIn("channels_count", data)
            self.assertIn("total_lines", data)
            self.assertIn("last_updated", data)

    def test_serve_index(self):
        url = f"http://127.0.0.1:{TEST_PORT}/"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            content = resp.read().decode("utf-8")
            self.assertIn("跟风直播", content)

    def test_live_txt_endpoint(self):
        url = f"http://127.0.0.1:{TEST_PORT}/live.txt"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("text/plain", resp.headers.get("Content-Type"))
            content = resp.read().decode("utf-8")
            self.assertIn("央视频道,#genre#", content)
            self.assertIn("CCTV-1,http://live.test/cctv1.m3u8", content)

    def test_live_m3u_endpoint(self):
        url = f"http://127.0.0.1:{TEST_PORT}/live.m3u"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            content = resp.read().decode("utf-8")
            self.assertTrue(content.startswith("#EXTM3U"))
            self.assertIn("CCTV-1", content)

    def test_channels_api(self):
        url = f"http://127.0.0.1:{TEST_PORT}/api/channels"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data["code"], 0)
            self.assertGreaterEqual(data["total"], 1)
            self.assertTrue(any(c["name"] == "CCTV-1" for c in data["channels"]))

    def test_refresh_api(self):
        url = f"http://127.0.0.1:{TEST_PORT}/api/refresh"
        req = urllib.request.Request(url, data=b"{}", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data["code"], 0)
            self.assertIn(data["status"], ["started", "busy"])

    def test_process_api(self):
        url = f"http://127.0.0.1:{TEST_PORT}/api/process"
        sample_payload = {
            "raw_text": """央视频道,#genre#
CCTV-1 综合,http://test.live/cctv1.m3u8
电视购物,#genre#
家庭购物特惠,http://test.live/ad.m3u8
"""
        }
        data_bytes = json.dumps(sample_payload).encode("utf-8")
        req = urllib.request.Request(url, data=data_bytes, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data["code"], 0)
            self.assertEqual(data["total_raw"], 1)  # 广告已被过滤
            self.assertIn("央视频道,#genre#", data["xiaowei_txt"])
            self.assertIn("CCTV-1,http://test.live/cctv1.m3u8", data["xiaowei_txt"])
            self.assertIn("#EXTM3U", data["m3u_text"])


    def test_options_cors(self):
        url = f"http://127.0.0.1:{TEST_PORT}/api/stream_proxy"
        req = urllib.request.Request(url, method="OPTIONS")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 204)
            self.assertEqual(resp.headers.get("Access-Control-Allow-Origin"), "*")

    def test_stream_proxy_missing_param(self):
        url = f"http://127.0.0.1:{TEST_PORT}/api/stream_proxy"
        try:
            with urllib.request.urlopen(url) as resp:
                pass
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 400)


    def test_stream_proxy_rewrite_and_ts_streaming(self):
        import http.server
        import urllib.parse

        # 启动一个本地临时 mock upstream 服务
        class MockUpstreamHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/mock/live.m3u8":
                    content = b"#EXTM3U\n#EXT-X-VERSION:3\n#EXTINF:10.0,\nseg1.ts\n"
                    self.send_response(200)
                    self.send_header("Content-Type", "application/vnd.apple.mpegurl")
                    self.send_header("Content-Length", str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)
                elif self.path == "/mock/seg1.ts":
                    content = b"G@\x00\x10MOCK_TS_PACKET_CONTENT_12345678" * 50
                    self.send_response(200)
                    self.send_header("Content-Type", "video/mp2t")
                    self.send_header("Content-Length", str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)
                else:
                    self.send_error(404)

            def log_message(self, format, *args):
                pass

        mock_server = http.server.HTTPServer(("127.0.0.1", 0), MockUpstreamHandler)
        mock_port = mock_server.server_port
        mock_thread = threading.Thread(target=mock_server.serve_forever, daemon=True)
        mock_thread.start()

        try:
            # 1. 测试 M3U8 重写
            target_m3u8 = f"http://127.0.0.1:{mock_port}/mock/live.m3u8"
            proxy_m3u8_url = f"http://127.0.0.1:{TEST_PORT}/api/stream_proxy?url={urllib.parse.quote(target_m3u8)}"
            with urllib.request.urlopen(proxy_m3u8_url) as resp:
                self.assertEqual(resp.status, 200)
                body = resp.read().decode("utf-8")
                self.assertIn("#EXTM3U", body)
                expected_part = f"/api/stream_proxy?url={urllib.parse.quote(f'http://127.0.0.1:{mock_port}/mock/seg1.ts')}"
                self.assertIn(expected_part, body)

            # 2. 测试 TS 分片流式代理
            target_ts = f"http://127.0.0.1:{mock_port}/mock/seg1.ts"
            proxy_ts_url = f"http://127.0.0.1:{TEST_PORT}/api/stream_proxy?url={urllib.parse.quote(target_ts)}"
            with urllib.request.urlopen(proxy_ts_url) as resp:
                self.assertEqual(resp.status, 200)
                self.assertIn("video/mp2t", resp.headers.get("Content-Type", ""))
                ts_data = resp.read()
                self.assertTrue(ts_data.startswith(b"G@\x00\x10MOCK_TS_PACKET"))
                self.assertEqual(len(ts_data), len(b"G@\x00\x10MOCK_TS_PACKET_CONTENT_12345678" * 50))
        finally:
            mock_server.shutdown()
            mock_server.server_close()


if __name__ == "__main__":
    unittest.main()
