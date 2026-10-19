package com.meraj.jupyternotebook;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.graphics.Color;
import android.view.View;
import android.webkit.WebChromeClient;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient.FileChooserParams;
import android.webkit.WebResourceRequest;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.ProgressBar;
import android.widget.TextView;

import com.chaquo.python.android.AndroidPlatform;
import com.chaquo.python.Python;

import java.net.HttpURLConnection;
import java.net.URL;

public class MainActivity extends Activity {
    private WebView webView;
    private FrameLayout root;
    private TextView status;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private volatile boolean pageLoaded = false;
    private ValueCallback<Uri[]> filePathCallback;
    private static final int FILE_CHOOSER_REQUEST = 1001;

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
        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback,
                                             FileChooserParams fileChooserParams) {
                // Android WebView does not open the system file picker unless this callback
                // is implemented by the native Activity.
                if (filePathCallback != null) {
                    filePathCallback.onReceiveValue(null);
                }
                filePathCallback = callback;
                try {
                    Intent intent = fileChooserParams.createIntent();
                    startActivityForResult(intent, FILE_CHOOSER_REQUEST);
                    return true;
                } catch (Exception e) {
                    filePathCallback = null;
                    callback.onReceiveValue(null);
                    handler.post(() -> status.setText("Unable to open file picker. Please try again."));
                    return false;
                }
            }
        });
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

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        if (requestCode == FILE_CHOOSER_REQUEST) {
            if (filePathCallback != null) {
                Uri[] results = null;
                if (resultCode == RESULT_OK && data != null) {
                    Uri uri = data.getData();
                    if (uri != null) results = new Uri[]{uri};
                    else if (data.getClipData() != null) {
                        int count = data.getClipData().getItemCount();
                        results = new Uri[count];
                        for (int i = 0; i < count; i++) {
                            results[i] = data.getClipData().getItemAt(i).getUri();
                        }
                    }
                }
                filePathCallback.onReceiveValue(results);
                filePathCallback = null;
            }
            return;
        }
        super.onActivityResult(requestCode, resultCode, data);
    }

    @Override public void onBackPressed() {
        if (webView != null && webView.canGoBack()) webView.goBack();
        else super.onBackPressed();
    }

    @Override protected void onDestroy() {
        if (filePathCallback != null) {
            filePathCallback.onReceiveValue(null);
            filePathCallback = null;
        }
        if (webView != null) {
            webView.stopLoading();
            webView.destroy();
        }
        super.onDestroy();
    }
}
