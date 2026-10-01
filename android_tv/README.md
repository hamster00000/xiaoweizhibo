# 清风直播 - 小米电视 (Android TV) 专属客户端工程

> 本工程为“清风直播”配套的小米电视 / Android TV 原生客户端源码，针对电视大屏与遥控器交互深度调优。

---

## 📺 特性与适配

1. **小米电视深度适配**：
   - 适配小米 PatchWall 桌面大卡片启动图标 (`LEANBACK_LAUNCHER`)。
   - 兼容 Android 5.0 (API 21) 至 Android 14+，覆盖小米各代智能电视与电视盒子。
   - 自动保持屏幕常亮 (`FLAG_KEEP_SCREEN_ON`)，杜绝看电视期间锁屏黑屏。

2. **电视遥控器专属极速换台**：
   - **上/下键**：一键切换上一个/下一个电视频道（秒开无等待）。
   - **左/右键**：调节音量或切换当前频道的备选极速线路。
   - **OK / 确定键**：呼出半透明半屏频道列表导航。
   - **返回键**：隐藏菜单或二次确认退出应用。

3. **双模直播源**：
   - **在线自愈订阅**：默认自动发现并直连局域网清风直播后台 (`http://<IP>:8088/live.txt` 或 `/live.m3u`)。
   - **离线内置源保底**：网络断开或未开电脑时，自动回退内置的高可用 CCTV 与主流卫视源。

---

## 🔨 本地构建与打包 APK (Android Studio / Gradle)

若您在安装有 JDK 17 及 Android SDK 的开发机上，可直接构建：

```bash
cd android_tv

# 1. 编译 Release 正式版 APK
./gradlew assembleRelease

# 2. 或编译 Debug 测试版 APK
./gradlew assembleDebug
```

编译生成的 APK 将位于：`android_tv/app/build/outputs/apk/release/app-release.apk`。

---

## 🚀 预置免编译开箱即用方案

若您暂未安装 Android Studio 开发环境，项目根目录下已为您内置了直接获取/打包好并针对小米电视优化的开箱即用安装包：

```bash
# 自动生成/拉取针对小米电视优化的小薇直播纯净版 APK
python3 scripts/package_tv_app.py xiaowei

# 一键通过无线 ADB 推送安装至小米电视
./scripts/install_to_mi_tv.sh <您的小米电视IP>
```
安装包将直接生成在 `output/tv_app/QingFeng_XiaoWei_TV.apk`，也可直接复制到 U 盘插入小米电视安装。
