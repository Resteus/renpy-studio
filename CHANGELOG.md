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
