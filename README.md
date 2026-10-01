# 小薇直播纯净版 (XiaoWei Live Clean Edition)

> 面向家庭电视端（以“小薇直播”等老牌电视直播软件为核心宿主）的高可用、全自动、零广告直播源维护与常驻订阅服务引擎。

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-100%25%20Passed-brightgreen.svg)]()

---

## 📺 痛点与解决思路

在给长辈或家庭智能电视配置电视直播时，传统方式往往存在以下困扰：
1. **源失效极快**：网络直播源经常几天或几小时断流，电视黑屏。
2. **垃圾广告台泛滥**：列表中充斥大量电视购物、买药、翡翠导购台，误导长辈。
3. **别名混乱重复**：一个台出现十几种名字（`CCTV1高清[1080P]`、`CCTV-1 综合`、`cctv-1`），选台困难。
4. **单台堆积几十条卡顿源**：每次换台遥控器卡死转圈。
5. **换源繁琐**：每次维护都要插拔 U 盘或找复杂局域网工具。

**本项目实现全自动“采集 -> 广告剔除 -> 台名归一 -> 毫秒测速 -> Top-K 线路精选 -> 原子双轨导出 -> 电视订阅自愈”业务闭环**：
- **0% 广告台**：严格过滤购物、特惠、商城、导购等非正常频道。
- **主流台名收敛**：规范 CCTV-1~17、4K/8K、5+ 及各大省级卫视标准名称。
- **Top 2~3 极速线路**：每个频道严格只保留响应最快的前 2~3 条活源，告别冗余。
- **一键订阅、永久保活**：电视端填入固定订阅 URL（如 `http://<局域网IP>:8088/live.txt`），服务在后台每天定时自愈重写。
- **有效性熔断保护**：若上游源全网异常，自动拒绝覆写旧文件，保障电视端正常播放。

---

## 🚀 快速开始

### 1. 安装依赖

本项目核心基于 Python 异步标准库，仅依赖轻量级 `httpx`：

```bash
git clone https://github.com/your-username/xiaoweizhibo.git
cd xiaoweizhibo
pip install -r requirements.txt
```

### 2. 启动服务与 Web 控制台

```bash
python3 server.py --port 8088
```

启动后控制台输出：
```text
[*] 小薇直播纯净版交付服务已启动:
    👉 Web 监控控制台: http://localhost:8088
    👉 小薇电视订阅源: http://localhost:8088/live.txt
    👉 通用标准 M3U 源: http://localhost:8088/live.m3u
    👉 健康状态接口: http://localhost:8088/api/status
```

打开浏览器访问 `http://localhost:8088` 即可进入 Web 原型与大屏控制台，支持模拟测速、电视画面试播与遥控器交互体验。

### 3. 单次全量命令行抓取与测速

```bash
# 正常抓取与并发测速
python3 run.py

# 快速预览（跳过网络测速，直接清洗规范化导出）
python3 run.py --dry-run
```

### 4. 终端终端管线 Demo 演示

```bash
python3 demo.py
```

---

## 📺 电视端与播放器接入方式

### 方式一：小薇直播【网络自定义】固定在线订阅（推荐 🌟）
1. 启动 `server.py`（部署在软路由、NAS、Docker 或局域网电脑）。
2. 在智能电视打开【小薇直播】。
3. 进入【设置】 -> 【自定义频道】 / 【网络自定义】。
4. 输入订阅链接：`http://<服务器IP>:8088/live.txt`。
5. 之后电视软件每次启动或刷新均会自动同步最新纯净源，免去频繁换源烦恼。

### 方式二：离线 U 盘导入
1. 将 `output/live_xiaowei.txt` 文件拷贝至 U 盘根目录。
2. 将 U 盘插入机顶盒或智能电视。
3. 打开小薇直播，根据提示完成自定义源导入。

### 方式三：通用标准 M3U 播放器（TiviMate / Kodi / VLC / PotPlayer）
- 订阅链接：`http://<服务器IP>:8088/live.m3u`
- 包含标准 `#EXTINF` 标签，附带频道名称、分类、EPG 电视指南与台标图元。

---

## 🛠️ 系统架构与处理管道

