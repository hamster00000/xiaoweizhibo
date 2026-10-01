import asyncio
from datetime import datetime
import json
import os
import sys
from typing import Dict, List, Optional
from live_crawler.normalizer import ChannelNormalizer
from live_crawler.fetcher import SourceFetcher, ChannelItem
from live_crawler.checker import StreamChecker
from live_crawler.exporter import StreamExporter


class LiveSourceManager:
    """直播源采集、测速与导出总调度器 (契合技术设计 5.1 与 5.2 规范)"""

    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.config = self._load_config(config_path)

        self.normalizer = ChannelNormalizer(
            channel_groups=self.config.get("channel_groups", []),
            ad_keywords=self.config.get("ad_keywords", [])
        )

        checker_cfg = self.config.get("checker", {})
        self.user_agent = checker_cfg.get("user_agent", "okhttp/3.15 XiaoWeiLive/5.0.0")
        self.fetcher = SourceFetcher(normalizer=self.normalizer, user_agent=self.user_agent)

        self.checker = StreamChecker(
            timeout=float(checker_cfg.get("timeout", 3.0)),
            concurrency=int(checker_cfg.get("concurrency", 25)),
            user_agent=self.user_agent
        )

        output_cfg = self.config.get("output", {})
        self.exporter = StreamExporter(
            max_lines_per_channel=int(output_cfg.get("max_lines_per_channel", 3))
        )

        # 熔断安全阈值（若有效源数低于该值且已存在旧文件，则熔断保护拒绝覆写）
        self.min_valid_channels = int(self.config.get("min_valid_channels", 1))

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
        output_cfg = self.config.get("output", {})
        out_dir = output_cfg.get("dir", "output")
        txt_name = output_cfg.get("xiaowei_txt", "live_xiaowei.txt")
        m3u_name = output_cfg.get("standard_m3u", "live.m3u")
        txt_target = os.path.join(out_dir, txt_name)
        m3u_target = os.path.join(out_dir, m3u_name)
        status_target = os.path.join(out_dir, "status.json")

        # 1. 抓取所有源
        raw_items = self.fetch_all_sources()
        if not raw_items:
            print("[!] 未从任何数据源获取到有效频道记录。")
            if os.path.exists(txt_target):
                print("[!] 自动回退复用已有本地源，避免电视端列表空白。")
            return {
                "total_raw": 0,
                "valid_count": 0,
                "status": "warning",
                "message": "未获取到有效数据，保留已有备份"
            }

        print(f"\n[+] 聚合完成，总计解析出 {len(raw_items)} 条频道条目。")

        # 2. 测速与有效性检验
        if dry_run:
            print("[*] Dry-run 模式：跳过流媒体网络连通性测速...")
            checked_items = raw_items
            for it in checked_items:
                it.is_valid = True
                if it.latency_ms is None:
                    it.latency_ms = 20.0
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

        # 3. 熔断保护机制：若有效源数量低于安全阈值且历史文件存在，拒绝覆写
        if len(valid_items) < self.min_valid_channels and os.path.exists(txt_target):
            warning_msg = (
                f"[!] 触发有效性熔断保护：本轮有效频道数 ({len(valid_items)}) "
                f"低于安全阈值 ({self.min_valid_channels})，拒绝覆写已有源文件以保障电视端正常播放。"
            )
            print(warning_msg, file=sys.stderr)
            return {
                "total_raw": len(raw_items),
                "valid_count": len(valid_items),
                "circuit_breaker_triggered": True,
                "status": "circuit_breaker",
                "message": warning_msg,
                "txt_path": txt_target,
                "m3u_path": m3u_target
            }

        # 4. 分组、排序与保留最优线路
        grouped = self.exporter.deduplicate_and_rank(checked_items)

        # 5. 导出文件 (原子写入)
        txt_file, m3u_file = self.exporter.save_to_files(
            grouped,
            output_dir=out_dir,
            xiaowei_filename=txt_name,
            m3u_filename=m3u_name
        )

        print("\n=== 导出完成 ===")
        print(f"小薇直播专用 TXT 文件: {txt_file}")
        print(f"通用标准 M3U 播放列表: {m3u_file}")

        # 计算频道总数与总线路数、平均延迟
        total_channels = sum(len(chs) for chs in grouped.values())
        total_lines = 0
        latencies = []
        for chs in grouped.values():
            for lines in chs.values():
                total_lines += len(lines)
                for line in lines:
                    if line.latency_ms is not None:
                        latencies.append(line.latency_ms)

        avg_latency = round(sum(latencies) / len(latencies), 1) if latencies else 0.0
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 统计概览
        summary = {
            "status": "ok",
            "channels_count": total_channels,
            "total_lines": total_lines,
            "last_updated": now_str,
            "avg_latency_ms": avg_latency,
            "sources_count": len(self.config.get("sources", [])),
            "total_raw": len(raw_items),
            "valid_count": len(valid_items),
            "groups": {g: len(chs) for g, chs in grouped.items()},
            "txt_path": txt_file,
            "m3u_path": m3u_file
        }

        # 写入 status.json 用于 Web UI 和 API 查询
        try:
            status_tmp = status_target + ".tmp"
            with open(status_tmp, "w", encoding="utf-8") as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(status_tmp, status_target)
        except Exception as e:
            print(f"[!] 写入状态文件失败: {e}", file=sys.stderr)

        print("\n=== 频道分组概况 ===")
        for grp, count in summary["groups"].items():
            print(f"  - {grp}: {count} 个频道")

        return summary

    def run(self, dry_run: bool = False) -> Dict:
        """同步运行入口"""
        return asyncio.run(self.run_pipeline_async(dry_run=dry_run))

    def get_status(self) -> Dict:
        """获取当前服务健康状态与源统计信息"""
        output_cfg = self.config.get("output", {})
        out_dir = output_cfg.get("dir", "output")
        status_file = os.path.join(out_dir, "status.json")

        if os.path.exists(status_file):
            try:
                with open(status_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

        # 备选推断状态
        txt_name = output_cfg.get("xiaowei_txt", "live_xiaowei.txt")
        txt_path = os.path.join(out_dir, txt_name)
        has_file = os.path.exists(txt_path)
        mtime = datetime.fromtimestamp(os.path.getmtime(txt_path)).strftime("%Y-%m-%d %H:%M:%S") if has_file else "未生成"

        return {
            "status": "ok" if has_file else "init",
            "channels_count": 0,
            "total_lines": 0,
            "last_updated": mtime,
            "avg_latency_ms": 0.0,
            "sources_count": len(self.config.get("sources", []))
        }
