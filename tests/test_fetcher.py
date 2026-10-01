import os
import tempfile
import unittest
from live_crawler.fetcher import SourceFetcher, decode_bytes_adaptive
from live_crawler.normalizer import ChannelNormalizer


class TestSourceFetcher(unittest.TestCase):
    def setUp(self):
        self.normalizer = ChannelNormalizer()
        self.fetcher = SourceFetcher(normalizer=self.normalizer)

    def test_parse_m3u(self):
        m3u_text = """#EXTM3U
#EXTINF:-1 tvg-id="cctv1" tvg-name="CCTV1" tvg-logo="https://example.com/cctv1.png" group-title="央视频道",CCTV-1 综合
http://stream.example.com/cctv1.m3u8
#EXTINF:-1 tvg-name="湖南卫视" group-title="卫视频道",湖南卫视高清
https://stream.example.com/hunan.flv
#EXTINF:-1 group-title="广告",购物特惠频道
http://stream.example.com/ad.m3u8
"""
        items = self.fetcher.parse_m3u(m3u_text, source_name="test_src")
        # 购物频道应当被过滤掉
        self.assertEqual(len(items), 2)

        cctv1 = items[0]
        self.assertEqual(cctv1.name, "CCTV-1")
        self.assertEqual(cctv1.url, "http://stream.example.com/cctv1.m3u8")
        self.assertEqual(cctv1.group, "央视频道")
        self.assertEqual(cctv1.tvg_id, "cctv1")
        self.assertEqual(cctv1.logo, "https://example.com/cctv1.png")
        self.assertEqual(cctv1.tvg_logo, "https://example.com/cctv1.png")
        self.assertEqual(cctv1.source_origin, "test_src")

        hunan = items[1]
        self.assertEqual(hunan.name, "湖南卫视")
        self.assertEqual(hunan.url, "https://stream.example.com/hunan.flv")
        self.assertEqual(hunan.group, "卫视频道")

    def test_parse_txt(self):
        txt_text = """央视频道,#genre#
CCTV-1 综合,http://stream.example.com/cctv1.m3u8
CCTV-2,http://stream.example.com/cctv2.m3u8

卫视频道,#genre#
湖南卫视 HD,http://stream.example.com/hunan.m3u8
电视购物,#genre#
家有购物,http://stream.example.com/ad.m3u8
"""
        items = self.fetcher.parse_txt(txt_text, source_name="txt_src")
        self.assertEqual(len(items), 3)
        self.assertEqual(items[0].name, "CCTV-1")
        self.assertEqual(items[1].name, "CCTV-2")
        self.assertEqual(items[2].name, "湖南卫视")
        self.assertEqual(items[2].group, "卫视频道")

    def test_decode_bytes_adaptive(self):
        # UTF-8 with BOM
        utf8_bom = "央视频道,#genre#".encode("utf-8-sig")
        self.assertEqual(decode_bytes_adaptive(utf8_bom), "央视频道,#genre#")

        # GBK
        gbk_bytes = "卫视频道,#genre#".encode("gbk")
        self.assertEqual(decode_bytes_adaptive(gbk_bytes), "卫视频道,#genre#")

    def test_fetch_local_file_gbk(self):
        with tempfile.NamedTemporaryFile("wb", delete=False) as f:
            f.write("央视频道,#genre#\nCCTV-1,http://live/1.m3u8\n".encode("gbk"))
            tmp_path = f.name

        try:
            content = self.fetcher.fetch_text(tmp_path)
            self.assertIn("央视频道,#genre#", content)
            self.assertIn("CCTV-1", content)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


if __name__ == "__main__":
    unittest.main()
