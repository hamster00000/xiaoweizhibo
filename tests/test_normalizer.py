import unittest
from live_crawler.normalizer import ChannelNormalizer


class TestChannelNormalizer(unittest.TestCase):
    def setUp(self):
        self.normalizer = ChannelNormalizer(
            channel_groups=[
                {"name": "央视频道", "patterns": [r"^CCTV-.*", r"^CGTN.*"]},
                {"name": "卫视频道", "patterns": [r".*卫视$"]}
            ],
            ad_keywords=["购物", "特惠", "测试"]
        )

    def test_normalize_cctv(self):
        cases = {
            "cctv1": "CCTV-1",
            "CCTV-1 综合": "CCTV-1",
            "CCTV1 高清": "CCTV-1",
            "cctv 5+ 体育赛事": "CCTV-5+",
            "CCTV-13 新闻": "CCTV-13",
            "CCTV-4K 超高清": "CCTV-4K",
            "CCTV-8K": "CCTV-8K"
        }
        for raw, expected in cases.items():
            self.assertEqual(self.normalizer.normalize_name(raw), expected)

    def test_normalize_weishi(self):
        cases = {
            "湖南卫视 高清": "湖南卫视",
            "浙江卫视 [1080P]": "浙江卫视",
            "东方卫视 (超清)": "东方卫视",
            "北京卫视": "北京卫视"
        }
        for raw, expected in cases.items():
            self.assertEqual(self.normalizer.normalize_name(raw), expected)

    def test_is_ad_channel(self):
        self.assertTrue(self.normalizer.is_ad_channel("电视购物"))
        self.assertTrue(self.normalizer.is_ad_channel("特惠商城专享"))
        self.assertTrue(self.normalizer.is_ad_channel("内部测试台"))
        self.assertFalse(self.normalizer.is_ad_channel("CCTV-1"))
        self.assertFalse(self.normalizer.is_ad_channel("湖南卫视"))

    def test_match_group(self):
        self.assertEqual(self.normalizer.match_group("CCTV-1"), "央视频道")
        self.assertEqual(self.normalizer.match_group("湖南卫视"), "卫视频道")
        self.assertEqual(self.normalizer.match_group("凤凰中文"), "其他频道")


if __name__ == "__main__":
    unittest.main()
