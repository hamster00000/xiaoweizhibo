import os
import unittest
from demo import run_demo


class TestDemo(unittest.TestCase):
    def test_run_demo(self):
        # 验证 demo 能顺畅跑通并生成 output/demo_xiaowei.txt
        run_demo()
        self.assertTrue(os.path.exists("output/demo_xiaowei.txt"))
        with open("output/demo_xiaowei.txt", "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("央视频道,#genre#", content)
            self.assertIn("CCTV-1", content)
            self.assertIn("卫视频道,#genre#", content)
            self.assertIn("湖南卫视", content)
            # 确认购物广告频道已被排除
            self.assertNotIn("特惠购物", content)
            self.assertNotIn("特惠导购", content)


if __name__ == "__main__":
    unittest.main()
