package com.t2.lounge

import android.annotation.SuppressLint
import android.app.AlertDialog
import android.content.Intent
import android.graphics.Color
import android.graphics.Rect
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.text.InputType
import android.view.Gravity
import android.view.HapticFeedbackConstants
import android.view.View
import android.webkit.CookieManager
import android.webkit.JavascriptInterface
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.activity.addCallback
import androidx.core.view.ViewCompat
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import androidx.credentials.CredentialManager
import androidx.credentials.CustomCredential
import androidx.credentials.GetCredentialRequest
import androidx.credentials.exceptions.GetCredentialCancellationException
import androidx.credentials.exceptions.GetCredentialException
import androidx.credentials.exceptions.NoCredentialException
import androidx.lifecycle.lifecycleScope
import com.google.android.libraries.identity.googleid.GetGoogleIdOption
import com.google.android.libraries.identity.googleid.GoogleIdTokenCredential
import kotlinx.coroutines.launch
import org.json.JSONObject

/**
 * The whole app is the T2 web lounge in a full-screen WebView (no address bar, no system bars).
 * Google sign-in runs natively (Google blocks it inside WebViews) and the ID token is handed
 * to the login page through window.t2SignIn(token).
 */
class MainActivity : ComponentActivity() {
    private lateinit var web: WebView
    private lateinit var offline: LinearLayout
    private lateinit var offlineText: TextView
    private var failed = false

