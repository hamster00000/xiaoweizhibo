import json
import os
import socketserver
import struct
import tempfile
import threading
import time
import unittest
import urllib.request
import zipfile

from server import LiveDemoHandler
from live_crawler.manager import LiveSourceManager
from scripts.package_tv_app import get_tv_app_status, TV_APPS, TV_APP_DIR

TEST_PORT_TV = 18109


class TestTvPackagingAndEndpoints(unittest.TestCase):
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
        cls.httpd = socketserver.TCPServer(("", TEST_PORT_TV), LiveDemoHandler)
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.3)

    @classmethod
    def tearDownClass(cls):
        if cls.httpd:
            cls.httpd.shutdown()
            cls.httpd.server_close()

    def test_get_tv_app_status(self):
        status = get_tv_app_status()
        self.assertIn("qingfeng", status)
        self.assertIn("xiaowei", status)
        self.assertIn("mytv", status)
        self.assertIn("default", status)
        self.assertEqual(status["qingfeng"]["filename"], "QingFeng_Live_TV.apk")
        self.assertEqual(status["qingfeng"]["package"], "com.qingfeng.live.tv")
        self.assertEqual(status["xiaowei"]["package"], "com.live.zd")
        # 验证清风直播是独立隔离的
        self.assertTrue(status["qingfeng"]["is_isolated"])

    def test_qingfeng_tv_apk_isolated_package_and_signature(self):
        apk_path = os.path.join(TV_APP_DIR, "QingFeng_Live_TV.apk")
        self.assertTrue(os.path.exists(apk_path), f"APK 文件未找到: {apk_path}")
        self.assertGreater(os.path.getsize(apk_path), 5 * 1024 * 1024)

        with zipfile.ZipFile(apk_path, "r") as z:
            names = z.namelist()
            self.assertIn("AndroidManifest.xml", names)
            self.assertIn("resources.arsc", names)
            self.assertIn("META-INF/MANIFEST.MF", names)
            self.assertIn("META-INF/CERT.SF", names)
            self.assertIn("META-INF/CERT.RSA", names)

            manifest_bytes = z.read("AndroidManifest.xml")
            arsc_bytes = z.read("resources.arsc")

        # 解析 AXML 验证包名已被修改为 com.qingfeng.live.tv
        scnt, = struct.unpack("<I", manifest_bytes[16:20])
        offsets = struct.unpack(f"<{scnt}I", manifest_bytes[36:36 + scnt * 4])
        sstart, = struct.unpack("<I", manifest_bytes[28:32])
        sdata = manifest_bytes[8 + sstart:]
        strings = []
        for off in offsets:
            l, = struct.unpack("<H", sdata[off:off + 2])
            strings.append(sdata[off + 2:off + 2 + l * 2].decode("utf-16le", errors="ignore"))

        self.assertIn("com.qingfeng.live.tv", strings, "Manifest 中必须包含新包名 com.qingfeng.live.tv")
        self.assertNotIn("com.live.zd", strings, "Manifest 中不应残留小薇原包名 com.live.zd 以免覆盖已有应用")

        # 验证 resources.arsc 包含清风直播
        self.assertIn("清风直播".encode("utf-8"), arsc_bytes, "arsc 中必须包含应用名称'清风直播'")

    def test_download_apk_endpoint_and_headers(self):
        url = f"http://127.0.0.1:{TEST_PORT_TV}/download/tv-app.apk"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as res:
            self.assertEqual(res.status, 200)
            self.assertEqual(res.headers.get("Content-Type"), "application/vnd.android.package-archive")
            self.assertIn("attachment", res.headers.get("Content-Disposition", ""))
            self.assertIn("QingFeng_Live_TV.apk", res.headers.get("Content-Disposition", ""))
            chunk = res.read(1024)
            self.assertGreater(len(chunk), 0)

    def test_download_qingfeng_apk_endpoint(self):
        url = f"http://127.0.0.1:{TEST_PORT_TV}/download/qingfeng.apk"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as res:
            self.assertEqual(res.status, 200)
            self.assertIn("QingFeng_Live_TV.apk", res.headers.get("Content-Disposition", ""))

    def test_tv_info_api(self):
        url = f"http://127.0.0.1:{TEST_PORT_TV}/api/tv/info"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as res:
            self.assertEqual(res.status, 200)
            data = json.loads(res.read().decode("utf-8"))
            self.assertEqual(data["status"], "success")
            self.assertIn("isolation_notice", data)
            self.assertIn("com.qingfeng.live.tv", data["isolation_notice"])
            self.assertIn("subscription_urls", data)
            self.assertIn("download_urls", data)
            self.assertIn("install_guide", data)
            self.assertIn("recommended", data["download_urls"])

    def test_package_scripts_exist_and_executable(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        pkg_script = os.path.join(base_dir, "scripts", "package_tv_app.py")
        repack_script = os.path.join(base_dir, "scripts", "repackage_tv_app.py")
        install_script = os.path.join(base_dir, "scripts", "install_to_mi_tv.sh")

        self.assertTrue(os.path.exists(pkg_script))
        self.assertTrue(os.access(pkg_script, os.X_OK))
        self.assertTrue(os.path.exists(repack_script))
        self.assertTrue(os.access(repack_script, os.X_OK))
        self.assertTrue(os.path.exists(install_script))
        self.assertTrue(os.access(install_script, os.X_OK))

    def test_android_tv_project_structure(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        manifest = os.path.join(base_dir, "android_tv", "app", "src", "main", "AndroidManifest.xml")
        main_activity = os.path.join(base_dir, "android_tv", "app", "src", "main", "java", "com", "qingfeng", "live", "MainActivity.java")

        self.assertTrue(os.path.exists(manifest))
        self.assertTrue(os.path.exists(main_activity))
        with open(manifest, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("android.intent.category.LEANBACK_LAUNCHER", content)

    def test_web_index_tv_elements(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        index_html = os.path.join(base_dir, "web", "index.html")
        with open(index_html, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("btnXiaomiTV", content)
            self.assertIn("xiaomiTvModal", content)
            self.assertIn("com.qingfeng.live.tv", content)
            self.assertIn("双应用并存", content)
            self.assertIn("/download/tv-app.apk", content)


if __name__ == "__main__":
    unittest.main()