```mermaid
flowchart TD
    subgraph Upstream [外部上游多数据源]
        U1[GitHub 开源维护源]
        U2[IPv6 / IPv4 直播流]
        U3[本地自定义 txt / m3u]
    end

    subgraph Pipeline [核心清洗与优选管线]
        F[Fetcher: 多源解析器] -->|原始流候选| N[Normalizer: 清洗引擎]
        N -->|剔除广告 / 规范台名| C[Checker: 异步测速引擎]
        C -->|首包延迟 / 剔除死链| E[Exporter: 线路优选与双轨输出]
    end

    subgraph Service [交付与守护服务]
        TXT[(output/live_xiaowei.txt)] --> S_TXT[GET /live.txt]
        M3U[(output/live.m3u)] --> S_M3U[GET /live.m3u]
        STAT[(output/status.json)] --> S_API[GET /api/status]
        S_REF[POST /api/refresh] -.-> Pipeline
    end

    Upstream --> F
    E --> TXT
    E --> M3U
    E --> STAT
```

---

## 🐳 Docker 部署 (家庭 NAS / 软路由)

### 使用 Docker Compose（推荐）

```bash
docker compose up -d
```

### 使用 Docker CLI

```bash
docker build -t xiaowei-live .
docker run -d \
  --name xiaowei-live \
  --restart unless-stopped \
  -p 8088:8088 \
  -v $(pwd)/config.json:/app/config.json:ro \
  -v $(pwd)/output:/app/output \
  xiaowei-live
```

---

## ⚙️ 配置文件说明 (`config.json`)

```json
{
  "sources": [
    {
      "name": "Guovin_IPTV",
      "url": "https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/result.m3u",
      "format": "m3u"
    }
  ],
  "checker": {
    "timeout": 3.0,
    "concurrency": 25,
    "user_agent": "okhttp/3.15 XiaoWeiLive/5.0.0"
  },
  "channel_groups": [
    { "name": "央视频道", "patterns": ["^CCTV-\\d+(\\+)?$", "^CCTV-4K$", "^CCTV-8K$", "^CGTN.*"] },
    { "name": "卫视频道", "patterns": [".*卫视$"] },
    { "name": "地方频道", "patterns": [".*综合.*", ".*都市.*", ".*影视.*"] }
  ],
  "ad_keywords": ["购物", "特惠", "商城", "导购", "测试", "广告", "体验", "专享"],
  "output": {
    "dir": "output",
    "xiaowei_txt": "live_xiaowei.txt",
    "standard_m3u": "live.m3u",
    "max_lines_per_channel": 3
  },
  "min_valid_channels": 1,
  "auto_refresh_hours": 12
}
```

| 配置参数 | 说明 | 默认值 |
| :--- | :--- | :--- |
| `sources` | 聚合上游数据源列表（支持远程 URL 与本地文件） | - |
| `checker.timeout` | 单个流媒体握手首包超时时间（秒） | `3.0` |
| `checker.concurrency` | 异步探测最大并发协程数 | `25` |
| `ad_keywords` | 广告台零容忍拦截黑名单关键词 | 详见配置文件 |
| `output.max_lines_per_channel` | 每个频道最终保留的最优低延迟线路数 | `3` |
| `min_valid_channels` | 有效性熔断阈值（有效频道数低于此值拒绝覆写） | `1` |
| `auto_refresh_hours` | 本地守护模式定时轮询周期（小时） | `12` |

---

## 🧪 测试与质量验证

运行全量单元测试与端到端集成测试：

```bash
python3 -m unittest discover tests
```

测试覆盖范围：
- `test_normalizer.py`：CCTV-1~17、4K、8K、5+ 标准收敛归一与广告过滤测试。
- `test_fetcher.py`：M3U / TXT 双状态机解析与 GBK/UTF-8 自适应编码嗅探。
- `test_checker.py`：首包 HTTP HEAD 探测与分片 Range GET 降级逻辑。
- `test_exporter.py`：Top-K 排序截断、小薇 TXT 格式校验与文件原子写入。
- `test_manager.py`：全流程管线、有效性熔断保护及 `status.json` 生成。
- `test_server.py`：`/live.txt`、`/live.m3u`、`/api/status`、`/api/refresh` 交付接口。

---

## 📄 开源许可

本项目遵循 MIT 协议开源。仅供家庭学习与个人电视机顶盒日常娱乐使用。
