#!/usr/bin/env python3
"""
清风直播源自动化抓取、测速与导出运行入口
"""
import argparse
import sys
from live_crawler.manager import LiveSourceManager


def main():
    parser = argparse.ArgumentParser(description="清风直播 - 直播源自动化抓取与测速维护工具")
    parser.add_argument("-c", "--config", default="config.json", help="配置文件路径 (默认: config.json)")
    parser.add_argument("--dry-run", action="store_true", help="跳过流媒体网络连通性测速，直接导出")
    parser.add_argument("--timeout", type=float, default=None, help="覆盖测速超时时间（秒）")
    parser.add_argument("--concurrency", type=int, default=None, help="覆盖测速并发任务数")
    parser.add_argument("--max-lines", type=int, default=None, help="每个频道最多保留的最优线路数")

    args = parser.parse_args()

    try:
        manager = LiveSourceManager(config_path=args.config)

        if args.timeout is not None:
            manager.checker.timeout = args.timeout
        if args.concurrency is not None:
            manager.checker.concurrency = args.concurrency
        if args.max_lines is not None:
            manager.exporter.max_lines_per_channel = args.max_lines

        manager.run(dry_run=args.dry_run)
    except Exception as e:
        print(f"运行出错: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
