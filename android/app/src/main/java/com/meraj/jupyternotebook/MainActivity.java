package com.meraj.jupyternotebook;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.database.Cursor;
import android.provider.DocumentsContract;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
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
    private static final int DATA_FOLDER_REQUEST = 1003;
    private static final int NICECODING_TREE_REQUEST = 1004;
    private byte[] pendingDownloadBytes;
    private String pendingSaveKey;
    private String pendingSaveMime;
    private boolean pendingSaveAs;
    private boolean niceCodingSetupPromptLaunched = false;

    /** Native bridge for downloads, because Android WebView does not reliably honor
     *  HTMLAnchorElement.download for data/blob URLs. */
    public final class AndroidDownloads {
        @JavascriptInterface
        public void saveBase64Image(String filename, String mimeType, String base64Data) {
            // Image exports always ask for a destination; this avoids signature mismatch
            // with the Save/Save As bridge used by text files.
            saveBase64File(filename, mimeType, base64Data, true, filename);
        }

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
                    String workspaceName = finalKey.startsWith("python:") ? "python" : (finalKey.startsWith("web:") ? "web" : (finalKey.startsWith("sql:") ? "sqlite" : "notebook"));
                    String managedFolder = getSharedPreferences("nicecoding_storage", MODE_PRIVATE).getString("folder_" + workspaceName, null);
                    if (managedFolder != null) {
                        try {
                            Uri folderUri = Uri.parse(managedFolder);
                            if (uriText != null && !saveAs) {
                                Uri existing = Uri.parse(uriText);
                                try (OutputStream output = getContentResolver().openOutputStream(existing, "wt")) {
                                    if (output == null) throw new java.io.IOException("Cannot update existing file");
                                    output.write(decoded); output.flush();
                                }
                            } else {
                                // Save As creates a new file; if the name already exists, add _1, _2, etc.
                                // Ordinary Save updates the existing file.
                                String savedName = writeSafFile(folderUri, finalName, finalMime, decoded, !saveAs);
                                Uri treeUri = Uri.parse(getSharedPreferences("nicecoding_storage", MODE_PRIVATE).getString("tree_uri", folderUri.toString()));
                                Uri created = findChildFile(treeUri, folderUri, savedName);
                                if (created != null) {
                                    android.content.SharedPreferences.Editor edit = prefs.edit().putString(finalKey, created.toString());
                                    edit.putString(saveKeyWithFilename(finalKey, savedName), created.toString()).apply();
                                }
                                writeBytes(new File(workspaceLocalDir(workspaceName), savedName), decoded);
                                if (webView != null) webView.evaluateJavascript(
                                    "window.onNativeDownloadResult && window.onNativeDownloadResult(true, 'Saved in Downloads/NiceCoding', '" + jsSafe(savedName) + "')", null);
                                return;
                            }
                            writeBytes(new File(workspaceLocalDir(workspaceName), finalName), decoded);
                            if (webView != null) webView.evaluateJavascript("window.onNativeDownloadResult && window.onNativeDownloadResult(true, 'Saved in Downloads/NiceCoding', '" + jsSafe(finalName) + "')", null);
                            return;
                        } catch (Exception storageError) {
                            notifyJs(false, "NiceCoding storage error: " + storageError.getMessage());
                            return;
                        }
                    }
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

        @JavascriptInterface
        public void setupNiceCodingStorage() {
            handler.post(() -> {
                try {
                    Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE);
                    intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
                    intent.putExtra("android.content.extra.SHOW_ADVANCED", true);
                    startActivityForResult(intent, NICECODING_TREE_REQUEST);
                } catch (Exception e) {
                    notifyJs(false, "Cannot open Android folder picker. Please try again.");
                }
            });
        }

        @JavascriptInterface
        public boolean syncWorkspaceFiles(String workspace) {
            try {
                String name = safeWorkspace(workspace);
                File local = workspaceLocalDir(name);
                if (!local.exists() && !local.mkdirs()) return false;
                String folderText = getSharedPreferences("nicecoding_storage", MODE_PRIVATE)
                        .getString("folder_" + name, null);
                if (folderText != null) {
                    Uri folder = Uri.parse(folderText);
                    String treeText = getSharedPreferences("nicecoding_storage", MODE_PRIVATE).getString("tree_uri", null);
                    if (treeText == null) throw new java.io.IOException("NiceCoding storage permission is missing. Run Setup Downloads/NiceCoding once.");
                    Uri treeUri = Uri.parse(treeText);
                    copyTreeContents(treeUri, DocumentsContract.getDocumentId(folder), local);
                }
                Python.getInstance().getModule("jupyter").callAttr("set_workspace_dir", local.getAbsolutePath());
                return true;
            } catch (Exception e) {
                android.util.Log.e("NiceCodingStorage", "Workspace file sync failed", e);
                return false;
            }
        }

        @JavascriptInterface
        public void setActiveWorkspace(String workspace) {
            final String name = safeWorkspace(workspace);
            handler.post(() -> {
                try {
                    File local = workspaceLocalDir(name);
                    local.mkdirs();
                    String folderUri = getSharedPreferences("nicecoding_storage", MODE_PRIVATE).getString("folder_" + name, null);
                    if (folderUri != null) {
                        Uri folder = Uri.parse(folderUri);
                        String treeText = getSharedPreferences("nicecoding_storage", MODE_PRIVATE).getString("tree_uri", null);
                        if (treeText == null) throw new java.io.IOException("NiceCoding storage permission is missing");
                        copyTreeContents(Uri.parse(treeText), DocumentsContract.getDocumentId(folder), local);
                    }
                    Python.getInstance().getModule("jupyter").callAttr("set_workspace_dir", local.getAbsolutePath());
                } catch (Exception e) {
                    // Workspace switching must never crash the app if external storage was revoked.
                }
            });
        }

        @JavascriptInterface
        public void importTextFile(String filename, String mimeType, String base64Data, String workspace) {
            try {
                byte[] bytes = Base64.decode(base64Data, Base64.DEFAULT);
                String name = safeFilename(filename);
                String ws = safeWorkspace(workspace);
                handler.post(() -> {
                    try {
                        File local = workspaceLocalDir(ws); local.mkdirs();
                        writeBytes(new File(local, name), bytes);
                        String folderUri = getSharedPreferences("nicecoding_storage", MODE_PRIVATE).getString("folder_" + ws, null);
                        if (folderUri != null) writeSafFile(Uri.parse(folderUri), name, mimeType, bytes, true);
                    } catch (Exception ignored) { }
                });
            } catch (Exception ignored) { }
        }
    }

    private String safeWorkspace(String value) {
        if ("python".equals(value)) return "python";
        if ("web".equals(value)) return "web";
        if ("sqlite".equals(value)) return "sqlite";
        return "notebook";
    }

    private String safeFilename(String value) {
        String name = (value == null || value.trim().isEmpty()) ? "untitled" : value.trim();
        return name.replaceAll("[\\/:*?\"<>|]", "_");
    }

    private File workspaceLocalDir(String workspace) {
        return new File(new File(getFilesDir(), "NiceCoding"), safeWorkspace(workspace));
    }

    private void notifyJs(boolean ok, String message) {
        String safe = jsSafe(message);
        if (webView != null) webView.evaluateJavascript("window.onNativeDownloadResult && window.onNativeDownloadResult(" + ok + ", '" + safe + "')", null);
    }

    private void writeBytes(File file, byte[] bytes) throws Exception {
        File parent = file.getParentFile(); if (parent != null) parent.mkdirs();
        try (FileOutputStream out = new FileOutputStream(file)) { out.write(bytes); out.flush(); }
    }

    private Uri findOrCreateDirectory(Uri treeUri, Uri parentUri, String name) throws Exception {
        String parentId = DocumentsContract.getDocumentId(parentUri);
        Uri children = DocumentsContract.buildChildDocumentsUriUsingTree(treeUri, parentId);
        String[] cols = {DocumentsContract.Document.COLUMN_DOCUMENT_ID, DocumentsContract.Document.COLUMN_DISPLAY_NAME, DocumentsContract.Document.COLUMN_MIME_TYPE};
        try (Cursor c = getContentResolver().query(children, cols, null, null, null)) {
            if (c != null) while (c.moveToNext()) {
                if (name.equals(c.getString(1)) && DocumentsContract.Document.MIME_TYPE_DIR.equals(c.getString(2)))
                    return DocumentsContract.buildDocumentUriUsingTree(treeUri, c.getString(0));
            }
        }
        Uri created = DocumentsContract.createDocument(getContentResolver(), parentUri, DocumentsContract.Document.MIME_TYPE_DIR, name);
        if (created == null) throw new java.io.IOException("Cannot create folder " + name);
        return created;
    }

    private Uri findChildFile(Uri treeUri, Uri parentUri, String name) throws Exception {
        String parentId = DocumentsContract.getDocumentId(parentUri);
        Uri children = DocumentsContract.buildChildDocumentsUriUsingTree(treeUri, parentId);
        String[] cols = {DocumentsContract.Document.COLUMN_DOCUMENT_ID, DocumentsContract.Document.COLUMN_DISPLAY_NAME, DocumentsContract.Document.COLUMN_MIME_TYPE};
        try (Cursor c = getContentResolver().query(children, cols, null, null, null)) {
            if (c != null) while (c.moveToNext()) {
                if (name.equals(c.getString(1)) && !DocumentsContract.Document.MIME_TYPE_DIR.equals(c.getString(2)))
                    return DocumentsContract.buildDocumentUriUsingTree(treeUri, c.getString(0));
            }
        }
        return null;
    }

    private String writeSafFile(Uri folderUri, String filename, String mime, byte[] bytes, boolean replaceExisting) throws Exception {
        Uri treeUri = Uri.parse(getSharedPreferences("nicecoding_storage", MODE_PRIVATE).getString("tree_uri", folderUri.toString()));
        Uri target = findChildFile(treeUri, folderUri, filename);
        String actualName = filename;
        if (target != null && replaceExisting) {
            try (OutputStream out = getContentResolver().openOutputStream(target, "wt")) {
                if (out == null) throw new java.io.IOException("Cannot write existing file " + filename);
                out.write(bytes);
                out.flush();
            }
            return filename;
        }
        // Save As never overwrites. Keep the original extension and choose the first free _N suffix.
        if (target != null) {
            int dot = filename.lastIndexOf('.');
            String base = dot > 0 ? filename.substring(0, dot) : filename;
            String ext = dot > 0 ? filename.substring(dot) : "";
            int index = 1;
            do {
                actualName = base + "_" + index + ext;
                index++;
            } while (findChildFile(treeUri, folderUri, actualName) != null);
        }
        String type = (mime == null || mime.trim().isEmpty()) ? "application/octet-stream" : mime;
        Uri created = DocumentsContract.createDocument(getContentResolver(), folderUri, type, actualName);
        if (created == null) throw new java.io.IOException("Cannot create " + actualName);
        try (OutputStream out = getContentResolver().openOutputStream(created, "wt")) {
            if (out == null) throw new java.io.IOException("Cannot write file " + actualName);
            out.write(bytes);
            out.flush();
        }
        return actualName;
    }

    private String saveKeyWithFilename(String saveKey, String filename) {
        if (saveKey == null) return filename;
        int separator = saveKey.lastIndexOf(':');
        return separator >= 0 ? saveKey.substring(0, separator + 1) + filename : filename;
    }

    private void configureNiceCodingTree(Uri treeUri) throws Exception {
        Uri rootDoc = DocumentsContract.buildDocumentUriUsingTree(treeUri, DocumentsContract.getTreeDocumentId(treeUri));
        Uri nice = findOrCreateDirectory(treeUri, rootDoc, "NiceCoding");
        Uri notebook = findOrCreateDirectory(treeUri, nice, "Notebook");
        Uri python = findOrCreateDirectory(treeUri, nice, "Python");
        Uri web = findOrCreateDirectory(treeUri, nice, "HTML_CSS");
        Uri sql = findOrCreateDirectory(treeUri, nice, "SQL");
        android.content.SharedPreferences.Editor edit = getSharedPreferences("nicecoding_storage", MODE_PRIVATE).edit();
        edit.putString("tree_uri", treeUri.toString());
        edit.putString("folder_notebook", notebook.toString());
        edit.putString("folder_python", python.toString());
        edit.putString("folder_web", web.toString());
        edit.putString("folder_sqlite", sql.toString());
        edit.apply();
        for (String ws : new String[]{"notebook", "python", "web", "sqlite"}) {
            File local = workspaceLocalDir(ws);
            if (!local.exists()) local.mkdirs();
            Uri folder = Uri.parse(getSharedPreferences("nicecoding_storage", MODE_PRIVATE).getString("folder_" + ws, ""));
            copyTreeContents(treeUri, DocumentsContract.getDocumentId(folder), local);
        }
        Python.getInstance().getModule("jupyter").callAttr("set_workspace_dir", workspaceLocalDir("notebook").getAbsolutePath());
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
        webView.getSettings().setSupportZoom(false);
        webView.getSettings().setBuiltInZoomControls(false);
        webView.getSettings().setDisplayZoomControls(false);
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
                    // Do not retain MIME filters created from the HTML input's accept list:
                    // Android providers may otherwise hide .py or .ipynb despite type=*/*.
                    intent.removeExtra(Intent.EXTRA_MIME_TYPES);
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
                    // First launch only: ask the user to grant persistent access to Downloads.
                    // Once granted, NiceCoding/Notebook, Python and HTML_CSS are created automatically.
                    if (!niceCodingSetupPromptLaunched && getSharedPreferences("nicecoding_storage", MODE_PRIVATE)
                            .getString("tree_uri", null) == null) {
                        niceCodingSetupPromptLaunched = true;
                        handler.postDelayed(() -> {
                            if (!isFinishing() && getSharedPreferences("nicecoding_storage", MODE_PRIVATE)
                                    .getString("tree_uri", null) == null) {
                                try {
                                    Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE);
                                    intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION
                                            | Intent.FLAG_GRANT_WRITE_URI_PERMISSION
                                            | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
                                    intent.putExtra("android.content.extra.SHOW_ADVANCED", true);
                                    startActivityForResult(intent, NICECODING_TREE_REQUEST);
                                } catch (Exception e) {
                                    notifyJs(false, "Please allow Downloads folder access from File > Setup Downloads/NiceCoding.");
                                }
                            }
                        }, 650);
                    }
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
        if (requestCode == NICECODING_TREE_REQUEST) {
            if (resultCode == RESULT_OK && data != null && data.getData() != null) {
                Uri treeUri = data.getData();
                try {
                    int flags = data.getFlags() & (Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
                    try { getContentResolver().takePersistableUriPermission(treeUri, flags); } catch (Exception ignored) { }
                    configureNiceCodingTree(treeUri);
                    notifyJs(true, "Storage ready. Existing NiceCoding folders were reused; missing folders were created. Choose Downloads in the Android folder picker, not the OPPO A55 storage root.");
                } catch (Exception e) {
                    notifyJs(false, "Could not set up NiceCoding folders: " + e.getMessage());
                }
            }
            return;
        }
        if (requestCode == DATA_FOLDER_REQUEST) {
            if (resultCode == RESULT_OK && data != null && data.getData() != null) {
                Uri treeUri = data.getData();
                try {
                    int flags = data.getFlags() & (Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
                    try { getContentResolver().takePersistableUriPermission(treeUri, flags); } catch (Exception ignored) { }
                    File target = new File(getFilesDir(), "notebook_workspace");
                    if (target.exists()) deleteTree(target);
                    if (!target.mkdirs() && !target.isDirectory()) throw new java.io.IOException("Cannot create workspace folder");
                    copyTreeContents(treeUri, DocumentsContract.getTreeDocumentId(treeUri), target);
                    Python.getInstance().getModule("jupyter").callAttr("set_workspace_dir", target.getAbsolutePath());
                    if (webView != null) webView.evaluateJavascript("alert('Data folder selected. CSV and other files were copied into the app workspace.')", null);
                } catch (Exception e) {
                    if (webView != null) webView.evaluateJavascript("alert('Could not import folder: " + jsSafe(e.getMessage()) + "')", null);
                }
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

    private String jsSafe(String value) {
        if (value == null) return "unknown error";
        return value.replace("\\", "\\\\").replace("'", "\\'").replace("\n", " ").replace("\r", " ");
    }

    private void deleteTree(File file) {
        if (file.isDirectory()) {
            File[] children = file.listFiles();
            if (children != null) for (File child : children) deleteTree(child);
        }
        file.delete();
    }

    private void copyTreeContents(Uri treeUri, String parentDocumentId, File destination) throws Exception {
        Uri childrenUri = DocumentsContract.buildChildDocumentsUriUsingTree(treeUri, parentDocumentId);
        String[] columns = {DocumentsContract.Document.COLUMN_DOCUMENT_ID, DocumentsContract.Document.COLUMN_DISPLAY_NAME, DocumentsContract.Document.COLUMN_MIME_TYPE};
        try (Cursor cursor = getContentResolver().query(childrenUri, columns, null, null, null)) {
            if (cursor == null) throw new java.io.IOException("Folder provider did not return files");
            while (cursor.moveToNext()) {
                String id = cursor.getString(0);
                String name = cursor.getString(1);
                String mime = cursor.getString(2);
                if (name == null || name.equals(".") || name.equals("..")) continue;
                File output = new File(destination, name.replaceAll("[\\/:*?\"<>|]", "_"));
                if (DocumentsContract.Document.MIME_TYPE_DIR.equals(mime)) {
                    if (!output.mkdirs() && !output.isDirectory()) continue;
                    copyTreeContents(treeUri, id, output);
                } else {
                    Uri fileUri = DocumentsContract.buildDocumentUriUsingTree(treeUri, id);
                    try (InputStream in = getContentResolver().openInputStream(fileUri); FileOutputStream out = new FileOutputStream(output)) {
                        if (in == null) continue;
                        byte[] buffer = new byte[8192]; int count;
                        while ((count = in.read(buffer)) > 0) out.write(buffer, 0, count);
                    }
                }
            }
        }
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
