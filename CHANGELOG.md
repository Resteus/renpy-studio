# Changelog

All notable changes to **RenPy Studio** will be documented in this file.

## [Unreleased]

### Added
- Initialized `~/renpy-studio` repository structure (`core/`, `web/`, `templates/`, `keystores/`, `builds/`).
- Configured `.gitignore` to exclude build artifacts, keystores, and base APKs from version control.
- Verified Termux signing toolchain (`apksigner`, `zipalign`, `keytool`) and installed `apktool`.

### Added (Core Builder)
- Built `core/builder.py` with automatic `.zip` and project folder inspection (`options.rpy` parser).
- Added recursive `x-` asset prefixing into `assets/x-game/` while filtering out `cache/`, `saves/`, and `.bak` files.
- Implemented manifest, `strings.xml`, `x-android.json`, and `apktool.yml` patching plus multi-DPI icon generation via Pillow.
- Added automated keystore provisioning (`keytool`), resource compilation (`apktool`), alignment (`zipalign`), and APK signing (`apksigner`).

### Added (Web Server API)
- Created `server.py` powered by Bottle + Waitress on `http://127.0.0.1:8070`.
- Added `.zip` upload and inspection (`/api/inspect/zip`) supporting archives up to 1 GB.
- Added local `RenPyProjects` scanner (`/api/projects` and `/api/inspect/local`) for direct folder builds.
- Added background APK build queue (`/api/build`, `/api/build/status`) with live log polling and APK download endpoints (`/api/builds`, `/download/<filename>`).

### Added (Mobile Web UI)
- Created mobile-first dark interface at `web/index.html` with `.zip` project upload and `RenPyProjects` folder picker.
- Added auto-syncing Package ID slug generator, orientation selector, custom icon uploader, live scrolling build console, and one-tap APK downloads.

### Fixed & Added (Core Builder v2)
- Fixed package installation conflict (`INSTALL_FAILED_CONFLICTING_PROVIDER`) by replacing all `org.renpy.engine` provider authorities (including `androidx-startup`) in `AndroidManifest.xml`.
- Added configurable `min_sdk` and `target_sdk` patching (`apktool.yml` and `compileSdkVersion`) for future Google Play API levels (36, 37, 38+).
- Added keystore management helpers (`list_keystores`, `create_keystore`, `inspect_keystore_details`).

### Fixed & Added (Server v2)
- Fixed `.apk.html` browser download bug by serving APKs with explicit `application/vnd.android.package-archive` MIME type.
- Added API level parameters (`min_sdk`, `target_sdk`) and signing keystore parameters to `/api/build`.
- Added Key Management endpoints (`/api/keystores`, `/api/keystores/create`, `/api/keystores/inspect`, `/api/keystores/upload`, `/api/keystores/download/<filename>`).

### Added & Fixed (Web UI v2)
- Redesigned `web/index.html` into a 3-tab mobile interface (`Build`, `Keystore`, `Builds`).
- Added Minimum API (`minSdk`) and Target API (`targetSdk`) inputs for Play Store API target updates (36, 37, 38+).
- Added Keystore Management tab (inspect SHA-256/aliases, generate new `.jks`, import existing keystores, and download `.jks` backups).

### Added (Builder v3 — Exit Dialog & APK CRUD)
- Added automatic injection of `zz_android_exit.rpy` (`K_AC_BACK` -> `Quit(confirm=True)`) so pressing Android's Back button opens Ren'Py's native quit confirmation dialog.
- Added `inspect_built_apk`, `rename_built_apk`, and `delete_built_apk` helpers in `core/builder.py`.

### Added (Server v3 — Exit Dialog & Builds CRUD API)
- Passed `enable_exit_dialog` option into `build_apk()` via `/api/build`.
- Added APK management endpoints: `/api/builds/inspect`, `/api/builds/rename`, `/api/builds/delete`, and `/api/builds/clear`.

### Added (Web UI v3 — Exit Dialog Toggle & Builds CRUD)
- Added `Enable Android Back-button exit confirmation dialog` toggle to the **Build** tab.
- Added full APK CRUD controls (**Download**, **Inspect**, **Rename**, **Delete**, and **Clear All**) to the **Builds** tab.
