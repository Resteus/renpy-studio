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
