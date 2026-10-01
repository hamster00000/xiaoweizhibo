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

TEST_PORT_FULLSCREEN = 18105


class TestWebFullscreenFeature(unittest.TestCase):
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
        cls.httpd = socketserver.TCPServer(("", TEST_PORT_FULLSCREEN), LiveDemoHandler)
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.3)

    @classmethod
    def tearDownClass(cls):
        if cls.httpd:
            cls.httpd.shutdown()
            cls.httpd.server_close()

    def test_index_file_fullscreen_elements_and_css(self):
        index_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "index.html")
        self.assertTrue(os.path.exists(index_path), "web/index.html 必须存在")

        with open(index_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 1. 验证全屏控制按钮存在
        self.assertIn('id="btnTvFullscreen"', content)
        self.assertIn('toggleTvFullscreen()', content)

        # 2. 验证电视画面双击全屏能力
        self.assertIn('ondblclick="toggleTvFullscreen()"', content)

        # 3. 验证仿真遥控器全屏按钮及快捷说明
        self.assertIn('id="btnRemoteFullscreen"', content)
        self.assertIn('双击画面', content)

        # 4. 验证 CSS 全屏规则与沉浸模式
        self.assertIn('.tv-frame:fullscreen', content)
        self.assertIn('.tv-frame.is-fullscreen', content)
        self.assertIn('controls-idle', content)
        self.assertIn('.tv-ctrl-btn', content)

        # 5. 验证 JS 全屏 API 与键盘快捷键
        self.assertIn('function isTvFullscreen()', content)
        self.assertIn('function enterTvFullscreen(', content)
        self.assertIn('function exitTvFullscreen()', content)
        self.assertIn('fullscreenchange', content)
        self.assertIn('KeyF', content)

    def test_http_get_index_contains_fullscreen_support(self):
        url = f"http://127.0.0.1:{TEST_PORT_FULLSCREEN}/"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            self.assertEqual(resp.status, 200)
            body = resp.read().decode("utf-8")

        self.assertIn("btnTvFullscreen", body)
        self.assertIn("toggleTvFullscreen", body)
        self.assertIn("btnRemoteFullscreen", body)
        self.assertIn("is-fullscreen", body)


if __name__ == "__main__":
    unittest.main()
