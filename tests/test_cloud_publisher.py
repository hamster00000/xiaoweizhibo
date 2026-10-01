import unittest
from scripts.publish_to_cloud import generate_accelerated_urls


class TestCloudPublisher(unittest.TestCase):
    def test_github_cdn_generation(self):
        repo = "https://github.com/testuser/tv_live"
        urls = generate_accelerated_urls(repo, branch="main")
        self.assertIn("jsdelivr_m3u", urls)
        self.assertIn("ghproxy_m3u", urls)
        self.assertEqual(urls["jsdelivr_m3u"], "https://fastly.jsdelivr.net/gh/testuser/tv_live@main/output/live.m3u")
        self.assertIn("ghproxy.net", urls["ghproxy_m3u"])

    def test_gitee_url_generation(self):
        repo = "https://gitee.com/testuser/tv_live"
        urls = generate_accelerated_urls(repo, branch="master")
        self.assertIn("gitee_raw_m3u", urls)
        self.assertEqual(urls["gitee_raw_m3u"], "https://gitee.com/testuser/tv_live/raw/master/live.m3u")


if __name__ == "__main__":
    unittest.main()
