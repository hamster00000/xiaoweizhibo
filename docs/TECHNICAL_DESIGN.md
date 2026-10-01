# 跟风直播 - MVP 技术架构与实施方案

## 一、 系统概述与技术目标

### 1.1 系统定位
本项目为电视端（以“小薇直播”等 APP 为核心宿主）提供高可用、全自动化、零广告的直播源维护与常驻订阅服务。系统充当电视软件的云端/局域网数据源引擎，负责在后台持续采集上游公网源、去噪清洗、并发测速、优选收敛，并通过固定 HTTP 订阅直链与标准文件分发给电视机顶盒。

### 1.2 核心技术目标
* **轻量化与零数据库依赖**：纯 Python 标准库 + 异步轻量网络并发，以无状态文件和内存数据流驱动，运行内存 $< 50\text{MB}$。
* **高并发与秒级探活**：支持 20~50 任务并发异步探测流媒体首包延迟，30~60 秒内完成数百条流的死链淘汰。
* **双轨高兼容导出**：严格兼容小薇直播 `#genre#` 分组 TXT 规范，并同步输出标准通用 M3U 播放列表。
* **故障自愈与缓存降级**：若上游源全网不可达，自动回退复用上一次健康源缓存，避免电视端出现列表空白。

---

## 二、 整体技术架构设计

```mermaid
flowchart TD
    subgraph Upstream [外部上游源]
        U1[GitHub 开源维护源]
        U2[公网 IPv6/IPv4 直播流]
        U3[本地自定义 txt/m3u]
    end

    subgraph CoreEngine [核心处理管道 (live_crawler)]
        direction TB
        F[Fetcher: 多源解析器] -->|原始流列表| N[Normalizer: 清洗引擎]
        N -->|剔除广告/规范台名| C[Checker: 异步测速引擎]
        C -->|延迟数据/淘汰死链| E[Exporter: 优选聚类与序列化]
    end

    subgraph Storage [持久化与缓存]
        CONF[(config.json 配置)]
        OUT_TXT[(output/live_xiaowei.txt)]
        OUT_M3U[(output/live.m3u)]
    end

    subgraph ServiceLayer [交付与分发服务 (server.py)]
        S_TXT[GET /live.txt 小薇订阅直链]
        S_M3U[GET /live.m3u 标准M3U直链]
        S_API[API: /api/status, /api/refresh]
        S_WEB[Web UI 控制台与仿真大屏]
    end

    subgraph TVClient [终端接入]
        TV1[智能电视 / 小薇直播网络自定义]
        TV2[U 盘 / 局域网离线导入]
        TV3[其他通用播放器 (TiviMate / Kodi)]
    end

    Upstream --> F
    CONF -.-> CoreEngine
    E --> OUT_TXT
    E --> OUT_M3U
    OUT_TXT --> S_TXT
    OUT_M3U --> S_M3U
    S_TXT --> TV1
    OUT_TXT --> TV2
    S_M3U --> TV3
```

---

## 三、 核心数据模型与契约规范

### 3.1 频道条目对象 (`ChannelItem`)
内存流转的核心载体，定义于 `live_crawler/normalizer.py`：
```python
class ChannelItem:
    raw_name: str       # 原始抓取到的频道名称，如 "CCTV-1 综合 [1080P 超清]"
    name: str           # 清洗归一化后的标准名称，如 "CCTV-1"
    group: str          # 归类分组，如 "央视频道"、"卫视频道"、"地方频道"
    url: str            # 流媒体播放 URL (HTTP/HTTPS/P2P)
    is_valid: bool      # 测速可用性标记 (True/False)
    latency_ms: float   # 测速首包往返延迟 (毫秒)，死链为 float('inf')
    tvg_id: str         # EPG 匹配标识符 (可选)
    tvg_logo: str       # 台标图片 URL (可选)
```

### 3.2 配置文件规格 (`config.json`)
```json
{
  "sources": [
    { "name": "Guovin_IPTV", "url": "https://.../result.m3u", "format": "m3u" },
    { "name": "fanmingming_ipv6", "url": "https://.../ipv6.m3u", "format": "m3u" }
  ],
  "checker": {
    "timeout": 3.0,
    "concurrency": 25,
    "max_retries": 1,
    "user_agent": "okhttp/3.15 XiaoWeiLive/5.0.0"
  },
  "channel_groups": [
    { "name": "央视频道", "patterns": ["^CCTV-\\d+(\\+)?$", "^CCTV-4K$", "^CCTV-8K$", "^CGTN.*"] },
    { "name": "卫视频道", "patterns": [".*卫视$"] },
    { "name": "地方频道", "patterns": [".*综合.*", ".*都市.*", ".*影视.*", ".*新闻.*"] }
  ],
  "ad_keywords": ["购物", "特惠", "商城", "导购", "测试", "广告", "专享"],
  "output": {
    "dir": "output",
    "xiaowei_txt": "live_xiaowei.txt",
    "standard_m3u": "live.m3u",
    "max_lines_per_channel": 3
  }
}
```

