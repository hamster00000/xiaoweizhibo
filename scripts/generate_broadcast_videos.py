#!/usr/bin/env python3
"""
生成高质量轻量级电视频道模拟广播视频 (MP4 H.264 + AAC)
为前端大屏提供真正的动态电视画面（新闻演播厅、体育现场、卫视综艺舞台等）。
"""
import math
import os
import subprocess
import sys
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "web", "videos")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 字体探测
FONT_PATH = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
if not os.path.exists(FONT_PATH):
    FONT_PATH = "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"


def get_font(size: int):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except Exception:
        return ImageFont.load_default()


def generate_channel_video(
    filename: str,
    channel_title: str,
    program_title: str,
    ticker_text: str,
    theme: str,
    duration: float = 6.0,
    fps: int = 25,
    width: int = 640,
    height: int = 360
):
    out_path = os.path.join(OUTPUT_DIR, filename)
    print(f"[*] 正在生成频道仿真画面: {channel_title} -> {filename} ...")

    total_frames = int(duration * fps)

    # 启动 ffmpeg 管道
    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-pix_fmt", "rgb24",
        "-s", f"{width}x{height}",
        "-r", str(fps),
        "-i", "-",
        "-f", "lavfi",
        "-i", "sine=frequency=523:sample_rate=44100",  # C5 悦耳伴音
        "-filter_complex", "[1:a]volume=0.04[a]",
        "-map", "0:v",
        "-map", "[a]",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "veryfast",
        "-crf", "24",
        "-c:a", "aac",
        "-b:a", "64k",
        "-t", str(duration),
        out_path
    ]

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    font_title = get_font(28)
    font_sub = get_font(18)
    font_ticker = get_font(16)

    for f_idx in range(total_frames):
        t = f_idx / fps
        im = Image.new("RGB", (width, height), (10, 15, 25))
        draw = ImageDraw.Draw(im)

        # 1. 动态演播厅背景绘制
        if theme == "cctv1":
            for y in range(height):
                ratio = y / height
                r = int(8 + 12 * ratio)
                g = int(20 + 35 * ratio)
                b = int(55 + 85 * ratio)
                draw.line([(0, y), (width, y)], fill=(r, g, b))

            cx, cy = int(width * 0.75), int(height * 0.45)
            for r_ring in (70, 50, 30):
                angle = t * 1.5 + r_ring * 0.1
                rx = int(math.cos(angle) * r_ring)
                draw.ellipse([cx - r_ring, cy - r_ring * 0.6, cx + r_ring, cy + r_ring * 0.6], outline=(70, 140, 220), width=2)
                draw.ellipse([cx - abs(rx), cy - r_ring * 0.6, cx + abs(rx), cy + r_ring * 0.6], outline=(100, 180, 255), width=1)

            for i in range(5):
                bar_x = int((t * 60 + i * 140) % (width + 200)) - 100
                draw.polygon([(bar_x, 60), (bar_x + 50, 60), (bar_x - 30, height - 80), (bar_x - 80, height - 80)], fill=(30, 70, 140))

        elif theme == "sports":
            for y in range(height):
                ratio = y / height
                r = int(5 + 15 * ratio)
                g = int(45 + 75 * ratio)
                b = int(25 + 35 * ratio)
                draw.line([(0, y), (width, y)], fill=(r, g, b))

            line_x = int((t * 220) % width)
            draw.line([(line_x, 40), (line_x + 80, height - 60)], fill=(255, 255, 120), width=4)
            draw.line([(line_x - 60, 40), (line_x + 20, height - 60)], fill=(255, 180, 50), width=2)

            draw.rectangle([width // 2 - 130, 45, width // 2 + 130, 85], fill=(20, 20, 30))
            draw.rectangle([width // 2 - 130, 45, width // 2 + 130, 85], outline=(255, 215, 0), width=2)
            score_sec = int(t * 3) % 60
            draw.text((width // 2 - 110, 52), f"中国队 88 - 82 欧洲明星队  Q4 02:{59 - score_sec:02d}", fill=(255, 255, 255), font=font_sub)

        elif theme == "news":
            for y in range(height):
                ratio = y / height
                r = int(40 + 70 * ratio)
                g = int(10 + 20 * ratio)
                b = int(15 + 30 * ratio)
                draw.line([(0, y), (width, y)], fill=(r, g, b))

            cx, cy = int(width * 0.3), int(height * 0.45)
            for rad in range(20, 110, 25):
                draw.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], outline=(180, 50, 60))
            sweep_angle = t * 2.0
            sweep_x = cx + int(math.cos(sweep_angle) * 100)
            sweep_y = cy + int(math.sin(sweep_angle) * 100)
            draw.line([(cx, cy), (sweep_x, sweep_y)], fill=(255, 80, 80), width=2)

        elif theme == "hunan":
            for y in range(height):
                ratio = y / height
                r = int(120 + 80 * ratio)
                g = int(35 + 60 * ratio)
                b = int(10 + 20 * ratio)
                draw.line([(0, y), (width, y)], fill=(r, g, b))

            for i in range(4):
                beam_angle = math.sin(t * 1.8 + i * 1.2) * 0.45
                base_x = int(width * (0.2 + i * 0.2))
                end_x = int(base_x + math.tan(beam_angle) * height)
                draw.polygon([(base_x - 15, 0), (base_x + 15, 0), (end_x + 60, height), (end_x - 60, height)], fill=(255, 190, 50))

        else:
            for y in range(height):
                ratio = y / height
                r = int(10 + 20 * ratio)
                g = int(35 + 70 * ratio)
                b = int(95 + 110 * ratio)
                draw.line([(0, y), (width, y)], fill=(r, g, b))

            for i in range(5):
                offset = (t * 80 + i * 90) % (width + 100)
                draw.line([(offset, 50), (offset + 120, height - 70)], fill=(0, 230, 255), width=3)

        # 2. 顶部台标与直播角标
        draw.rectangle([18, 14, 130, 42], fill=(20, 20, 20))
        draw.text((26, 17), channel_title, fill=(255, 255, 255), font=font_sub)
        draw.rectangle([width - 80, 14, width - 18, 38], fill=(220, 38, 38))
        draw.text((width - 68, 18), "LIVE", fill=(255, 255, 255), font=get_font(13))

        # 3. 画面中央节目动态卡片
        card_w, card_h = 360, 90
        card_x = (width - card_w) // 2
        card_y = height // 2 - 35
        draw.rectangle([card_x, card_y, card_x + card_w, card_y + card_h], fill=(10, 16, 28))
        draw.rectangle([card_x, card_y, card_x + card_w, card_y + card_h], outline=(56, 189, 248), width=2)
        draw.text((card_x + 20, card_y + 16), program_title, fill=(255, 255, 255), font=font_title)
        draw.text((card_x + 20, card_y + 54), "1080P 超高清 50FPS 杜比全景声", fill=(56, 189, 248), font=font_sub)

        # 4. 底部滚动的真实滚动新闻字幕
        draw.rectangle([0, height - 36, width, height], fill=(15, 23, 42))
        draw.rectangle([0, height - 36, 95, height], fill=(37, 99, 235))
        draw.text((12, height - 28), "今日要闻", fill=(255, 255, 255), font=get_font(15))

        ticker_len = len(ticker_text) * 16
        shift_x = int(105 - (t * 70) % (ticker_len + width - 105))
        draw.text((shift_x, height - 28), ticker_text, fill=(226, 232, 240), font=font_ticker)

        proc.stdin.write(im.tobytes())

    proc.stdin.close()
    proc.wait()
    print(f"[+] 视频生成完成: {out_path} ({os.path.getsize(out_path) // 1024} KB)")


LIVE_STREAMS = {
    "cctv1.mp4": "http://38.75.136.137:98/gslb/dsdqbv/cctv1hd.m3u8?auth=test20251009",
    "cctv5.mp4": "http://38.75.136.137:98/gslb/dsdqpub/cctv5p.m3u8?auth=testpub",
    "cctv13.mp4": "http://120.76.248.139/live/bfgd/4200000067.m3u8",
    "hunan.mp4": "https://txmov2.a.kwimgs.com/bs3/video-hls/5199687338554291078_hlsb.m3u8",
    "zhejiang.mp4": "http://ali-m-l.cztv.com/channels/lantian/channel01/1080p.m3u8",
}


def capture_real_stream(url: str, out_path: str, duration: float = 8.0) -> bool:
    print(f"[*] 尝试从真实直播源获取节目电视画面: {url} -> {out_path} ...")
    cmd = [
        "ffmpeg", "-y",
        "-i", url,
        "-t", str(duration),
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-c:a", "aac",
        out_path
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=20)
        if res.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 10000:
            print(f"[+] 成功录制真实电视频道画面: {out_path} ({os.path.getsize(out_path) // 1024} KB)")
            return True
    except Exception as e:
        print(f"[!] 真实直播流录制失败: {e}，将采用备用动态广播画面")
    return False


def main():
    clips = [
        (
            "cctv1.mp4",
            "CCTV-1",
            "新闻联播 实时直播",
            "【央视综合】全国春耕备耕全面展开 经济运行回升向好 重点工程加速推进 国际交流合作稳步拓展...",
            "cctv1"
        ),
        (
            "cctv5.mp4",
            "CCTV-5+",
            "国际锦标赛 决胜局",
            "【CCTV-5+ 体育赛事】两队比分胶着 防守激烈 反击速度持续提升 精彩三分点燃全场现场观众...",
            "sports"
        ),
        (
            "cctv13.mp4",
            "CCTV-13",
            "共同关注 滚动播报",
            "【新闻直播间】各地出台稳经济促就业系列举措 科技自主创新成果涌现 气象部门发布最新出行指南...",
            "news"
        ),
        (
            "hunan.mp4",
            "湖南卫视",
            "快乐大本营 特别企划",
            "【芒果TV 卫视直播】金鹰独播剧场即将上线 明星嘉宾精彩舞台嗨翻全场 精彩游戏互动笑料不断...",
            "hunan"
        ),
        (
            "zhejiang.mp4",
            "浙江卫视",
            "奔跑吧 青春特辑",
            "【中国蓝剧场】追光少年热血向前 跑男家族再度集结 绿色中国行公益活动火热启动进行中...",
            "zhejiang"
        )
    ]

    for fname, title, prog, ticker, theme in clips:
        out_path = os.path.join(OUTPUT_DIR, fname)
        if fname in LIVE_STREAMS:
            if capture_real_stream(LIVE_STREAMS[fname], out_path):
                continue

        generate_channel_video(
            filename=fname,
            channel_title=title,
            program_title=prog,
            ticker_text=ticker,
            theme=theme,
            duration=6.0,
            fps=25,
            width=640,
            height=360
        )


if __name__ == "__main__":
    main()
