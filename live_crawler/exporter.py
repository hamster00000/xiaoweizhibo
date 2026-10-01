import os
import re
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
from live_crawler.fetcher import ChannelItem


class StreamExporter:
    """直播源清洗排序与多格式输出生成器 (契合技术设计 4.4 与 5.2 规范)"""

    # 央视排序权重
    CCTV_ORDER = [
        "CCTV-1", "CCTV-2", "CCTV-3", "CCTV-4", "CCTV-5", "CCTV-5+",
        "CCTV-6", "CCTV-7", "CCTV-8", "CCTV-9", "CCTV-10", "CCTV-11",
        "CCTV-12", "CCTV-13", "CCTV-14", "CCTV-15", "CCTV-16", "CCTV-17",
        "CCTV-4K", "CCTV-8K"
    ]

    # 重点卫视排序权重
    POPULAR_WEISHI = [
        "湖南卫视", "浙江卫视", "江苏卫视", "东方卫视", "北京卫视",
        "广东卫视", "深圳卫视", "安徽卫视", "山东卫视", "天津卫视",
        "重庆卫视", "四川卫视", "湖北卫视", "河南卫视", "江西卫视",
        "辽宁卫视", "黑龙江卫视", "吉林卫视", "河北卫视", "山西卫视",
        "陕西卫视", "贵州卫视", "云南卫视", "广西卫视", "海南卫视"
    ]

    def __init__(self, max_lines_per_channel: int = 3, only_best: bool = False):
        self.max_lines_per_channel = max_lines_per_channel
        self.only_best = only_best

    def deduplicate_and_rank(self, items: List[ChannelItem], only_best: Optional[bool] = None) -> Dict[str, Dict[str, List[ChannelItem]]]:
        """
        按 [分组 -> 频道名称] 分类去重，并按延迟从小到大保留最优的多条线路
        结构: { group_name: { channel_name: [ChannelItem, ...] } }
        """
        is_only_best = self.only_best if only_best is None else only_best
        line_limit = 1 if is_only_best else self.max_lines_per_channel

        grouped: Dict[str, Dict[str, List[ChannelItem]]] = defaultdict(lambda: defaultdict(list))
        seen_urls = set()

        # 仅保留有效或者未校验过的条目（过滤确定失效的）
        valid_items = [it for it in items if it.is_valid]
        # 若全部未标记有效（如 dry-run 未检测场景），则放行全部
        if not valid_items and any(it.latency_ms is None for it in items):
            valid_items = items

        for item in valid_items:
            if item.url in seen_urls:
                continue
            seen_urls.add(item.url)
            grouped[item.group][item.name].append(item)

        # 对每个频道的线路按响应延迟升序排序并截取最大限制
        for group, channels in grouped.items():
            for ch_name, lines in channels.items():
                lines.sort(key=lambda x: (x.latency_ms is None, x.latency_ms or 99999))
                grouped[group][ch_name] = lines[:line_limit]

        return grouped

    def _sort_channels(self, group_name: str, channels: Dict[str, List[ChannelItem]]) -> List[Tuple[str, List[ChannelItem]]]:
        """对分组内的频道进行人性化排序"""
        items_list = list(channels.items())

        if group_name == "央视频道":
            def cctv_key(entry):
                name = entry[0]
                if name in self.CCTV_ORDER:
                    return (0, self.CCTV_ORDER.index(name))
                return (1, name)
            items_list.sort(key=cctv_key)

        elif group_name == "卫视频道":
            def weishi_key(entry):
                name = entry[0]
                if name in self.POPULAR_WEISHI:
                    return (0, self.POPULAR_WEISHI.index(name))
                return (1, name)
            items_list.sort(key=weishi_key)

        else:
            items_list.sort(key=lambda x: x[0])

        return items_list

    def export_xiaowei_txt(self, grouped_channels: Dict[str, Dict[str, List[ChannelItem]]], only_best: bool = False) -> str:
        """生成小薇直播专用的分类 TXT 格式，支持单台仅保留最优单源"""
        lines: List[str] = []
        # 预设首选分组顺序
        group_priority = ["央视频道", "卫视频道", "地方频道"]
        all_groups = group_priority + [g for g in grouped_channels.keys() if g not in group_priority]

        for group in all_groups:
            if group not in grouped_channels or not grouped_channels[group]:
                continue
            lines.append(f"{group},#genre#")
            sorted_channels = self._sort_channels(group, grouped_channels[group])
            for ch_name, channel_lines in sorted_channels:
                lines_to_export = channel_lines[:1] if (only_best or self.only_best) else channel_lines
                for line in lines_to_export:
                    lines.append(f"{ch_name},{line.url}")
            lines.append("")  # 分组间留空行更易阅读

        return "\n".join(lines).strip() + "\n"

    def export_standard_m3u(self, grouped_channels: Dict[str, Dict[str, List[ChannelItem]]], epg_url: str = "https://live.fanmingming.com/e.xml", only_best: bool = False) -> str:
        """生成通用 M3U 播放列表格式，支持单台仅保留最优单源"""
        lines = [f'#EXTM3U x-tvg-url="{epg_url}"']
        group_priority = ["央视频道", "卫视频道", "地方频道"]
        all_groups = group_priority + [g for g in grouped_channels.keys() if g not in group_priority]

        for group in all_groups:
            if group not in grouped_channels:
                continue
            sorted_channels = self._sort_channels(group, grouped_channels[group])
            for ch_name, channel_lines in sorted_channels:
                lines_to_export = channel_lines[:1] if (only_best or self.only_best) else channel_lines
                for idx, line in enumerate(lines_to_export):
                    display_name = ch_name if len(lines_to_export) == 1 else f"{ch_name} (线路{idx+1})"
                    logo_val = line.tvg_logo or getattr(line, "logo", "")
                    logo_attr = f' tvg-logo="{logo_val}"' if logo_val else ""
                    id_attr = f' tvg-id="{line.tvg_id}"' if line.tvg_id else ""
                    lines.append(f'#EXTINF:-1{id_attr} tvg-name="{ch_name}"{logo_attr} group-title="{group}",{display_name}')
                    lines.append(line.url)

        return "\n".join(lines) + "\n"

    def save_to_files(
        self,
        grouped_channels: Dict[str, Dict[str, List[ChannelItem]]],
        output_dir: str = "output",
        xiaowei_filename: str = "live_xiaowei.txt",
        m3u_filename: str = "live.m3u"
    ) -> Tuple[str, str]:
        """将两种格式写入目标输出目录，采用原子写入 (先 .tmp 再 os.replace) 保证读写无冲突"""
        os.makedirs(output_dir, exist_ok=True)
        txt_path = os.path.join(output_dir, xiaowei_filename)
        m3u_path = os.path.join(output_dir, m3u_filename)

        txt_tmp = txt_path + ".tmp"
        m3u_tmp = m3u_path + ".tmp"

        txt_content = self.export_xiaowei_txt(grouped_channels)
        with open(txt_tmp, "w", encoding="utf-8") as f:
            f.write(txt_content)
            f.flush()
            os.fsync(f.fileno())

        m3u_content = self.export_standard_m3u(grouped_channels)
        with open(m3u_tmp, "w", encoding="utf-8") as f:
            f.write(m3u_content)
            f.flush()
            os.fsync(f.fileno())

        # 原子重命名
        os.replace(txt_tmp, txt_path)
        os.replace(m3u_tmp, m3u_path)

        return txt_path, m3u_path
