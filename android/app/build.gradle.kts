plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// Server address and Google web client ID come from the build (GitHub repository variables).
fun setting(name: String, fallback: String) = (System.getenv(name) ?: "").ifBlank { fallback }
val keystore = System.getenv("T2_KEYSTORE")

android {
    namespace = "com.t2.lounge"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.t2.lounge"
        minSdk = 26
        targetSdk = 35
        versionCode = setting("GITHUB_RUN_NUMBER", "1").toInt()
        versionName = "0.1." + setting("GITHUB_RUN_NUMBER", "0")
        buildConfigField("String", "SERVER_URL", "\"" + setting("T2_SERVER_URL", "http://127.0.0.1:8080") + "\"")
        buildConfigField("String", "WEB_CLIENT_ID", "\"" + setting("T2_WEB_CLIENT_ID", "") + "\"")
    }

    signingConfigs {
        if (keystore != null) {
            create("t2") {
                storeFile = file(keystore)
                storePassword = System.getenv("T2_KEYSTORE_PASSWORD")
                keyAlias = "t2"
                keyPassword = System.getenv("T2_KEYSTORE_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.findByName("t2") ?: signingConfigs.getByName("debug")
        }
    }
    buildFeatures { buildConfig = true }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.activity:activity-ktx:1.9.3")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    implementation("androidx.credentials:credentials:1.3.0")
    implementation("androidx.credentials:credentials-play-services-auth:1.3.0")
    implementation("com.google.android.libraries.identity.googleid:googleid:1.1.1")
}
