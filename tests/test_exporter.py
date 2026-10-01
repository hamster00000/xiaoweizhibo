import os
import shutil
import tempfile
import unittest
from live_crawler.exporter import StreamExporter
from live_crawler.fetcher import ChannelItem


class TestStreamExporter(unittest.TestCase):
    def setUp(self):
        self.exporter = StreamExporter(max_lines_per_channel=2)
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_deduplicate_and_rank(self):
        items = [
            # CCTV-1: 3条线路，延迟分别为 300, 100, 200
            ChannelItem(raw_name="C1", name="CCTV-1", url="http://s1", group="央视频道", latency_ms=300.0, is_valid=True),
            ChannelItem(raw_name="C1", name="CCTV-1", url="http://s2", group="央视频道", latency_ms=100.0, is_valid=True),
            ChannelItem(raw_name="C1", name="CCTV-1", url="http://s3", group="央视频道", latency_ms=200.0, is_valid=True),
            # CCTV-1 重复 URL
            ChannelItem(raw_name="C1", name="CCTV-1", url="http://s1", group="央视频道", latency_ms=50.0, is_valid=True),
            # 失效源
            ChannelItem(raw_name="C1", name="CCTV-1", url="http://dead", group="央视频道", latency_ms=None, is_valid=False),
        ]

        grouped = self.exporter.deduplicate_and_rank(items)
        cctv1_lines = grouped["央视频道"]["CCTV-1"]

        # 由于 max_lines_per_channel=2，只保留最优前2条
        self.assertEqual(len(cctv1_lines), 2)
        # 最快的是 100ms (s2)，第二快的是 200ms (s3) (s1因重复已被过滤或排后)
        self.assertEqual(cctv1_lines[0].url, "http://s2")
        self.assertEqual(cctv1_lines[1].url, "http://s3")

    def test_export_xiaowei_txt(self):
        items = [
            ChannelItem(raw_name="CCTV-1", name="CCTV-1", url="http://cctv1", group="央视频道", is_valid=True, latency_ms=10.0),
            ChannelItem(raw_name="湖南卫视", name="湖南卫视", url="http://hunan", group="卫视频道", is_valid=True, latency_ms=20.0),
        ]
        grouped = self.exporter.deduplicate_and_rank(items)
        txt = self.exporter.export_xiaowei_txt(grouped)

        self.assertIn("央视频道,#genre#", txt)
        self.assertIn("CCTV-1,http://cctv1", txt)
        self.assertIn("卫视频道,#genre#", txt)
        self.assertIn("湖南卫视,http://hunan", txt)

    def test_export_standard_m3u(self):
        items = [
            ChannelItem(raw_name="CCTV-1", name="CCTV-1", url="http://cctv1", group="央视频道", is_valid=True, latency_ms=10.0, tvg_id="cctv1", tvg_logo="http://logo.png"),
        ]
        grouped = self.exporter.deduplicate_and_rank(items)
        m3u = self.exporter.export_standard_m3u(grouped)

        self.assertTrue(m3u.startswith("#EXTM3U"))
        self.assertIn('group-title="央视频道"', m3u)
        self.assertIn('tvg-logo="http://logo.png"', m3u)
        self.assertIn('tvg-id="cctv1"', m3u)
        self.assertIn("http://cctv1", m3u)

    def test_save_to_files_atomic(self):
        items = [
            ChannelItem(raw_name="CCTV-1", name="CCTV-1", url="http://cctv1", group="央视频道", is_valid=True, latency_ms=10.0),
        ]
        grouped = self.exporter.deduplicate_and_rank(items)
        txt_path, m3u_path = self.exporter.save_to_files(
            grouped,
            output_dir=self.test_dir,
            xiaowei_filename="test_xw.txt",
            m3u_filename="test.m3u"
        )

        self.assertTrue(os.path.exists(txt_path))
        self.assertTrue(os.path.exists(m3u_path))
        # 临时文件应该已被原子替换，不再残留
        self.assertFalse(os.path.exists(txt_path + ".tmp"))
        self.assertFalse(os.path.exists(m3u_path + ".tmp"))

        with open(txt_path, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("央视频道,#genre#", content)


if __name__ == "__main__":
    unittest.main()
