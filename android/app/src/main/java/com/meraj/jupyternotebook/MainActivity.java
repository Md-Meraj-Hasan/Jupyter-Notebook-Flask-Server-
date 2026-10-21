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
import android.webkit.JavascriptInterface;
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
import java.io.OutputStream;
import android.util.Base64;

public class MainActivity extends Activity {
    private WebView webView;
    private FrameLayout root;
    private TextView status;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private volatile boolean pageLoaded = false;
    private ValueCallback<Uri[]> filePathCallback;
    private static final int FILE_CHOOSER_REQUEST = 1001;
    private static final int CREATE_DOCUMENT_REQUEST = 1002;
    private byte[] pendingDownloadBytes;
    private String pendingSaveKey;
    private String pendingSaveMime;
    private boolean pendingSaveAs;

    /** Native bridge for downloads, because Android WebView does not reliably honor
     *  HTMLAnchorElement.download for data/blob URLs. */
    public final class AndroidDownloads {
        @JavascriptInterface
        public void saveBase64File(String filename, String mimeType, String base64Data,
                                   boolean saveAs, String saveKey) {
            try {
                byte[] decoded = Base64.decode(base64Data, Base64.DEFAULT);
                String safeName = (filename == null || filename.trim().isEmpty()) ? "download" : filename;
                safeName = safeName.replaceAll("[\\/:*?\"<>|]", "_");
                final String finalName = safeName;
                final String finalMime = (mimeType == null || mimeType.trim().isEmpty())
                        ? "application/octet-stream" : mimeType;
                final String finalKey = (saveKey == null || saveKey.trim().isEmpty()) ? finalName : saveKey;
                handler.post(() -> {
                    android.content.SharedPreferences prefs = getSharedPreferences("saved_file_uris", MODE_PRIVATE);
                    String uriText = saveAs ? null : prefs.getString(finalKey, null);
                    if (uriText != null) {
                        try {
                            Uri uri = Uri.parse(uriText);
                            try (OutputStream output = getContentResolver().openOutputStream(uri, "wt")) {
                                if (output == null) throw new java.io.IOException("Unable to open existing file");
                                output.write(decoded);
                                output.flush();
                            }
                            if (webView != null) webView.evaluateJavascript(
                                    "window.onNativeDownloadResult && window.onNativeDownloadResult(true, 'File updated successfully')", null);
                            return;
                        } catch (Exception writeError) {
                            // If the stored destination was removed or revoked, ask for a new one.
                        }
                    }
                    pendingDownloadBytes = decoded;
                    pendingSaveKey = finalKey;
                    pendingSaveMime = finalMime;
                    pendingSaveAs = saveAs;
                    Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT);
                    intent.addCategory(Intent.CATEGORY_OPENABLE);
                    intent.setType(finalMime);
                    intent.putExtra(Intent.EXTRA_TITLE, finalName);
                    intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
                    try {
                        startActivityForResult(intent, CREATE_DOCUMENT_REQUEST);
                    } catch (Exception e) {
                        pendingDownloadBytes = null; pendingSaveKey = null;
                        if (webView != null) webView.evaluateJavascript(
                                "window.onNativeDownloadResult && window.onNativeDownloadResult(false, 'Cannot open Save dialog')", null);
                    }
                });
            } catch (Exception e) {
                handler.post(() -> {
                    if (webView != null) webView.evaluateJavascript(
                            "window.onNativeDownloadResult && window.onNativeDownloadResult(false, 'Could not prepare file')", null);
                });
            }
        }
    }

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
        // The UI is served by the app's local Flask server. Avoid stale WebView
        // resource caching when a newly built APK contains updated HTML/CSS/JS.
        webView.getSettings().setCacheMode(android.webkit.WebSettings.LOAD_NO_CACHE);
        webView.clearCache(true);
        webView.addJavascriptInterface(new AndroidDownloads(), "AndroidDownloads");
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
                    // .ipynb is JSON content but Android document providers often expose
                    // it as application/octet-stream, so a narrow MIME filter hides it.
                    // Keep the system picker broad and let the HTML input validate extensions.
                    intent.setAction(Intent.ACTION_OPEN_DOCUMENT);
                    intent.addCategory(Intent.CATEGORY_OPENABLE);
                    intent.setType("*/*");
                    intent.putExtra(Intent.EXTRA_MIME_TYPES, new String[]{
                            "application/x-ipynb+json", "application/json", "text/plain",
                            "application/octet-stream", "text/html", "text/css"
                    });
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
        if (requestCode == CREATE_DOCUMENT_REQUEST) {
            byte[] bytes = pendingDownloadBytes;
            String saveKey = pendingSaveKey;
            pendingDownloadBytes = null;
            pendingSaveKey = null;
            if (resultCode == RESULT_OK && data != null && data.getData() != null && bytes != null) {
                Uri uri = data.getData();
                try {
                    int takeFlags = data.getFlags() & (Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
                    try { getContentResolver().takePersistableUriPermission(uri, takeFlags); } catch (Exception ignored) { }
                    try (OutputStream output = getContentResolver().openOutputStream(uri, "wt")) {
                        if (output == null) throw new java.io.IOException("Unable to open selected destination");
                        output.write(bytes);
                        output.flush();
                    }
                    if (saveKey != null) getSharedPreferences("saved_file_uris", MODE_PRIVATE).edit().putString(saveKey, uri.toString()).apply();
                    if (webView != null) webView.evaluateJavascript(
                            "window.onNativeDownloadResult && window.onNativeDownloadResult(true, 'File saved successfully')", null);
                } catch (Exception e) {
                    if (webView != null) webView.evaluateJavascript(
                            "window.onNativeDownloadResult && window.onNativeDownloadResult(false, 'Could not save file')", null);
                }
            } else if (webView != null) {
                webView.evaluateJavascript("window.onNativeDownloadResult && window.onNativeDownloadResult(false, 'Save cancelled')", null);
            }
            return;
        }
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
        if (webView == null) {
            super.onBackPressed();
            return;
        }

        // The output screen is a single-page UI, so Android's system Back button
        // must explicitly return to the Python editor instead of leaving the app.
        webView.evaluateJavascript(
            "(function(){var p=document.getElementById('coding-output-page');"
            + "if(p && getComputedStyle(p).display !== 'none' && typeof backToCodingEditor === 'function'){"
            + "backToCodingEditor(); return true;} return false;})()",
            value -> {
                if ("true".equals(value)) {
                    return;
                }
                // This app is a single-page local UI. WebView history can contain
                // transient server routes and returning through it may show a blank/start page.
                // After closing the output overlay, leave the activity only when Back is pressed
                // from the main workspace; never navigate the WebView's internal history.
                MainActivity.super.onBackPressed();
            }
        );
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