    private val prefs by lazy { getSharedPreferences("t2", MODE_PRIVATE) }
    private val serverUrl: String get() = prefs.getString("server", null) ?: BuildConfig.SERVER_URL

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, false)
        hideSystemBars()

        val bg = Color.parseColor("#071E22")
        val root = FrameLayout(this).apply { setBackgroundColor(bg) }
        web = WebView(this).apply { setBackgroundColor(bg) }
        root.addView(web, FrameLayout.LayoutParams(-1, -1))
        // 게임 화면은 왼쪽 가장자리를 끌어 순위 창을 연다. 그 구간(화면 가운데 높이 200dp, 폭 32dp)에서는
        // 안드로이드의 '뒤로 가기' 끌기를 막는다. 안드로이드가 허용하는 한 변의 최대가 200dp 다.
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            web.addOnLayoutChangeListener { v, _, _, _, _, _, _, _, _ ->
                val dp = resources.displayMetrics.density
                val h = (200 * dp).toInt()
                val top = ((v.height - h) / 2).coerceAtLeast(0)
                v.systemGestureExclusionRects = listOf(Rect(0, top, (32 * dp).toInt(), top + h))
            }
        }
        offline = buildOfflineView()
        root.addView(offline, FrameLayout.LayoutParams(-1, -1))
        setContentView(root)
        // keep inputs above the keyboard (bars are hidden, so only the keyboard pushes the page up)
        ViewCompat.setOnApplyWindowInsetsListener(root) { v, insets ->
            v.setPadding(0, 0, 0, insets.getInsets(WindowInsetsCompat.Type.ime()).bottom)
            insets
        }

        CookieManager.getInstance().setAcceptCookie(true)
        web.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            mediaPlaybackRequiresUserGesture = false
            userAgentString = "$userAgentString T2App/${BuildConfig.VERSION_NAME}"
        }
        web.addJavascriptInterface(Bridge(), "T2App")
        web.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                val url = request.url
                val home = Uri.parse(serverUrl)
                if (url.host == home.host && url.port == home.port) return false
                // anything outside our server opens in the phone's browser
                runCatching { startActivity(Intent(Intent.ACTION_VIEW, url)) }
                return true
            }

            override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
                if (request.isForMainFrame) showOffline(error.description?.toString() ?: "")
            }

            override fun onPageFinished(view: WebView, url: String) {
                if (!failed) offline.visibility = View.GONE
            }
        }
        onBackPressedDispatcher.addCallback(this) {
            if (web.canGoBack()) web.goBack() else finish()
        }

        if (savedInstanceState == null) load() else web.restoreState(savedInstanceState)
    }

    private fun load() {
        failed = false
        web.loadUrl(serverUrl)
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        web.saveState(outState)
    }

    override fun onPause() {
        super.onPause()
        CookieManager.getInstance().flush()
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        if (hasFocus) hideSystemBars()
    }

    private fun hideSystemBars() {
        WindowInsetsControllerCompat(window, window.decorView).apply {
            hide(WindowInsetsCompat.Type.systemBars())
            systemBarsBehavior = WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        }
    }

    // ---- connection lost screen

    private fun buildOfflineView(): LinearLayout {
        val gold = Color.parseColor("#F4D38E")
        val box = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setBackgroundColor(Color.parseColor("#071E22"))
            setPadding(64, 0, 64, 0)
            visibility = View.GONE
        }
        box.addView(TextView(this).apply {
            text = "♠ T2"
            textSize = 44f
            setTextColor(Color.parseColor("#FFE1A4"))
            setTypeface(typeface, android.graphics.Typeface.BOLD_ITALIC)
            gravity = Gravity.CENTER
        })
        offlineText = TextView(this).apply {
            textSize = 15f
            setTextColor(Color.parseColor("#C5D6D0"))
            gravity = Gravity.CENTER
            setPadding(0, 40, 0, 40)
        }
        box.addView(offlineText)
        box.addView(Button(this).apply {
            text = "다시 연결"
            setTextColor(Color.parseColor("#17201B"))
            setBackgroundColor(gold)
            setOnClickListener { load() }
        }, LinearLayout.LayoutParams(-1, -2))
        box.addView(Button(this).apply {
            text = "서버 주소 바꾸기"
            setTextColor(gold)
            setBackgroundColor(Color.TRANSPARENT)
            setOnClickListener { askServer() }
        }, LinearLayout.LayoutParams(-1, -2))
        return box
    }

    private fun showOffline(reason: String) {
        failed = true
        offlineText.text = "서버에 연결할 수 없습니다.\n$serverUrl\n$reason"
        offline.visibility = View.VISIBLE
    }

    private fun askServer() {
        val input = EditText(this).apply {
            setText(serverUrl)
            inputType = InputType.TYPE_TEXT_VARIATION_URI
            setSingleLine()
        }
        AlertDialog.Builder(this)
            .setTitle("서버 주소")
            .setView(input)
            .setPositiveButton("저장") { _, _ ->
                val v = input.text.toString().trim().trimEnd('/')
                prefs.edit().apply { if (v.isEmpty()) remove("server") else putString("server", v) }.apply()
                load()
            }
            .setNeutralButton("기본값") { _, _ ->
                prefs.edit().remove("server").apply()
                load()
            }
            .setNegativeButton("취소", null)
            .show()
    }

    // ---- Google sign-in, called from the login page

    inner class Bridge {
        @JavascriptInterface
        fun signIn() = runOnUiThread { googleSignIn() }

        // 버튼을 누를 때 살짝 진동(키보드 터치 피드백). 권한이 필요 없고, 휴대폰의
        // '터치 시 진동' 설정을 따른다. 웹(press.js)이 버튼 pointerdown 때 부른다.
        @JavascriptInterface
        fun tap() = runOnUiThread { web.performHapticFeedback(HapticFeedbackConstants.KEYBOARD_TAP) }
    }

    private fun googleSignIn() {
        if (BuildConfig.WEB_CLIENT_ID.isEmpty()) return signInError("구글 로그인이 아직 설정되지 않았습니다")
        val option = GetGoogleIdOption.Builder()
            .setServerClientId(BuildConfig.WEB_CLIENT_ID)
            .setFilterByAuthorizedAccounts(false)
            .build()
        val request = GetCredentialRequest.Builder().addCredentialOption(option).build()
        lifecycleScope.launch {
            try {
                val credential = CredentialManager.create(this@MainActivity)
                    .getCredential(this@MainActivity, request).credential
                if (credential is CustomCredential &&
                    credential.type == GoogleIdTokenCredential.TYPE_GOOGLE_ID_TOKEN_CREDENTIAL
                ) {
                    val token = GoogleIdTokenCredential.createFrom(credential.data).idToken
                    web.evaluateJavascript("window.t2SignIn(${JSONObject.quote(token)})", null)
                } else {
                    signInError("구글 계정을 가져오지 못했습니다")
                }
            } catch (e: GetCredentialCancellationException) {
                signInError("로그인을 취소했습니다")
            } catch (e: NoCredentialException) {
                signInError("이 폰에 구글 계정이 없습니다. 설정에서 구글 계정을 추가해 주세요")
            } catch (e: GetCredentialException) {
                signInError("구글 로그인 실패: ${e.message ?: e.type}")
            }
        }
    }

    private fun signInError(message: String) {
        web.evaluateJavascript("window.t2SignInError && window.t2SignInError(${JSONObject.quote(message)})", null)
    }
}
