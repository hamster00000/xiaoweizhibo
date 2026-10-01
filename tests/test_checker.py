import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from live_crawler.checker import StreamChecker
from live_crawler.fetcher import ChannelItem


class TestStreamChecker(unittest.TestCase):
    def setUp(self):
        self.checker = StreamChecker(timeout=1.0, concurrency=5)

    def test_check_single_via_head(self):
        item = ChannelItem(
            raw_name="CCTV-1",
            name="CCTV-1",
            url="http://mock.live/cctv1.m3u8",
            group="央视频道"
        )

        mock_head_resp = MagicMock()
        mock_head_resp.status_code = 200

        mock_client = MagicMock()
        mock_client.head = AsyncMock(return_value=mock_head_resp)

        async def run_test():
            res = await self.checker.check_single(mock_client, item)
            self.assertTrue(res.is_valid)
            self.assertIsNotNone(res.latency_ms)
            self.assertGreater(res.latency_ms, 0)
            mock_client.head.assert_awaited_once()

        asyncio.run(run_test())

    def test_check_single_success_fallback_get(self):
        item = ChannelItem(
            raw_name="CCTV-1",
            name="CCTV-1",
            url="http://mock.live/cctv1.m3u8",
            group="央视频道"
        )

        # 模拟 HEAD 失败或抛异常
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        async def mock_iter():
            yield b"#EXTM3U\n#EXT-X-STREAM-INF\n"

        mock_resp.aiter_bytes = mock_iter

        mock_stream_ctx = MagicMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)

        mock_client = MagicMock()
        mock_client.head = AsyncMock(side_effect=Exception("HEAD not allowed"))
        mock_client.stream.return_value = mock_stream_ctx

        async def run_test():
            res = await self.checker.check_single(mock_client, item)
            self.assertTrue(res.is_valid)
            self.assertIsNotNone(res.latency_ms)
            self.assertGreater(res.latency_ms, 0)

        asyncio.run(run_test())

    def test_check_single_failure(self):
        item = ChannelItem(
            raw_name="CCTV-1",
            name="CCTV-1",
            url="http://mock.live/dead.m3u8",
            group="央视频道"
        )

        mock_stream_ctx = MagicMock()
        mock_stream_ctx.__aenter__ = AsyncMock(side_effect=Exception("Connection refused"))
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)

        mock_client = MagicMock()
        mock_client.head = AsyncMock(side_effect=Exception("Connection refused"))
        mock_client.stream.return_value = mock_stream_ctx

        async def run_test():
            res = await self.checker.check_single(mock_client, item)
            self.assertFalse(res.is_valid)
            self.assertIsNone(res.latency_ms)

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
