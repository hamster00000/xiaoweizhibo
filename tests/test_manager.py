import json
import os
import shutil
import tempfile
import unittest
from live_crawler.manager import LiveSourceManager


class TestLiveSourceManager(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.source_file = os.path.join(self.test_dir, "sample.txt")
        with open(self.source_file, "w", encoding="utf-8") as f:
            f.write("""央视频道,#genre#
CCTV-1 综合,http://stream.test/cctv1.m3u8
CCTV-2 财经,http://stream.test/cctv2.m3u8
卫视频道,#genre#
浙江卫视,http://stream.test/zhejiang.m3u8
""")

        self.config_file = os.path.join(self.test_dir, "test_config.json")
        self.output_dir = os.path.join(self.test_dir, "out")
        cfg = {
            "sources": [
                {
                    "name": "local_test",
                    "url": self.source_file,
                    "format": "txt"
                }
            ],
            "checker": {
                "timeout": 1.0,
                "concurrency": 2,
                "user_agent": "TestAgent"
            },
            "channel_groups": [
                {"name": "央视频道", "patterns": ["^CCTV-.*"]},
                {"name": "卫视频道", "patterns": [".*卫视$"]}
            ],
            "output": {
                "dir": self.output_dir,
                "xiaowei_txt": "test_xw.txt",
                "standard_m3u": "test.m3u",
                "max_lines_per_channel": 2
            },
            "min_valid_channels": 2
        }
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(cfg, f)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_run_dry_run_pipeline(self):
        mgr = LiveSourceManager(config_path=self.config_file)
        summary = mgr.run(dry_run=True)

        self.assertEqual(summary["total_raw"], 3)
        self.assertEqual(summary["valid_count"], 3)
        self.assertEqual(summary["channels_count"], 3)
        self.assertTrue(os.path.exists(summary["txt_path"]))
        self.assertTrue(os.path.exists(summary["m3u_path"]))

        # 检查 status.json
        status_file = os.path.join(self.output_dir, "status.json")
        self.assertTrue(os.path.exists(status_file))
        status_data = mgr.get_status()
        self.assertEqual(status_data["status"], "ok")
        self.assertEqual(status_data["channels_count"], 3)

        with open(summary["txt_path"], "r", encoding="utf-8") as f:
            txt_content = f.read()
            self.assertIn("CCTV-1,http://stream.test/cctv1.m3u8", txt_content)
            self.assertIn("浙江卫视,http://stream.test/zhejiang.m3u8", txt_content)

    def test_circuit_breaker_protection(self):
        """测试有效性熔断保护：当探测到的有效数低于阈值且存在旧文件时，拒绝覆写旧文件"""
        mgr = LiveSourceManager(config_path=self.config_file)
        # 首次先正常导出生成基线健康文件
        summary1 = mgr.run(dry_run=True)
        self.assertTrue(os.path.exists(summary1["txt_path"]))
        with open(summary1["txt_path"], "r", encoding="utf-8") as f:
            original_txt = f.read()

        # 修改 checker 让其所有探测均失败 (模拟全网源断流)
        async def mock_fail_all(items, on_progress=None):
            for it in items:
                it.is_valid = False
            return items

        mgr.checker.check_all = mock_fail_all

        # 运行管线，由于 min_valid_channels=2，而有效数=0，应当触发熔断
        summary2 = mgr.run(dry_run=False)
        self.assertTrue(summary2.get("circuit_breaker_triggered", False))

        # 旧文件内容必须被完整保留，不能被覆写为空
        with open(summary1["txt_path"], "r", encoding="utf-8") as f:
            current_txt = f.read()
        self.assertEqual(original_txt, current_txt)


if __name__ == "__main__":
    unittest.main()
