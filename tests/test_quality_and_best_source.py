import os
import unittest


class TestQualityAndBestSourceFeature(unittest.TestCase):
    def setUp(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.index_path = os.path.join(self.base_dir, "web", "index.html")
        self.java_path = os.path.join(
            self.base_dir,
            "android_tv", "app", "src", "main", "java", "com", "qingfeng", "live", "MainActivity.java"
        )
        with open(self.index_path, "r", encoding="utf-8") as f:
            self.index_content = f.read()

        with open(self.java_path, "r", encoding="utf-8") as f:
            self.java_content = f.read()

    def test_quality_selector_ui_elements(self):
        """测试清晰度快速选择按钮、浮动菜单及档位"""
        # 1. 顶部控制条画质切换按钮
        self.assertIn('id="btnTvQuality"', self.index_content)
        self.assertIn('toggleQualityMenu()', self.index_content)

        # 2. 清晰度浮动菜单及4个画质档位 (超清1080P, 高清720P, 标清/流畅480P防卡, 自动Auto)
        self.assertIn('id="tvQualityMenu"', self.index_content)
        self.assertIn('setPlaybackQuality(\'1080P\')', self.index_content)
        self.assertIn('setPlaybackQuality(\'720P\')', self.index_content)
        self.assertIn('setPlaybackQuality(\'480P\')', self.index_content)
        self.assertIn('setPlaybackQuality(\'auto\')', self.index_content)
        self.assertIn('防卡推荐', self.index_content)

        # 3. 电视大屏浮动 Toast 通知
        self.assertIn('id="tvToastNotice"', self.index_content)
        self.assertIn('.tv-toast-notice', self.index_content)

    def test_remote_and_keyboard_quality_shortcuts(self):
        """测试遥控器画质按键与键盘快捷键 [Q] / [M]"""
        # 1. 仿真遥控器画质快捷键
        self.assertIn('id="btnRemoteQuality"', self.index_content)
        self.assertIn('cycleQuality()', self.index_content)
        self.assertIn('快速选清晰度', self.index_content)

        # 2. 键盘 Q 键与 M 键监听
        self.assertIn('KeyQ', self.index_content)
        self.assertIn('KeyM', self.index_content)

        # 3. 遥控操作说明更新
        self.assertIn('快速切换清晰度', self.index_content)

    def test_single_best_source_default_mode(self):
        """测试默认情况下只显一个信号源，最好的"""
        # 1. 默认状态变量
        self.assertIn('isTableOnlyBest = true', self.index_content)

        # 2. 切换按钮与表头
        self.assertIn('id="btnTableOnlyBest"', self.index_content)
        self.assertIn('toggleTableSourceView()', self.index_content)
        self.assertIn('id="channelTableHeadRow"', self.index_content)
        self.assertIn('最好信号源 (极速第一)', self.index_content)

        # 3. 最优源徽标
        self.assertIn('badge-best-source', self.index_content)
        self.assertIn('badge-quality-tag', self.index_content)
        self.assertIn('⭐ 最优第一源', self.index_content)

        # 4. 电视节目单抽屉也是单台只显最好源
        self.assertIn('⭐最优', self.index_content)

        # 5. 步骤 4 专属订阅直链提供单台最好源直链
        self.assertIn('/live.txt?best=1', self.index_content)
        self.assertIn('/live.m3u?best=1', self.index_content)

    def test_android_tv_menu_key_quality_mapping(self):
        """测试 Android TV 遥控器菜单键绑定快速切换清晰度"""
        self.assertIn('KeyEvent.KEYCODE_MENU', self.java_content)
        self.assertIn('cycleQuality()', self.java_content)


if __name__ == "__main__":
    unittest.main()
