package com.meraj.jupyternotebook;

import android.app.Activity;
import android.content.ContentValues;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.provider.MediaStore;
import android.util.Base64;
import android.text.TextUtils;
import android.util.Log;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;

public class MainActivity extends Activity {
    private static final String TAG = "NiceCoding";
    private static final int FILE_CHOOSER_REQUEST = 4207;
    private WebView webView;
    private ValueCallback<Uri[]> fileChooserCallback;
    private volatile String serverStartupError = "";
    private volatile boolean activityClosing = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);

        webView = new WebView(this);
        webView.setLayoutParams(new ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        setContentView(webView);

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(true);
        settings.setAllowContentAccess(true);
        settings.setSupportZoom(false);
        webView.addJavascriptInterface(new NiceCodingBridge(), "NiceCodingBridge");
        webView.setWebViewClient(new WebViewClient());
        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (fileChooserCallback != null) fileChooserCallback.onReceiveValue(null);
                fileChooserCallback = callback;
                Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                intent.setType("*/*");
                try {
                    startActivityForResult(intent, FILE_CHOOSER_REQUEST);
                } catch (Exception e) {
                    fileChooserCallback = null;
                    callback.onReceiveValue(null);
                    Toast.makeText(MainActivity.this, "Unable to open file picker", Toast.LENGTH_SHORT).show();
                }
                return true;
            }
        });

        showStatusPage("Starting NiceCoding", "Starting the embedded Python runtime and local notebook server. This can take a little while on the first launch.", false);

        try {
            if (!Python.isStarted()) Python.start(new AndroidPlatform(this));
        } catch (Throwable error) {
            serverStartupError = Log.getStackTraceString(error);
            Log.e(TAG, "Could not initialize embedded Python runtime", error);
            showStatusPage("Python runtime failed to initialize", serverStartupError, true);
            return;
        }
        Thread serverThread = new Thread(() -> {
            try {
                Log.i(TAG, "Loading android_server Python module");
                Python.getInstance().getModule("android_server").callAttr("start_server");
                Log.e(TAG, "Local server returned unexpectedly");
                serverStartupError = "The server process returned without serving requests. Check the Python startup logs.";
            } catch (Throwable error) {
                serverStartupError = Log.getStackTraceString(error);
                Log.e(TAG, "Could not start local notebook server", error);
                runOnUiThread(() -> showStatusPage("NiceCoding server failed", serverStartupError, true));
            }
        }, "nicecoding-python-server");
        serverThread.setDaemon(true);
        serverThread.start();

        Thread pageThread = new Thread(() -> {
            boolean ready = false;
            int lastStatusCode = -1;
            // Allow up to two minutes for first-start imports of scientific Python packages.
            for (int i = 0; i < 120 && !ready && !activityClosing; i++) {
                if (!serverStartupError.isEmpty()) {
                    final String errorText = serverStartupError;
                    runOnUiThread(() -> showStatusPage("NiceCoding server failed", errorText, true));
                    return;
                }
                HttpURLConnection connection = null;
                try {
                    connection = (HttpURLConnection) new URL("http://127.0.0.1:8000/").openConnection();
                    connection.setConnectTimeout(700);
                    connection.setReadTimeout(1200);
                    connection.setRequestMethod("GET");
                    lastStatusCode = connection.getResponseCode();
                    ready = lastStatusCode == 200;
                } catch (Exception ignored) {
                    // The local server may still be importing its Python modules.
                } finally {
                    if (connection != null) connection.disconnect();
                }
                if (!ready) {
                    try { Thread.sleep(500); } catch (InterruptedException interrupted) {
                        Thread.currentThread().interrupt();
                        return;
                    }
                }
            }
            final boolean serverReady = ready;
            final int responseCode = lastStatusCode;
            runOnUiThread(() -> {
                if (activityClosing || webView == null) return;
                if (serverReady) {
                    Log.i(TAG, "Local notebook server is ready; loading UI");
                    webView.loadUrl("http://127.0.0.1:8000/");
                } else if (!serverStartupError.isEmpty()) {
                    showStatusPage("NiceCoding server failed", serverStartupError, true);
                } else {
                    String details = "The local server did not return HTTP 200 within 120 seconds. Last HTTP status: " + responseCode
                            + "\n\nPlease send a screenshot of this screen and the GitHub Actions build log. The error is not hidden behind a blank white page anymore.";
                    showStatusPage("Server did not become ready", details, true);
                }
            });
        }, "nicecoding-page-loader");
        pageThread.setDaemon(true);
        pageThread.start();
    }

    private void showStatusPage(String title, String message, boolean error) {
        if (webView == null || activityClosing) return;
        String safeTitle = TextUtils.htmlEncode(title == null ? "NiceCoding" : title);
        String safeMessage = TextUtils.htmlEncode(message == null ? "No diagnostic details available." : message);
        String accent = error ? "#ff6b6b" : "#9b8cff";
        String html = "<!doctype html><html><head><meta name='viewport' content='width=device-width,initial-scale=1'>"
                + "<meta charset='utf-8'><style>body{margin:0;background:#101018;color:#f3f2fa;font:16px system-ui;padding:24px}"
                + ".card{max-width:760px;margin:8vh auto;background:#1b1b28;border:1px solid #37364b;border-radius:18px;padding:24px}"
                + "h2{color:" + accent + ";margin-top:0}p{line-height:1.55;color:#cbc9d8}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#101018;padding:14px;border-radius:10px;color:#ffd7d7;font-size:12px}"
                + ".dot{display:inline-block;width:9px;height:9px;border-radius:50%;background:" + accent + ";margin-right:8px}</style></head><body><div class='card'>"
                + "<h2><span class='dot'></span>" + safeTitle + "</h2><p>" + (error ? "Startup diagnostic:" : "Please wait while the local server starts.") + "</p>"
                + (error ? "<pre>" + safeMessage + "</pre><p>Take a screenshot of this error and send it here. Do not share passwords or private data.</p>"
                         : "<p>NiceCoding runs its Python server inside this app. The page will open automatically when the server is ready.</p>")
                + "</div></body></html>";
        webView.loadDataWithBaseURL("http://127.0.0.1:8000/", html, "text/html", "UTF-8", null);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == FILE_CHOOSER_REQUEST && fileChooserCallback != null) {
            Uri[] results = null;
            if (resultCode == RESULT_OK && data != null && data.getData() != null) results = new Uri[]{data.getData()};
            fileChooserCallback.onReceiveValue(results);
            fileChooserCallback = null;
        }
    }

    @Override
    protected void onDestroy() {
        activityClosing = true;
        if (webView != null) {
            webView.removeJavascriptInterface("NiceCodingBridge");
            webView.destroy();
        }
        super.onDestroy();
    }

    public class NiceCodingBridge {
        @JavascriptInterface
        public void saveBase64File(String filename, String base64Content, String mimeType) {
            try {
                byte[] bytes = Base64.decode(base64Content, Base64.DEFAULT);
                String safeName = filename == null ? "NiceCoding-file.txt" : new File(filename).getName();
                String mime = mimeType == null ? "application/octet-stream" : mimeType;
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                    ContentValues values = new ContentValues();
                    values.put(MediaStore.MediaColumns.DISPLAY_NAME, safeName);
                    values.put(MediaStore.MediaColumns.MIME_TYPE, mime);
                    values.put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS + "/NiceCoding");
                    values.put(MediaStore.MediaColumns.IS_PENDING, 1);
                    Uri uri = getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values);
                    if (uri == null) throw new IllegalStateException("Downloads provider returned no file URI");
                    try (OutputStream output = getContentResolver().openOutputStream(uri)) {
                        if (output == null) throw new IllegalStateException("Could not open output file");
                        output.write(bytes);
                    }
                    ContentValues done = new ContentValues();
                    done.put(MediaStore.MediaColumns.IS_PENDING, 0);
                    getContentResolver().update(uri, done, null, null);
                    runOnUiThread(() -> Toast.makeText(MainActivity.this, "Saved to Downloads/NiceCoding", Toast.LENGTH_SHORT).show());
                } else {
                    File folder = new File(getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS), "NiceCoding");
                    if (!folder.exists() && !folder.mkdirs()) throw new IllegalStateException("Could not create Downloads folder");
                    File file = new File(folder, safeName);
                    try (FileOutputStream output = new FileOutputStream(file)) { output.write(bytes); }
                    runOnUiThread(() -> Toast.makeText(MainActivity.this, "Saved in app Downloads: " + file.getAbsolutePath(), Toast.LENGTH_LONG).show());
                }
            } catch (Exception e) {
                Log.e(TAG, "File save failed", e);
                runOnUiThread(() -> Toast.makeText(MainActivity.this, "File save failed: " + e.getMessage(), Toast.LENGTH_LONG).show());
            }
        }
    }
}
