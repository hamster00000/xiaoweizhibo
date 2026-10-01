import asyncio
import time
from typing import Callable, List, Optional
import httpx
from live_crawler.fetcher import ChannelItem


class StreamChecker:
    """基于异步并发的流可用性与响应延迟探测器 (契合技术设计 4.3 规范)"""

    def __init__(
        self,
        timeout: float = 3.0,
        concurrency: int = 20,
        user_agent: str = "okhttp/3.15 XiaoWeiLive/5.0.0"
    ):
        self.timeout = timeout
        self.concurrency = concurrency
        self.user_agent = user_agent

    async def check_single(self, client: httpx.AsyncClient, item: ChannelItem) -> ChannelItem:
        """检测单个频道的连通性与首包延迟 (第一步 HEAD 优先探测，第二步 GET Range 降级)"""
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "*/*",
        }
        start_time = time.perf_counter()

        # 第一步：优先尝试 HTTP HEAD 请求获取响应头
        try:
            if hasattr(client, "head"):
                head_call = client.head(item.url, headers=headers, timeout=self.timeout)
                if asyncio.iscoroutine(head_call):
                    resp = await head_call
                    if resp.status_code in (200, 206, 301, 302, 307, 308):
                        latency = (time.perf_counter() - start_time) * 1000.0
                        item.latency_ms = round(latency, 2)
                        item.is_valid = True
                        return item
        except Exception:
            pass

        # 第二步：针对屏蔽 HEAD 的 CDN，降级为 Range: bytes=0-1024 的分片 GET 请求
        get_headers = {
            "User-Agent": self.user_agent,
            "Accept": "*/*",
            "Range": "bytes=0-1024"
        }
        start_time = time.perf_counter()
        try:
            async with client.stream("GET", item.url, headers=get_headers, timeout=self.timeout) as resp:
                if (200 <= resp.status_code < 400) or resp.status_code == 206:
                    async for _ in resp.aiter_bytes():
                        break
                    latency = (time.perf_counter() - start_time) * 1000.0
                    item.latency_ms = round(latency, 2)
                    item.is_valid = True
                    return item
        except Exception:
            pass

        item.is_valid = False
        item.latency_ms = None
        return item

    async def check_all(
        self,
        items: List[ChannelItem],
        on_progress: Optional[Callable[[int, int], None]] = None
    ) -> List[ChannelItem]:
        """并发批量检测所有频道链接"""
        semaphore = asyncio.Semaphore(self.concurrency)
        total = len(items)
        completed = 0

        limits = httpx.Limits(max_keepalive_connections=self.concurrency, max_connections=self.concurrency * 2)
        async with httpx.AsyncClient(verify=False, follow_redirects=True, limits=limits) as client:
            async def _worker(item: ChannelItem):
                nonlocal completed
                async with semaphore:
                    res = await self.check_single(client, item)
                    completed += 1
                    if on_progress:
                        on_progress(completed, total)
                    return res

            tasks = [_worker(item) for item in items]
            results = await asyncio.gather(*tasks, return_exceptions=False)
            return results
