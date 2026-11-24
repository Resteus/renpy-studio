# Installation Guide — RenPy Studio (v1.0.0)

Complete setup guide for running **RenPy Studio** on Android via **Termux**—no PC, laptop, or root access required.

---

## 1. Install Termux (Android)

> **Important:** Do **not** install Termux from the Google Play Store. That version is deprecated and fails when installing current packages.

1. Download and install **Termux** (`arm64-v8a`) from **[F-Droid](https://f-droid.org/packages/com.termux/)** or the official **[Termux GitHub Releases](https://github.com/termux/termux-app/releases)**.
2. Open Termux, update all repositories, and grant shared storage permission so RenPy Studio can read your projects and save signed APKs to your Android **Downloads** folder:
~~~bash
pkg update && pkg upgrade -y
termux-setup-storage
~~~
3. Tap **Allow** when Android prompts for storage access.

---

## 2. Install System Dependencies

Install Python, OpenJDK 17, Git, Android packaging binaries (`apktool`, `aapt2`, `apksigner`, `zipalign`), and native image headers (`libjpeg-turbo`, `zlib`) required to compile Pillow on ARM64:

~~~bash
pkg install -y python openjdk-17 apktool aapt2 apksigner zipalign git curl libjpeg-turbo zlib
~~~

---

## 3. Clone RenPy Studio & Install Python Packages

1. Clone this repository into your Termux home directory:
~~~bash
git clone https://github.com/Resteus/renpy-studio.git ~/renpy-studio
cd ~/renpy-studio
~~~

2. *(Recommended)* Create and activate an isolated Python virtual environment:
~~~bash
python -m venv .venv
source .venv/bin/activate
~~~

3. Install the web server and image-resizing dependencies:
~~~bash
pip install --upgrade pip
pip install bottle waitress pillow
~~~

---

## 4. Download the Base Ren'Py 8.6.1 Engine APK

Because large 50 MB+ binary templates are excluded from Git, download the base runtime once from **[eren-coder07/RenPy-Android-Port Releases](https://github.com/eren-coder07/RenPy-Android-Port/releases)**:

1. Download **`RenPy-8.6.1-engine-android-universal-arm32-arm64.apk`** in your mobile browser (it saves to your Android `Downloads` folder).
2. Copy and rename it into `~/renpy-studio/templates/base_engine.apk`:
~~~bash
mkdir -p ~/renpy-studio/templates
cp ~/storage/downloads/RenPy-8.6.1-engine-android-universal-arm32-arm64.apk ~/renpy-studio/templates/base_engine.apk
~~~
*(On your first build, RenPy Studio automatically unpacks `base_engine.apk` into `templates/base_decoded/` and reuses that decoded template for all future builds.)*

---

## 5. Link the CLI Manager & Launch the Web UI

1. Make `renpystudio.sh` executable and link it into Termux's global `$PREFIX/bin` path:
~~~bash
chmod +x ~/renpy-studio/renpystudio.sh
ln -sf ~/renpy-studio/renpystudio.sh $PREFIX/bin/renpystudio
~~~

2. Start the background server:
~~~bash
renpystudio start
~~~

3. Open your mobile browser and go to:
~~~text
http://127.0.0.1:8070
~~~

### CLI Commands Reference
- `renpystudio` — Open interactive control menu
- `renpystudio start` — Start the Web UI server in the background
- `renpystudio stop` — Stop the server
- `renpystudio restart` — Restart the server after updates
- `renpystudio status` — Check if the server is running
- `renpystudio logs` — View recent server logs

---

## 6. Building Your First APK

1. **Load Your Project:** Import a Ren'Py 8+ `.zip` archive under **Build → Import .ZIP**, or place uncompressed project folders inside `~/storage/shared/RenPyProjects/` and pick them under **Build → RenPyProjects**.
2. **Verify App Metadata:** Review the auto-detected **App Name**, **Package ID** (must be unique per game, e.g., `com.yourname.gamename`), **Version**, and **Target API** (`36` default).
3. **Build & Install:** Tap **Build Signed APK**, then install the generated `.apk` from your **Downloads** folder or the **Builds** tab.

---

## 7. Troubleshooting

- **`pip install pillow` fails to build:** Make sure `libjpeg-turbo` and `zlib` were installed via `pkg install` before running `pip install pillow`.
- **`Base engine APK missing` error:** Confirm `~/renpy-studio/templates/base_engine.apk` exists (`ls -lh ~/renpy-studio/templates/base_engine.apk`).
- **`App not installed as package conflicts with an existing package`:** Change the **Android Package ID** to a unique value or uninstall an older APK signed with a different keystore.
- **Port `8070` already in use:** Launch on an alternate port with `RENPY_STUDIO_PORT=8075 renpystudio start`.
