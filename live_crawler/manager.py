import asyncio
import json
import os
import sys
from typing import Dict, List, Optional
from live_crawler.normalizer import ChannelNormalizer
from live_crawler.fetcher import SourceFetcher, ChannelItem
from live_crawler.checker import StreamChecker
from live_crawler.exporter import StreamExporter


class LiveSourceManager:
    """直播源采集、测速与导出总调度器"""

    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.config = self._load_config(config_path)

        self.normalizer = ChannelNormalizer(
            channel_groups=self.config.get("channel_groups", []),
            ad_keywords=self.config.get("ad_keywords", [])
        )

        checker_cfg = self.config.get("checker", {})
        self.user_agent = checker_cfg.get("user_agent", "XiaoWeiLive/5.0")
        self.fetcher = SourceFetcher(normalizer=self.normalizer, user_agent=self.user_agent)

        self.checker = StreamChecker(
            timeout=float(checker_cfg.get("timeout", 3.0)),
            concurrency=int(checker_cfg.get("concurrency", 20)),
            user_agent=self.user_agent
        )

        output_cfg = self.config.get("output", {})
        self.exporter = StreamExporter(
            max_lines_per_channel=int(output_cfg.get("max_lines_per_channel", 4))
        )

    def _load_config(self, path: str) -> dict:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Configuration file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def fetch_all_sources(self) -> List[ChannelItem]:
        """抓取并汇聚所有配置的数据源"""
        sources = self.config.get("sources", [])
        all_items: List[ChannelItem] = []

        for src in sources:
            src_name = src.get("name", "unnamed")
            url = src.get("url")
            fmt = src.get("format", "auto")
            print(f"[*] 正在获取数据源: {src_name} ({url})...")
            try:
                content = self.fetcher.fetch_text(url)
                items = self.fetcher.parse(content, format_hint=fmt, source_name=src_name)
                print(f"    -> 成功解析出 {len(items)} 条频道记录")
                all_items.extend(items)
            except Exception as e:
                print(f"    [!] 获取或解析失败: {e}", file=sys.stderr)

        return all_items

    async def run_pipeline_async(self, dry_run: bool = False) -> Dict:
        """异步执行完整抓取、测速与导出管线"""
        # 1. 抓取所有源
        raw_items = self.fetch_all_sources()
        if not raw_items:
            print("[!] 未从任何数据源获取到有效频道记录。")
            return {"total_raw": 0, "valid_count": 0}

        print(f"\n[+] 聚合完成，总计解析出 {len(raw_items)} 条频道条目。")

        # 2. 测速与有效性检验
        if dry_run:
            print("[*] Dry-run 模式：跳过流媒体网络连通性测速...")
            checked_items = raw_items
            for it in checked_items:
                it.is_valid = True
        else:
            print(f"[*] 正在并发检测流媒体可用性 (并发数: {self.checker.concurrency}, 超时: {self.checker.timeout}s)...")
            
            def progress(current, total):
                if current % 20 == 0 or current == total:
                    pct = (current / total) * 100
                    print(f"\r    测速进度: {current}/{total} ({pct:.1f}%)", end="", flush=True)

            checked_items = await self.checker.check_all(raw_items, on_progress=progress)
            print()

        valid_items = [it for it in checked_items if it.is_valid]
        print(f"[+] 测速完成，可用有效直播源数: {len(valid_items)} / {len(checked_items)}")

        # 3. 分组、排序与保留最优线路
        grouped = self.exporter.deduplicate_and_rank(checked_items)

        # 4. 导出文件
        output_cfg = self.config.get("output", {})
        out_dir = output_cfg.get("dir", "output")
        txt_name = output_cfg.get("xiaowei_txt", "live_xiaowei.txt")
        m3u_name = output_cfg.get("standard_m3u", "live.m3u")

        txt_file, m3u_file = self.exporter.save_to_files(
            grouped,
            output_dir=out_dir,
            xiaowei_filename=txt_name,
            m3u_filename=m3u_name
        )

        print("\n=== 导出完成 ===")
        print(f"小薇直播专用 TXT 文件: {txt_file}")
        print(f"通用标准 M3U 播放列表: {m3u_file}")

        # 统计概览
        summary = {
            "total_raw": len(raw_items),
            "valid_count": len(valid_items),
            "groups": {g: len(chs) for g, chs in grouped.items()},
            "txt_path": txt_file,
            "m3u_path": m3u_file
        }

        print("\n=== 频道分组概况 ===")
        for grp, count in summary["groups"].items():
            print(f"  - {grp}: {count} 个频道")

        return summary

    def run(self, dry_run: bool = False) -> Dict:
        """同步运行入口"""
        return asyncio.run(self.run_pipeline_async(dry_run=dry_run))
