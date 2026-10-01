import re
from typing import Dict, List, Optional, Tuple


class ChannelNormalizer:
    """频道名称标准化、去噪与分类处理器"""

    CCTV_NAME_MAP = {
        "1": "CCTV-1",
        "2": "CCTV-2",
        "3": "CCTV-3",
        "4": "CCTV-4",
        "5": "CCTV-5",
        "5+": "CCTV-5+",
        "5PLUS": "CCTV-5+",
        "6": "CCTV-6",
        "7": "CCTV-7",
        "8": "CCTV-8",
        "9": "CCTV-9",
        "10": "CCTV-10",
        "11": "CCTV-11",
        "12": "CCTV-12",
        "13": "CCTV-13",
        "14": "CCTV-14",
        "15": "CCTV-15",
        "16": "CCTV-16",
        "17": "CCTV-17",
        "4K": "CCTV-4K",
        "8K": "CCTV-8K",
    }

    # 常见需要剥离的清晰度/冗余标签
    CLEAN_PATTERNS = [
        r"\[.*?\]",
        r"\(.*?\)",
        r"（.*?）",
        r"\b(1080[pP]|720[pP]|4[kK]|8[kK]|2[kK]|HD|FHD|UHD|SD|HEVC)\b",
        r"(超清|高清|标清|蓝光|全高清)",
        r"(综合|财经|综艺|中文国际|体育赛事|体育|电影|国防军事|军事|电视剧|纪录|科教|戏曲|社会与法|新闻|少儿|音乐|农业农村|奥林匹克)",
        r"[_\-\s]+$",
    ]

    DEFAULT_AD_KEYWORDS = [
        "购物", "特惠", "商城", "导购", "测试", "广告", "体验", "专享",
        "专卖", "优惠", "热卖", "理财", "彩票", "聚鲨"
    ]

    def __init__(self, channel_groups: Optional[List[Dict]] = None, ad_keywords: Optional[List[str]] = None):
        self.channel_groups = channel_groups or []
        kws = ad_keywords if ad_keywords is not None else self.DEFAULT_AD_KEYWORDS
        self.ad_keywords = [kw.lower() for kw in kws]

    def is_ad_channel(self, name: str) -> bool:
        """判断是否属于广告或推广频道（零容忍拦截）"""
        if not name or not name.strip():
            return True
        name_lower = name.lower()
        for kw in self.ad_keywords:
            if kw in name_lower:
                return True
        return False

    def normalize_name(self, raw_name: str) -> str:
        """对频道名称进行清洗与标准化映射"""
        if not raw_name:
            return ""

        clean_name = raw_name.strip()

        # 1. 匹配 CCTV 系列 (例如: cctv-1, CCTV1 高清, CCTV 5+ 体育赛事, CCTV-4K, CCTV5PLUS)
        cctv_match = re.search(r"cctv[-_\s]*(4k|8k|[0-9]{1,2}(?:\s*plus|\+)?|[0-9]{1,2})", clean_name, re.IGNORECASE)
        if cctv_match:
            cctv_id = cctv_match.group(1).upper().replace(" ", "").replace("PLUS", "+")
            if cctv_id in self.CCTV_NAME_MAP:
                return self.CCTV_NAME_MAP[cctv_id]
            return f"CCTV-{cctv_id}"

        # 2. 匹配 CGTN 系列
        cgtn_match = re.search(r"cgtn[-_\s]*([a-zA-Z]+)?", clean_name, re.IGNORECASE)
        if cgtn_match:
            suffix = (cgtn_match.group(1) or "").upper()
            return f"CGTN-{suffix}" if suffix else "CGTN"

        # 3. 匹配卫视系列 (例如: 湖南卫视超清, 浙江卫视 HD)
        weishi_match = re.search(r"([\u4e00-\u9fa5]{2,4}卫视)", clean_name)
        if weishi_match:
            return weishi_match.group(1)

        # 4. 其他频道的通用降噪清洗
        cleaned = clean_name
        for pattern in self.CLEAN_PATTERNS:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()

        return cleaned if cleaned else clean_name

    def match_group(self, normalized_name: str) -> str:
        """根据频道名模式匹配所属分组"""
        for group in self.channel_groups:
            group_name = group.get("name", "其他频道")
            patterns = group.get("patterns", [])
            for pat in patterns:
                if re.search(pat, normalized_name, re.IGNORECASE):
                    return group_name

        # 默认匹配规则
        if normalized_name.startswith("CCTV") or normalized_name.startswith("CGTN"):
            return "央视频道"
        if "卫视" in normalized_name:
            return "卫视频道"
        return "其他频道"

    def normalize_group(self, raw_group: str, normalized_name: str = "") -> str:
        """对原始分组名称进行标准化归并，防止央视/央视频道碎裂成不同分组"""
        raw = (raw_group or "").strip()
        if re.search(r"^(cctv|央视)", raw, re.IGNORECASE) or normalized_name.startswith("CCTV") or normalized_name.startswith("CGTN"):
            return "央视频道"
        if re.search(r"卫视", raw) or "卫视" in normalized_name:
            return "卫视频道"
        if not raw or raw in ["其他", "其它", "其他频道"]:
            return self.match_group(normalized_name)
        return raw
