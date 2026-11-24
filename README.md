# RenPy Studio (v1.0.0)

**RenPy Studio** is a standalone, on-device Android APK packager for Ren'Py visual novels built to run entirely inside **Termux** on Android—no PC, laptop, Gradle, or desktop Ren'Py SDK required.

> **Project Origin:** This entire tool—from the Python build pipeline and Bottle/Waitress backend to the mobile Web UI and CLI manager—was engineered 100% on an Android smartphone without a PC, built collaboratively in Termux using **Gemini Hydrogen High**.

---

## How It Works

Instead of compiling heavy C++/Java engine source code from scratch, RenPy Studio packages your visual novel around a pre-compiled ARM64/ARM32 Ren'Py 8.6.1 runtime template:

1. **Project Inspection & Metadata Parsing:** Accepts either a `.zip` archive (full project folder or `game/` directory) or an uncompressed folder in `~/storage/shared/RenPyProjects`. Automatically reads `options.rpy` to populate `config.name`, `config.version`, numeric `versionCode`, and a sanitized Android Package ID.
2. **Base Runtime Cloning:** Uses `apktool` once to decode `templates/base_engine.apk` into `templates/base_decoded/`, then clones that clean template into an isolated temporary workspace for every build.
3. **Ren'Py `x-` Asset Bundling:** Walks your project's `game/` folder and copies all scripts, images, audio, and fonts into `assets/x-game/` with the `x-` filename prefix required by Ren'Py's Android asset loader—automatically stripping `cache/`, `saves/`, `.bak`, and `.pyc` clutter.
4. **Manifest, SDK & Icon Patching:**
   - Rewrites all `org.renpy.engine` package names and provider authorities (including `androidx-startup`) in `AndroidManifest.xml` so multiple packaged games install side-by-side without package conflicts.
   - Patches `res/values/strings.xml`, `assets/x-android.json`, screen orientation, `minSdkVersion`, and `targetSdkVersion` (`36`, `37`, `38+`).
   - Restores the native **Quit** button inside the in-game mobile menu (`x-screens.rpy`).
   - Resizes optional PNG/JPG icons across all `mipmap-*` densities and adaptive foreground/background layers using Pillow.
5. **Repackaging, Alignment & Signing:** Rebuilds resources with `apktool` + `aapt2`, aligns 4-byte boundaries with `zipalign`, signs with `apksigner` using your `.jks` keystore, and outputs timestamped APKs (`<AppName>-v<Version>-<YYYYMMDD_HHMMSS>-signed.apk`) so previous versions remain available for rollback.

### Why a Universal Player APK Works as a Template
On its own, [`eren-coder07/RenPy-Android-Port`](https://github.com/eren-coder07/RenPy-Android-Port) is a standalone universal Ren'Py launcher that runs loose project folders on Android. RenPy Studio repurposes that APK as a hollow, pre-compiled engine shell:
- **Native Binaries Stay Untouched:** The ARM64/ARM32 C++ libraries (`lib/`), SDL2 Java launcher (`classes.dex`), and Python 3 Ren'Py runtime (`assets/x-renpy/`) are already compiled—eliminating any need for a PC, Android NDK, or Gradle.
- **Swap & Re-Brand Only:** RenPy Studio decodes the APK once (`templates/base_decoded/`), swaps your visual novel's files into `assets/x-game/`, rewrites the Package ID, app name, and icons, and re-signs it into an independent standalone APK.

---

## Features (v1.0.0)

- **3-Tab Mobile Web UI (`http://127.0.0.1:8070`):** Touch-friendly dark interface with **Build**, **Keystore**, and **Builds** tabs.
- **Future-Proof API Target Controls:** Set any `Minimum API` or `Target API` (`36`, `37`, `38+`) directly in the UI without downloading extra Android SDKs.
- **Built-In Keystore Manager:** Auto-generates a default `.jks` keystore on first launch, or lets you create new keystores, inspect SHA-256 fingerprints/aliases, import existing keys, and download `.jks` backups.
- **Version-Preserving Builds & CRUD:** Timestamped filenames prevent newer builds from overwriting older releases, paired with one-tap **Download**, **Inspect** (`aapt2 dump badging`), **Rename**, **Delete**, and **Clear All** actions.
- **Global CLI Service Manager:** Manage the background server anytime with `renpystudio {start|stop|restart|status|logs}`.

---

## Limitations & Future Roadmap (TODO)

- **Hardware Back Button / Double-Tap Exit Dialog (TODO):** Intercepting Android's system Back gesture (`K_AC_BACK`) to trigger a double-tap exit confirmation dialog is planned for a future release. In v1.0.0, RenPy Studio automatically unhides the native **Quit** button in the in-game side menu so players can exit cleanly.
- **Ren'Py 8+ (Python 3) Compatibility Only:** Because the underlying runtime is Ren'Py 8.6.1, games built on older Ren'Py 6 or 7 engines (Python 2) are not supported.
- **Base Engine APK Excluded from Git:** `templates/base_engine.apk` (~50 MB) is gitignored and must be downloaded once during setup (see [`INSTALLATION.md`](INSTALLATION.md)).
- **No Native Java/C++ Bytecode Recompilation:** Customizes assets, manifest metadata, icons, and API levels around the pre-built engine runtime rather than compiling custom Android Java/NDK modules.

---

## Credits & Attribution

- **Android Runtime Port:** Built on top of the open-source ARM64/ARM32 runtime by **[eren-coder07/RenPy-Android-Port](https://github.com/eren-coder07/RenPy-Android-Port)** (Ren'Py 8.6.1).
- **Visual Novel Engine:** Powered by **[Ren'Py](https://www.renpy.org/)** created by Tom Rothamel.

See [`INSTALLATION.md`](INSTALLATION.md) for the complete Termux setup guide.
