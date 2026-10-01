package com.qingfeng.live.tv;

import android.app.Activity;
import android.content.Context;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.view.KeyEvent;
import android.view.View;
import android.view.WindowManager;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.TextView;
import android.widget.Toast;

/**
 * 清风直播 - 小米电视专属全屏遥控播放 Activity
 * 针对遥控器上下左右、确定键及全屏防休眠做了深度优化。
 */
public class MainActivity extends Activity {

    private WebView mWebView;
    private FrameLayout mContainer;
    private TextView mOsdChannelText;
    private long mLastBackPressTime = 0;

    // 默认局域网清风直播后台服务地址 (可在设置中或通过广播动态调整)
    private static final String DEFAULT_SERVER_URL = "http://192.168.0.113:8088";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // 保持屏幕常亮，禁止电视自动进入休眠省电模式
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        // 全屏沉浸模式，隐藏电视状态栏
        getWindow().getDecorView().setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                        | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                        | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                        | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                        | View.SYSTEM_UI_FLAG_FULLSCREEN
                        | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
        );

        initViews();
        setupWebView();
        loadLivePlayer();
    }

    private void initViews() {
        mContainer = new FrameLayout(this);
        mContainer.setBackgroundColor(Color.BLACK);

        mWebView = new WebView(this);
        FrameLayout.LayoutParams webParams = new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT
        );
        mContainer.addView(mWebView, webParams);

        // 电视换台 OSD 提示框
        mOsdChannelText = new TextView(this);
        mOsdChannelText.setTextColor(Color.WHITE);
        mOsdChannelText.setTextSize(24);
        mOsdChannelText.setPadding(32, 16, 32, 16);
        mOsdChannelText.setBackgroundColor(Color.parseColor("#CC111827"));
        mOsdChannelText.setVisibility(View.GONE);

        FrameLayout.LayoutParams osdParams = new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.WRAP_CONTENT,
                FrameLayout.LayoutParams.WRAP_CONTENT
        );
        osdParams.leftMargin = 48;
        osdParams.topMargin = 48;
        mContainer.addView(mOsdChannelText, osdParams);

        setContentView(mContainer);
    }

    private void setupWebView() {
        WebSettings settings = mWebView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setUseWideViewPort(true);
        settings.setLoadWithOverviewMode(true);
        settings.setCacheMode(WebSettings.LOAD_DEFAULT);

        // 注入电视遥控器交互模式标识
        settings.setUserAgentString(settings.getUserAgentString() + " QingFengTV/1.0 (Xiaomi; PatchWall; Leanback)");

        mWebView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                // 页面加载完成后自动触发全屏电视模式
                mWebView.evaluateJavascript(
                        "if(typeof toggleFullscreen === 'function'){ try{ toggleFullscreen(true); }catch(e){} }",
                        null
                );
            }
        });

        mWebView.setWebChromeClient(new WebChromeClient());
    }

    private void loadLivePlayer() {
        // 加载清风直播本地/局域网服务
        mWebView.loadUrl(DEFAULT_SERVER_URL);
    }

    /**
     * 拦截小米电视遥控器按键，实现毫秒级物理按键响应
     */
    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        switch (keyCode) {
            case KeyEvent.KEYCODE_DPAD_UP:
                // 上键：切换到上一个频道
                showOsdNotice("正在切换至上一个频道...");
                mWebView.evaluateJavascript("window.dispatchEvent(new KeyboardEvent('keydown', {'key': 'ArrowUp'}));", null);
                return true;

            case KeyEvent.KEYCODE_DPAD_DOWN:
                // 下键：切换到下一个频道
                showOsdNotice("正在切换至下一个频道...");
                mWebView.evaluateJavascript("window.dispatchEvent(new KeyboardEvent('keydown', {'key': 'ArrowDown'}));", null);
                return true;

            case KeyEvent.KEYCODE_DPAD_CENTER:
            case KeyEvent.KEYCODE_ENTER:
                // OK 确认键：呼出或关闭频道列表
                mWebView.evaluateJavascript("window.dispatchEvent(new KeyboardEvent('keydown', {'key': 'Enter'}));", null);
                return true;

            case KeyEvent.KEYCODE_MENU:
                // 菜单键：刷新或重新加载当前线路
                showOsdNotice("正在刷新直播线路...");
                mWebView.reload();
                return true;

            case KeyEvent.KEYCODE_BACK:
                // 返回键：双击退出防误触
                long currentTime = System.currentTimeMillis();
                if (currentTime - mLastBackPressTime < 2000) {
                    finish();
                } else {
                    mLastBackPressTime = currentTime;
                    Toast.makeText(this, "再按一次返回键退出清风直播", Toast.LENGTH_SHORT).show();
                }
                return true;
        }

        return super.onKeyDown(keyCode, event);
    }

    private void showOsdNotice(String text) {
        mOsdChannelText.setText(text);
        mOsdChannelText.setVisibility(View.VISIBLE);
        mOsdChannelText.removeCallbacks(mHideOsdRunnable);
        mOsdChannelText.postDelayed(mHideOsdRunnable, 2500);
    }

    private final Runnable mHideOsdRunnable = new Runnable() {
        @Override
        public void run() {
            mOsdChannelText.setVisibility(View.GONE);
        }
    };

    @Override
    protected void onDestroy() {
        if (mWebView != null) {
            mWebView.destroy();
        }
        super.onDestroy();
    }
}
