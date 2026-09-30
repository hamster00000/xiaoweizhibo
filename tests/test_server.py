import json
import socketserver
import threading
import time
import unittest
import urllib.request
from server import LiveDemoHandler

TEST_PORT = 18099


class TestLiveDemoServer(unittest.TestCase):
    httpd = None
    server_thread = None

    @classmethod
    def setUpClass(cls):
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
            self.assertEqual(data["status"], "ok")

    def test_serve_index(self):
        url = f"http://127.0.0.1:{TEST_PORT}/"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            content = resp.read().decode("utf-8")
            self.assertIn("小薇直播纯净版", content)

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


if __name__ == "__main__":
    unittest.main()
