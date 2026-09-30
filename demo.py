#!/usr/bin/env python3
"""
小薇直播纯净版 - 直播源处理核心流程演示 (Demo)
展示从原始杂乱直播源 -> 智能过滤广告 -> 频道标准化 -> 测速优选 -> 导出小薇直播标准格式的全过程。
"""
import os
import sys
from live_crawler.normalizer import ChannelNormalizer
from live_crawler.fetcher import SourceFetcher, ChannelItem
from live_crawler.exporter import StreamExporter

# 1. 模拟一段常见的原始杂乱直播源文本 (含广告、清晰度后缀、重复源、乱序等)
SAMPLE_RAW_SOURCES = """
#EXTM3U x-tvg-url="https://live.fanmingming.com/e.xml"
#EXTINF:-1 tvg-name="CCTV1" tvg-logo="https://live.fanmingming.com/tv/CCTV1.png" group-title="央视频道",CCTV-1 综合 [1080P]
http://111.20.10.1:8080/live/cctv1_line1.m3u8
#EXTINF:-1 tvg-name="CCTV1" group-title="央视",CCTV1 高清
http://111.20.10.2:8080/live/cctv1_line2.m3u8
#EXTINF:-1 tvg-name="CCTV1" group-title="央视",cctv-1
http://111.20.10.1:8080/live/cctv1_line1.m3u8
#EXTINF:-1 group-title="购物频道",天天电视特惠购物
http://111.20.10.9:8080/live/ad_shopping.m3u8
#EXTINF:-1 tvg-name="CCTV5+" group-title="央视",cctv 5+ 体育赛事 超清
http://111.20.10.5:8080/live/cctv5plus.m3u8
#EXTINF:-1 tvg-name="湖南卫视" group-title="卫视",湖南卫视 HD [4K测试]
http://222.30.10.1:8080/live/hunan_line1.m3u8
#EXTINF:-1 tvg-name="湖南卫视" group-title="卫视",湖南卫视 (超清)
http://222.30.10.2:8080/live/hunan_line2.m3u8
#EXTINF:-1 tvg-name="浙江卫视" group-title="卫视",浙江卫视 1080P
http://222.30.10.3:8080/live/zhejiang.m3u8
#EXTINF:-1 group-title="其他",家庭特惠导购
http://111.20.10.8:8080/live/shop2.m3u8
"""


def run_demo():
    print("=" * 65)
    print("      小薇直播纯净版 - 直播源清洗与转换管线 Demo 演示")
    print("=" * 65)

    # 步骤一：解析原始源并智能过滤广告
    print("\n【步骤 1】解析原始直播源并过滤广告台...")
    normalizer = ChannelNormalizer()
    fetcher = SourceFetcher(normalizer=normalizer)
    raw_items = fetcher.parse_m3u(SAMPLE_RAW_SOURCES, source_name="SampleDemo")

    print(f"-> 原始输入包含 9 条记录，经广告关键词过滤后提取出 {len(raw_items)} 条有效频道候选：")
    for item in raw_items:
        print(f"   [提取] 原始名称: {item.raw_name:<20} => 标准化名称: {item.name:<10} | 分组: {item.group}")

    # 步骤二：模拟多线路网络测速 (设定不同线路响应延迟并过滤失效源)
    print("\n【步骤 2】模拟流媒体测速与可用性探测...")
    # 模拟探测得到的延迟 (ms)
    mock_latencies = {
        "http://111.20.10.1:8080/live/cctv1_line1.m3u8": 45.2,   # 线路1延迟 45ms
        "http://111.20.10.2:8080/live/cctv1_line2.m3u8": 12.8,   # 线路2延迟 12ms (更优)
        "http://111.20.10.5:8080/live/cctv5plus.m3u8": 28.4,
        "http://222.30.10.1:8080/live/hunan_line1.m3u8": 15.6,   # 湖南线路1
        "http://222.30.10.2:8080/live/hunan_line2.m3u8": 88.0,   # 湖南线路2
        "http://222.30.10.3:8080/live/zhejiang.m3u8": 32.1,
    }

    for item in raw_items:
        if item.url in mock_latencies:
            item.latency_ms = mock_latencies[item.url]
            item.is_valid = True
            print(f"   [测速] 频道: {item.name:<10} 线路: {item.url} -> 响应延迟: {item.latency_ms} ms (可用)")

    # 步骤三：去重、按测速延迟优选排序
    print("\n【步骤 3】去重合并、优选最快线路...")
    exporter = StreamExporter(max_lines_per_channel=2)
    grouped = exporter.deduplicate_and_rank(raw_items)

    for group, channels in grouped.items():
        print(f"   分组 [{group}]:")
        for ch_name, lines in channels.items():
            best_info = ", ".join([f"{l.url} ({l.latency_ms}ms)" for l in lines])
            print(f"     * {ch_name}: 已优选保留 {len(lines)} 条最快线路: {best_info}")

    # 步骤四：导出为小薇直播纯净版专用 TXT 格式
    print("\n【步骤 4】导出为小薇直播专用 TXT 文件 (分类 #genre# 格式)...")
    xiaowei_txt = exporter.export_xiaowei_txt(grouped)
    
    # 保存到 output/demo_xiaowei.txt
    demo_output_dir = "output"
    os.makedirs(demo_output_dir, exist_ok=True)
    demo_txt_file = os.path.join(demo_output_dir, "demo_xiaowei.txt")
    with open(demo_txt_file, "w", encoding="utf-8") as f:
        f.write(xiaowei_txt)

    print("-" * 50)
    print("【小薇直播 live_xiaowei.txt 文件内容预览】:")
    print("-" * 50)
    print(xiaowei_txt.strip())
    print("-" * 50)
    print(f"演示输出文件已保存至: {os.path.abspath(demo_txt_file)}")
    print("可以直接复制该文件内容导入小薇直播或通过局域网上传使用！")
    print("=" * 65)


if __name__ == "__main__":
    run_demo()
