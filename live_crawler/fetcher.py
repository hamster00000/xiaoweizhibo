import os
import re
from dataclasses import dataclass
from typing import List, Optional
import httpx
from live_crawler.normalizer import ChannelNormalizer


@dataclass
class ChannelItem:
    """直播源频道条目对象 (契合技术设计 3.1 规范)"""
    raw_name: str
    name: str
    url: str
    group: str
    tvg_id: str = ""
    tvg_logo: str = ""
    latency_ms: Optional[float] = None
    is_valid: bool = False
    source_origin: str = ""

    def __init__(
        self,
        raw_name: str,
        name: str,
        url: str,
        group: str,
        tvg_id: str = "",
        tvg_logo: str = "",
        logo: str = "",
        latency_ms: Optional[float] = None,
        is_valid: bool = False,
        source_origin: str = ""
    ):
        self.raw_name = raw_name
        self.name = name
        self.url = url
        self.group = group
        self.tvg_id = tvg_id
        # 兼容 logo 与 tvg_logo
        self.tvg_logo = tvg_logo or logo
        self.latency_ms = latency_ms
        self.is_valid = is_valid
        self.source_origin = source_origin

    @property
    def logo(self) -> str:
        return self.tvg_logo

    @logo.setter
    def logo(self, val: str):
        self.tvg_logo = val


def decode_bytes_adaptive(raw_bytes: bytes) -> str:
    """自适应多编码嗅探解码 (UTF-8 优先，GB18030/GBK 备选)"""
    for enc in ("utf-8-sig", "utf-8", "gb18030", "gbk", "big5"):
        try:
            return raw_bytes.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw_bytes.decode("utf-8", errors="replace")


class SourceFetcher:
    """直播源获取与多格式解析器"""

    def __init__(self, normalizer: Optional[ChannelNormalizer] = None, user_agent: str = "okhttp/3.15 XiaoWeiLive/5.0.0"):
        self.normalizer = normalizer or ChannelNormalizer()
        self.user_agent = user_agent

    def fetch_text(self, source_path_or_url: str, timeout: float = 10.0) -> str:
        """从 URL 或本地路径自适应读取源内容"""
        if source_path_or_url.startswith(("http://", "https://")):
            headers = {"User-Agent": self.user_agent}
            with httpx.Client(timeout=timeout, verify=False, follow_redirects=True) as client:
                resp = client.get(source_path_or_url, headers=headers)
                resp.raise_for_status()
                return decode_bytes_adaptive(resp.content)
        else:
            local_path = source_path_or_url.replace("file://", "")
            if not os.path.exists(local_path):
                raise FileNotFoundError(f"Local source file not found: {local_path}")
            with open(local_path, "rb") as f:
                raw_bytes = f.read()
                return decode_bytes_adaptive(raw_bytes)

    def parse_m3u(self, content: str, source_name: str = "") -> List[ChannelItem]:
        """解析 M3U / M3U8 格式内容"""
        items: List[ChannelItem] = []
        lines = [line.strip() for line in content.splitlines() if line.strip()]

        current_extinf = None
        for line in lines:
            if line.startswith("#EXTINF"):
                current_extinf = line
            elif line.startswith("#"):
                continue
            elif current_extinf and (
                line.startswith("http://") or
                line.startswith("https://") or
                line.startswith("rtmp://") or
                line.startswith("rtp://") or
                line.startswith("p2p://")
            ):
                url = line
                # 解析 EXTINF 参数
                tvg_id_match = re.search(r'tvg-id="([^"]*)"', current_extinf)
                tvg_name_match = re.search(r'tvg-name="([^"]*)"', current_extinf)
                tvg_logo_match = re.search(r'tvg-logo="([^"]*)"', current_extinf)
                group_match = re.search(r'group-title="([^"]*)"', current_extinf)

                # 频道名称通常在逗号后
                comma_idx = current_extinf.rfind(",")
                raw_name = ""
                if comma_idx != -1:
                    raw_name = current_extinf[comma_idx + 1:].strip()
                if not raw_name and tvg_name_match:
                    raw_name = tvg_name_match.group(1).strip()

                if raw_name and not self.normalizer.is_ad_channel(raw_name):
                    norm_name = self.normalizer.normalize_name(raw_name)
                    raw_grp = group_match.group(1).strip() if group_match else ""
                    group = self.normalizer.normalize_group(raw_grp, norm_name)
                    logo = tvg_logo_match.group(1).strip() if tvg_logo_match else ""
                    tvg_id = tvg_id_match.group(1).strip() if tvg_id_match else ""

                    items.append(ChannelItem(
                        raw_name=raw_name,
                        name=norm_name,
                        url=url,
                        group=group,
                        tvg_id=tvg_id,
                        tvg_logo=logo,
                        source_origin=source_name
                    ))
                current_extinf = None

        return items

    def parse_txt(self, content: str, source_name: str = "") -> List[ChannelItem]:
        """解析小薇 / DIYP 风格的 TXT 直播源格式"""
        items: List[ChannelItem] = []
        current_group = "其他频道"
        lines = [line.strip() for line in content.splitlines() if line.strip()]

        for line in lines:
            # 判断分组标记: 分组名,#genre#
            if "#genre#" in line:
                parts = line.split(",")
                current_group = parts[0].strip()
                continue

            if "," in line:
                parts = line.split(",", 1)
                raw_name = parts[0].strip()
                url = parts[1].strip()

                if not raw_name or not url or self.normalizer.is_ad_channel(raw_name):
                    continue

                norm_name = self.normalizer.normalize_name(raw_name)
                group = self.normalizer.normalize_group(current_group, norm_name)

                items.append(ChannelItem(
                    raw_name=raw_name,
                    name=norm_name,
                    url=url,
                    group=group,
                    source_origin=source_name
                ))

        return items

    def parse(self, content: str, format_hint: str = "auto", source_name: str = "") -> List[ChannelItem]:
        """根据内容或格式提示统一解析"""
        if format_hint == "m3u" or "#EXTINF" in content or "#EXTM3U" in content:
            return self.parse_m3u(content, source_name)
        return self.parse_txt(content, source_name)