### 3.3 小薇直播 TXT 协议格式规范
输出格式严格遵循小薇直播官方自定义源解析器标准：
* 字符集编码：`UTF-8`（无 BOM 头，换行符 `\n`）。
* 分组格式：`<分类名称>,#genre#`。
* 频道行格式：`<标准频道名>,<直播源URL>`。
* 允许相同频道名连续出现多行，小薇直播客户端将自动将其识别为**多线路源**（按遥控器左右键可切换线路）。

---

## 四、 核心子系统与关键算法设计

### 4.1 数据抓取与解析模块 (`fetcher.py`)
1. **网络弹性获取**：
   * 发起 HTTP GET 请求时模拟 Android 机顶盒 User-Agent（如 `okhttp/3.15`），规避防爬与重定向拦截。
   * 支持文本编码自适应嗅探（优先 UTF-8，备选 GBK / GB2312）。
2. **双格式解析状态机**：
   * **M3U 解析**：正则捕获 `#EXTINF:-1 tvg-name="..." group-title="...",<频道名>`，紧随的非空行捕获为 URL。
   * **小薇 TXT 解析**：识别 `,#genre#` 作为分组切换边界；普通逗号分隔行提取名称与 URL。

### 4.2 清洗与归一化引擎 (`normalizer.py`)
1. **广告零容忍拦截算法**：
   * 采用关键词黑名单过滤，对频道名执行模式扫描。命中任一广告关键词（“购物/特惠/导购/测试”等）立即被丢弃，不进入后续计算。
2. **台标清洗与去噪（正则替换序列）**：
   * 剥离分辨率修饰符：`\b(1080[pP]|720[pP]|4[kK]|8[kK]|HD|FHD)\b` $\rightarrow$ 清空。
   * 剥离格式方括号/圆括号内容：`\[.*?\]|\(.*?\)|（.*?）` $\rightarrow$ 清空。
   * 剥离杂质后缀：“超清、高清、标清、体育赛事、综合”等。
3. **CCTV 与卫视频道标准化映射**：
   * CCTV 归一规则：`cctv[-_\s]*(4k|8k|\d+\+|\d+)` 正则匹配，提取统一转为大写标准格式 `CCTV-$1`（如 `cctv1`、`CCTV-1综合` $\rightarrow$ `CCTV-1`）。
   * 卫视归一规则：提取省份 + `卫视`（如 `湖南卫视高清` $\rightarrow$ `湖南卫视`）。
4. **分类归并**：根据 `config.json` 的 `channel_groups` 正则表，将频道精确指派到对应分组。

### 4.3 异步流媒体测速与淘汰引擎 (`checker.py`)
1. **非阻塞异步并发架构**：
   * 基于 Python 原生 `asyncio` + 协程池执行流探活，设定 `asyncio.Semaphore(concurrency)` 严格控制对外并发连接数（默认 25~30 并发），防止路由器连接数耗尽或触发源站拉黑。
2. **轻量首包探测策略 (RTT)**：
   * 第一步：优先尝试 `HTTP HEAD` 请求获取响应头及 HTTP 200/206 状态，测量客户端与源服务器的传输时延。
   * 第二步：针对部分屏蔽 HEAD 方法的 CDN，自动降级为 `Range: bytes=0-1024` 的分片 `GET` 请求，只要接收到首个媒体分片（M3U8 播放列表文本或 TS 头）即刻中断连接并记录耗时。
3. **淘汰判定逻辑**：
   * 状态码非 200/206/302，或连接超时（超过 `timeout`，默认 3.0 秒），标记 `is_valid = False`。
   * 测速完成后，直接丢弃所有无效源。

### 4.4 优选排序与双轨输出引擎 (`exporter.py`)
1. **拓扑分组与线路排序**：
   * 按 `分组名 -> 频道名` 构建双层字典。
   * 针对每个频道的多条可用线路，严格按照 `latency_ms` 升序排列。
