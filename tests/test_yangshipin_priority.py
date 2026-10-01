import unittest
from live_crawler.fetcher import ChannelItem
from live_crawler.exporter import StreamExporter
from live_crawler.normalizer import ChannelNormalizer


class TestYangShiPinPriority(unittest.TestCase):
    def setUp(self):
        self.exporter = StreamExporter(max_lines_per_channel=3, prioritize_yangshipin=True)

    def test_yangshipin_property_detection(self):
        # 1. URL 含有 ysp / cctv.cn / yangshipin
        item1 = ChannelItem(
            raw_name="CCTV-1 综合",
            name="CCTV-1",
            url="http://mobilelive-ds.ysp.cctv.cn/ysp/2013693901.m3u8",
            group="央视频道",
            is_valid=True
        )
        self.assertTrue(item1.is_yangshipin, "ysp.cctv.cn 应被识别为央视频线路")

        item2 = ChannelItem(
            raw_name="CCTV-2",
            name="CCTV-2",
            url="http://liveop.cctv.cn/hls/CCTV2/playlist.m3u8",
            group="央视频道",
            is_valid=True
        )
        self.assertTrue(item2.is_yangshipin, "cctv.cn 应被识别为央视频/央视官方线路")

        # 2. raw_name 含有 央视频 / ysp
        item3 = ChannelItem(
            raw_name="CCTV-5 [央视频高码率]",
            name="CCTV-5",
            url="http://112.25.12.3:8080/live/cctv5.m3u8",
            group="央视频道",
            is_valid=True
        )
        self.assertTrue(item3.is_yangshipin, "名称中包含[央视频]应被识别")

        # 3. 普通非央视频源
        item4 = ChannelItem(
            raw_name="CCTV-1",
            name="CCTV-1",
            url="http://198.204.228.26/live/cctv1hd.m3u8",
            group="央视频道",
            is_valid=True
        )
        self.assertFalse(item4.is_yangshipin, "普通海外/第三方IPTV源不应被误判为央视频")

    def test_yangshipin_priority_over_faster_non_ysp(self):
        """测试核心需求：线路优先使用 yangshipin，即便第三方源延迟略低，央视频也排第一"""
        items = [
            # 第三方源，延迟 15ms (极快)
            ChannelItem(raw_name="CCTV-1", name="CCTV-1", url="http://fast.other/live.m3u8", group="央视频道", latency_ms=15.0, is_valid=True),
            # 央视频源，延迟 45ms
            ChannelItem(raw_name="CCTV-1", name="CCTV-1", url="http://mobilelive-ds.ysp.cctv.cn/ysp/cctv1.m3u8", group="央视频道", latency_ms=45.0, is_valid=True),
            # 普通较慢源，延迟 120ms
            ChannelItem(raw_name="CCTV-1", name="CCTV-1", url="http://slow.other/live.m3u8", group="央视频道", latency_ms=120.0, is_valid=True),
        ]

        grouped = self.exporter.deduplicate_and_rank(items)
        cctv1_lines = grouped["央视频道"]["CCTV-1"]

        # 央视频必须排在第 1 条线路
        self.assertEqual(cctv1_lines[0].url, "http://mobilelive-ds.ysp.cctv.cn/ysp/cctv1.m3u8")
        self.assertTrue(cctv1_lines[0].is_yangshipin)
        # 随后是较快的普通线路
        self.assertEqual(cctv1_lines[1].url, "http://fast.other/live.m3u8")

    def test_single_best_mode_selects_yangshipin(self):
        """测试单台最优模式 (only_best=True) 时，唯一导出的信号源是央视频"""
        items = [
            ChannelItem(raw_name="CCTV-2", name="CCTV-2", url="http://fast.other/cctv2.m3u8", group="央视频道", latency_ms=10.0, is_valid=True),
            ChannelItem(raw_name="CCTV-2 [央视频]", name="CCTV-2", url="http://liveop.cctv.cn/hls/cctv2.m3u8", group="央视频道", latency_ms=35.0, is_valid=True),
        ]

        # 1. 导出分组
        grouped = self.exporter.deduplicate_and_rank(items, only_best=True)
        self.assertEqual(len(grouped["央视频道"]["CCTV-2"]), 1)
        self.assertEqual(grouped["央视频道"]["CCTV-2"][0].url, "http://liveop.cctv.cn/hls/cctv2.m3u8")

        # 2. 导出小薇 TXT
        txt = self.exporter.export_xiaowei_txt(grouped, only_best=True)
        self.assertIn("CCTV-2,http://liveop.cctv.cn/hls/cctv2.m3u8", txt)
        self.assertNotIn("http://fast.other/cctv2.m3u8", txt)

        # 3. 导出标准 M3U
        m3u = self.exporter.export_standard_m3u(grouped, only_best=True)
        self.assertIn("http://liveop.cctv.cn/hls/cctv2.m3u8", m3u)
        self.assertNotIn("http://fast.other/cctv2.m3u8", m3u)

    def test_multiple_yangshipin_sorted_by_latency(self):
        """当有多条央视频源时，内部按延迟从小到大排序"""
        items = [
            ChannelItem(raw_name="CCTV-5", name="CCTV-5", url="http://ysp-slow.cctv.cn/cctv5.m3u8", group="央视频道", latency_ms=80.0, is_valid=True),
            ChannelItem(raw_name="CCTV-5", name="CCTV-5", url="http://ysp-fast.cctv.cn/cctv5.m3u8", group="央视频道", latency_ms=25.0, is_valid=True),
            ChannelItem(raw_name="CCTV-5", name="CCTV-5", url="http://other.com/cctv5.m3u8", group="央视频道", latency_ms=10.0, is_valid=True),
        ]

        grouped = self.exporter.deduplicate_and_rank(items)
        cctv5_lines = grouped["央视频道"]["CCTV-5"]

        self.assertEqual(cctv5_lines[0].url, "http://ysp-fast.cctv.cn/cctv5.m3u8")
        self.assertEqual(cctv5_lines[1].url, "http://ysp-slow.cctv.cn/cctv5.m3u8")
        self.assertEqual(cctv5_lines[2].url, "http://other.com/cctv5.m3u8")

    def test_non_yangshipin_channels_remain_latency_sorted(self):
        """无央视频源的频道 (如卫视或地方台) 保持原有按延迟升序逻辑"""
        items = [
            ChannelItem(raw_name="湖南卫视", name="湖南卫视", url="http://line-b/hunan.m3u8", group="卫视频道", latency_ms=60.0, is_valid=True),
            ChannelItem(raw_name="湖南卫视", name="湖南卫视", url="http://line-a/hunan.m3u8", group="卫视频道", latency_ms=20.0, is_valid=True),
        ]
        grouped = self.exporter.deduplicate_and_rank(items)
        hunan_lines = grouped["卫视频道"]["湖南卫视"]
        self.assertEqual(hunan_lines[0].url, "http://line-a/hunan.m3u8")
        self.assertEqual(hunan_lines[1].url, "http://line-b/hunan.m3u8")

    def test_yangshipin_cn_strictly_on_line_1(self):
        """测试将 yangshipin.cn 的订阅源绝对置于【线路 1】"""
        items = [
            # 第三方源 (10ms)
            ChannelItem(raw_name="CCTV-1", name="CCTV-1", url="http://other.com/cctv1.m3u8", group="央视频道", latency_ms=10.0, is_valid=True),
            # 央视频 ysp.cctv.cn 源 (20ms)
            ChannelItem(raw_name="CCTV-1", name="CCTV-1", url="http://mobilelive-ds.ysp.cctv.cn/ysp/cctv1.m3u8", group="央视频道", latency_ms=20.0, is_valid=True),
            # yangshipin.cn 域名或来源源 (50ms)
            ChannelItem(raw_name="CCTV-1 [yangshipin.cn]", name="CCTV-1", url="http://liveplay.yangshipin.cn/live/cctv1.m3u8", group="央视频道", latency_ms=50.0, is_valid=True, source_origin="yangshipin.cn"),
        ]

        grouped = self.exporter.deduplicate_and_rank(items)
        lines = grouped["央视频道"]["CCTV-1"]

        # 验证线路 1 必须是 yangshipin.cn
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[0].url, "http://liveplay.yangshipin.cn/live/cctv1.m3u8", "线路 1 必须是 yangshipin.cn")
        self.assertEqual(lines[1].url, "http://mobilelive-ds.ysp.cctv.cn/ysp/cctv1.m3u8", "线路 2 是其他央视频源")
        self.assertEqual(lines[2].url, "http://other.com/cctv1.m3u8", "线路 3 是第三方源")


if __name__ == "__main__":
    unittest.main()
