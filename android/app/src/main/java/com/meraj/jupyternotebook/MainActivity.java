package com.meraj.jupyternotebook;

import android.app.Activity;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.graphics.Color;
import android.view.View;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.ProgressBar;
import android.widget.TextView;

import com.chaquo.python.AndroidPlatform;
import com.chaquo.python.Python;

import java.net.HttpURLConnection;
import java.net.URL;

public class MainActivity extends Activity {
    private WebView webView;
    private FrameLayout root;
    private TextView status;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private volatile boolean pageLoaded = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().setStatusBarColor(Color.rgb(247, 247, 247));
        getWindow().setNavigationBarColor(Color.BLACK);

        root = new FrameLayout(this);
        webView = new WebView(this);
        status = new TextView(this);
        status.setText("Starting offline Python engine…\nPlease wait");
        status.setTextColor(Color.DKGRAY);
        status.setTextSize(17);
        status.setGravity(android.view.Gravity.CENTER);
        root.addView(webView, new FrameLayout.LayoutParams(-1, -1));
        root.addView(status, new FrameLayout.LayoutParams(-1, -1));
        setContentView(root);

        webView.getSettings().setJavaScriptEnabled(true);
        webView.getSettings().setDomStorageEnabled(true);
        webView.getSettings().setAllowFileAccess(true);
        webView.getSettings().setAllowContentAccess(true);
        webView.setOverScrollMode(View.OVER_SCROLL_NEVER);
        webView.setWebChromeClient(new WebChromeClient());
        webView.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                String host = request.getUrl().getHost();
                // Keep navigation inside the offline app; never open external websites.
                return host != null && !(host.equals("127.0.0.1") || host.equals("localhost"));
            }
            @Override public void onPageFinished(WebView view, String url) {
                if (url.startsWith("http://127.0.0.1:8000") || url.startsWith("http://localhost:8000")) {
                    pageLoaded = true;
                    status.setVisibility(View.GONE);
                    webView.setVisibility(View.VISIBLE);
                }
            }
        });
        webView.setVisibility(View.INVISIBLE);

        if (!Python.isStarted()) Python.start(new AndroidPlatform(this));
        Thread serverThread = new Thread(() -> {
            try {
                Python.getInstance().getModule("android_server").callAttr("start_server");
            } catch (Throwable t) {
                handler.post(() -> status.setText("Could not start Python engine.\n" + t.getMessage()));
            }
        }, "offline-python-server");
        serverThread.setDaemon(true);
        serverThread.start();

        Thread waitThread = new Thread(() -> {
            for (int i = 0; i < 90; i++) {
                if (isFinishing()) return;
                try {
                    HttpURLConnection c = (HttpURLConnection) new URL("http://127.0.0.1:8000/").openConnection();
                    c.setConnectTimeout(700);
                    c.setReadTimeout(700);
                    c.setRequestMethod("GET");
                    int code = c.getResponseCode();
                    c.disconnect();
                    if (code >= 200 && code < 500) {
                        handler.post(() -> webView.loadUrl("http://127.0.0.1:8000/"));
                        return;
                    }
                } catch (Exception ignored) { }
                try { Thread.sleep(500); } catch (InterruptedException e) { return; }
            }
            handler.post(() -> status.setText("Python engine did not start.\nClose and reopen the app, or check the GitHub Actions build logs."));
        }, "wait-for-python-server");
        waitThread.setDaemon(true);
        waitThread.start();
    }

    @Override public void onBackPressed() {
        if (webView != null && webView.canGoBack()) webView.goBack();
        else super.onBackPressed();
    }

    @Override protected void onDestroy() {
        if (webView != null) {
            webView.stopLoading();
            webView.destroy();
        }
        super.onDestroy();
    }
}