2. **Top-K 截断算法**：
   * 截取前 $K$ 条线路（`max_lines_per_channel`，默认 2~3 条）。
   * 该机制有效解决“一个频道搜刮出 30 条源，切台卡顿 20 次”的顽疾，保证遥控器切到的都是极速活源。
3. **序列化输出**：
   * 一键写入 `output/live_xiaowei.txt`（小薇标准格式）。
   * 同步写入 `output/live.m3u`（标准扩展 M3U 格式）。

### 4.5 服务与交付子系统 (`server.py`)
采用轻量无依赖的 HTTP 守护服务：
* **路由表**：
  * `GET /`：展示静态 Web 交互控制台与运行监控。
  * `GET /live.txt`：读取 `output/live_xiaowei.txt`，返回 `text/plain; charset=utf-8`，供电视机端直接填入作为网络自定义源。
  * `GET /live.m3u`：读取 `output/live.m3u`，返回 `application/x-mpegurl; charset=utf-8`。
  * `GET /api/status`：返回 JSON 格式当前可用频道数、有效率及更新时间戳。
  * `POST /api/refresh`：异步拉起新一轮抓取与测速管线。

---

## 五、 自动化调度与可靠性设计

### 5.1 定时保活调度机制
* **本地守护模式**：在 `server.py` 内部挂载后台守护线程，支持配置定时轮询（如每 12 小时或每日凌晨 04:00 自动执行一轮探测与优选重写）。
* **CLI / Cron 模式**：通过系统 crontab 执行 `python3 run.py`，执行完毕写入文件。
* **CI/CD 模式 (GitHub Actions)**：在仓库内配置定时 Workflow，抓取后自动 commit 部署至 GitHub Pages，作为免服务器云端订阅源。

### 5.2 降级容灾机制
* **写原子性**：导出文件时采用“先写临时文件 (`.tmp`)，测速无误后原子重命名 (`os.replace`)”的方式，避免电视机恰好在写入瞬间拉取到不完整内容。
* **有效性熔断保护**：若最新一轮测速后总有效频道数低于安全阈值（如正常有 50 个台，本轮只探测到 3 个），系统发出告警并拒绝覆写旧的静态文件，确保电视端依然可以继续播放已有源。

---

## 六、 接口定义规范 (API Spec)

### 6.1 获取小薇专属直播源
* **请求**：`GET /live.txt`
* **响应头**：`Content-Type: text/plain; charset=utf-8`
* **响应体示例**：
  ```text
  央视频道,#genre#
  CCTV-1,http://111.20.10.2:8080/live/cctv1_line2.m3u8
  CCTV-1,http://111.20.10.1:8080/live/cctv1_line1.m3u8
  CCTV-5+,http://111.20.10.5:8080/live/cctv5plus.m3u8

  卫视频道,#genre#
  湖南卫视,http://222.30.10.2:8080/live/hunan_line2.m3u8
  浙江卫视,http://222.30.10.3:8080/live/zhejiang.m3u8
  ```

### 6.2 获取服务健康状态
* **请求**：`GET /api/status`
* **响应体示例**：
  ```json
  {
    "status": "ok",
    "channels_count": 8,
    "total_lines": 16,
    "last_updated": "2026-10-01 08:30:00",
    "avg_latency_ms": 22.4
  }
  ```

---

## 七、 测试与质量验收方案

| 模块 | 测试文件 | 验证范围 |
| :--- | :--- | :--- |
| **归一化引擎** | `tests/test_normalizer.py` | 验证广告关键词丢弃率（100%）、CCTV-1~17 归一、卫视前缀提取 |
| **抓取解析器** | `tests/test_fetcher.py` | 验证 M3U 与 TXT 状态机解析正确性、脏数据健壮性 |
| **测速探活** | `tests/test_checker.py` | 验证并发控制、超时剔除逻辑与延迟统计精度 |
| **导出格式** | `tests/test_exporter.py` | 验证 Top-2 截断算法、`#genre#` 格式完整性、多线路排序 |
| **Web 路由与API** | `tests/test_server.py` | 验证 `/live.txt`、`/api/status`、`/api/process` 状态码与响应体 |
| **端到端管线** | `tests/test_manager.py` | 验证整条 Manager 执行链条从输入到文件落地的完整性 |

每次迭代与代码改动均执行全量自动化单元测试：
```bash
python3 -m unittest discover tests
```
确保全量用例 100% 通过后方可进行版本提交与交付。
