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

        if (!Python.isStarted()) Python.start(new AndroidPlatform(this));
        Thread serverThread = new Thread(() -> {
            try {
                Python.getInstance().getModule("android_server").callAttr("start_server");
            } catch (Throwable error) {
                Log.e(TAG, "Could not start local notebook server", error);
                runOnUiThread(() -> Toast.makeText(MainActivity.this, "NiceCoding server failed to start. Check bundled Python packages.", Toast.LENGTH_LONG).show());
            }
        }, "nicecoding-python-server");
        serverThread.setDaemon(true);
        serverThread.start();

        Thread pageThread = new Thread(() -> {
            boolean ready = false;
            for (int i = 0; i < 100 && !ready; i++) {
                HttpURLConnection connection = null;
                try {
                    connection = (HttpURLConnection) new URL("http://127.0.0.1:8000/").openConnection();
                    connection.setConnectTimeout(500);
                    connection.setReadTimeout(500);
                    connection.setRequestMethod("GET");
                    ready = connection.getResponseCode() == 200;
                } catch (Exception ignored) {
                    try { Thread.sleep(250); } catch (InterruptedException interrupted) { Thread.currentThread().interrupt(); return; }
                } finally {
                    if (connection != null) connection.disconnect();
                }
            }
            final boolean serverReady = ready;
            runOnUiThread(() -> {
                if (serverReady) webView.loadUrl("http://127.0.0.1:8000/");
                else Toast.makeText(MainActivity.this, "NiceCoding server did not start. Please check the APK build logs.", Toast.LENGTH_LONG).show();
            });
        }, "nicecoding-page-loader");
        pageThread.setDaemon(true);
        pageThread.start();
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
