"""
XiaoWei TV Live Source Crawler & Checker Engine
"""
import os

# 过滤 httpx 原生不支持的 socks:// 协议环境变量，避免代理异常
for _key in ["all_proxy", "ALL_PROXY"]:
    if os.environ.get(_key, "").startswith("socks"):
        del os.environ[_key]

__version__ = "1.0.0"
