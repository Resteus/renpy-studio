from datetime import datetime
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

try:
    from PIL import Image
except ImportError:
    Image = None

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
BASE_ENGINE_APK = TEMPLATES_DIR / "base_engine.apk"
BASE_DECODED_DIR = TEMPLATES_DIR / "base_decoded"
KEYSTORES_DIR = BASE_DIR / "keystores"
BUILDS_DIR = BASE_DIR / "builds"

SKIP_DIRS = {"cache", "saves", "__pycache__", ".git", ".idea", ".vscode"}
SKIP_EXTS = {".bak", ".tmp", ".swp", ".pyc", ".pyo"}
SKIP_FILES = {".DS_Store", "Thumbs.db", "errors.txt", "traceback.txt", "log.txt"}


def sanitize_package_segment(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "", text.lower())
    if not cleaned:
        return "game"
    if cleaned[0].isdigit():
        cleaned = "g_" + cleaned
    return cleaned


def make_default_package(app_name: str) -> str:
    return f"com.renpystudio.{sanitize_package_segment(app_name)}"


def find_game_dir(root: Path) -> Path:
    if (root / "game").is_dir():
        return root / "game"
    markers = {"script.rpy", "script.rpyc", "options.rpy", "options.rpyc"}
    if any((root / m).exists() for m in markers):
        return root
    for candidate in sorted(root.rglob("game")):
        if candidate.is_dir() and "__MACOSX" not in candidate.parts:
            if any((candidate / m).exists() for m in markers) or any(candidate.iterdir()):
                return candidate
    for marker in markers:
        for f in root.rglob(marker):
            if "__MACOSX" not in f.parts:
                return f.parent
    raise FileNotFoundError("Could not find a valid Ren'Py 'game/' folder or .rpy/.rpyc scripts.")


def parse_options(game_dir: Path) -> dict:
    fallback_name = game_dir.parent.name if game_dir.name.lower() == "game" else game_dir.name
    if not fallback_name or fallback_name.startswith("renpy_inspect_"):
        fallback_name = "RenPy Game"

    info = {"app_name": fallback_name, "version": "1.0", "numeric_version": 100}
    options_rpy = game_dir / "options.rpy"
    if options_rpy.is_file():
        text = options_rpy.read_text(encoding="utf-8", errors="ignore")
        m_name = re.search(r'config\.name\s*=\s*(?:_\()?\s*["\']([^"\']+)["\']', text)
        if m_name:
            info["app_name"] = m_name.group(1).strip()
        m_ver = re.search(r'config\.version\s*=\s*["\']([^"\']+)["\']', text)
        if m_ver:
            info["version"] = m_ver.group(1).strip()

    digits = re.findall(r"\d+", info["version"])
    if digits:
        nums = [int(d) for d in digits[:3]]
        while len(nums) < 3:
            nums.append(0)
        info["numeric_version"] = max(1, nums[0] * 10000 + nums[1] * 100 + nums[2])

    info["package_id"] = make_default_package(info["app_name"])
    return info


def inspect_source(source_path: str) -> dict:
    src = Path(source_path).expanduser().resolve()
    if not src.exists():
        raise FileNotFoundError(f"Source not found: {src}")

    if src.is_dir():
        game_dir = find_game_dir(src)
        meta = parse_options(game_dir)
        meta["file_count"] = sum(1 for _ in game_dir.rglob("*") if _.is_file())
        return meta

    if src.is_file() and src.suffix.lower() == ".zip":
        tmp_dir = Path(tempfile.mkdtemp(prefix="renpy_inspect_"))
        try:
            with zipfile.ZipFile(src, "r") as zf:
                zf.extractall(tmp_dir)
            game_dir = find_game_dir(tmp_dir)
            meta = parse_options(game_dir)
            if meta["app_name"] == "RenPy Game":
                meta["app_name"] = src.stem
                meta["package_id"] = make_default_package(src.stem)
            meta["file_count"] = sum(1 for _ in game_dir.rglob("*") if _.is_file())
            return meta
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    raise ValueError("Source must be a .zip file or a project directory.")


def ensure_base_template(log_fn=print):
    if BASE_DECODED_DIR.is_dir() and (BASE_DECODED_DIR / "AndroidManifest.xml").is_file():
        return
    if not BASE_ENGINE_APK.is_file():
        raise FileNotFoundError(f"Base engine APK missing at {BASE_ENGINE_APK}.")
    log_fn("[1/6] Decoding base Ren'Py engine template...")
    subprocess.run(
        ["apktool", "d", "--no-src", "-f", str(BASE_ENGINE_APK), "-o", str(BASE_DECODED_DIR)],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )


def create_keystore(
    ks_name: str,
    ks_pass: str,
    alias: str,
    cn: str = "RenPyStudio",
    validity_days: int = 10000,
    overwrite: bool = False,
) -> Path:
    KEYSTORES_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^a-zA-Z0-9._-]+", "_", ks_name).strip("_") or "renpystudio.jks"
    if not safe_name.endswith((".jks", ".keystore")):
        safe_name += ".jks"
    ks_path = KEYSTORES_DIR / safe_name

    if ks_path.exists():
        if not overwrite:
            raise FileExistsError(f"Keystore '{safe_name}' already exists.")
        ks_path.unlink()

    if len(ks_pass) < 6:
        raise ValueError("Keystore password must be at least 6 characters.")

    proc = subprocess.run(
        [
            "keytool", "-genkeypair", "-v",
            "-keystore", str(ks_path),
            "-storepass", ks_pass,
            "-keypass", ks_pass,
            "-alias", alias,
            "-keyalg", "RSA",
            "-keysize", "2048",
            "-validity", str(int(validity_days)),
            "-dname", f"CN={cn}, OU=MobileDev, O=RenPyStudio, L=CDO, S=MisOr, C=PH",
        ],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"keytool error:\n{proc.stdout}")
    return ks_path


def ensure_default_keystore(log_fn=print) -> Path:
    KEYSTORES_DIR.mkdir(parents=True, exist_ok=True)
    existing = list(KEYSTORES_DIR.glob("*.jks")) + list(KEYSTORES_DIR.glob("*.keystore"))
    if existing:
        return existing[0]
    log_fn("[*] Generating default signing keystore (renpystudio.jks)...")
    return create_keystore("renpystudio.jks", "renpystudio", "renpykey")


def inspect_keystore_details(ks_name: str, ks_pass: str) -> dict:
    ks_path = KEYSTORES_DIR / Path(ks_name).name
    if not ks_path.is_file():
        raise FileNotFoundError(f"Keystore not found: {ks_name}")
    proc = subprocess.run(
        ["keytool", "-list", "-v", "-keystore", str(ks_path), "-storepass", ks_pass],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    if proc.returncode != 0:
        raise ValueError("Wrong password or unreadable keystore.")
    out = proc.stdout
    aliases = re.findall(r"Alias name:\s*(.+)", out)
    sha256_m = re.search(r"SHA256:\s*([A-F0-9:]+)", out)
    valid_m = re.search(r"Valid from:\s*(.+)", out)
    return {
        "name": ks_path.name,
        "aliases": [a.strip() for a in aliases] or ["renpykey"],
        "sha256": sha256_m.group(1).strip() if sha256_m else "Unknown",
        "valid": valid_m.group(1).strip() if valid_m else "Unknown",
    }


def list_keystores() -> list:
    ensure_default_keystore()
    items = []
    files = sorted(
        list(KEYSTORES_DIR.glob("*.jks")) + list(KEYSTORES_DIR.glob("*.keystore")),
        key=lambda p: p.name.lower(),
    )
    for f in files:
        entry = {
            "name": f.name,
            "size_kb": round(f.stat().st_size / 1024, 1),
            "default_alias": "renpykey" if f.name == "renpystudio.jks" else "",
            "default_pass": "renpystudio" if f.name == "renpystudio.jks" else "",
            "sha256": "",
        }
        if f.name == "renpystudio.jks":
            try:
                info = inspect_keystore_details(f.name, "renpystudio")
                entry["default_alias"] = info["aliases"][0]
                entry["sha256"] = info["sha256"]
            except Exception:
                pass
        items.append(entry)
    return items


def copy_game_with_x_prefix(src_game: Path, dst_x_game: Path) -> int:
    if dst_x_game.exists():
        shutil.rmtree(dst_x_game)
    dst_x_game.mkdir(parents=True, exist_ok=True)
    copied = 0
    for root, dirs, files in os.walk(src_game):
        rel_root = Path(root).relative_to(src_game)
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        x_parts = [f"x-{part}" for part in rel_root.parts]
        target_dir = dst_x_game.joinpath(*x_parts) if x_parts else dst_x_game
        target_dir.mkdir(parents=True, exist_ok=True)
        for fname in files:
            if fname in SKIP_FILES or fname.startswith(".") or Path(fname).suffix.lower() in SKIP_EXTS:
                continue
            shutil.copy2(Path(root) / fname, target_dir / f"x-{fname}")
            copied += 1
    return copied


def patch_manifest_and_metadata(
    work_dir: Path,
    app_name: str,
    package_id: str,
    version_name: str,
    version_code: int,
    orientation: str,
    min_sdk: int,
    target_sdk: int,
):
    # 1. AndroidManifest.xml — replace ALL org.renpy.engine occurrences (package, providers, permissions)
    manifest_file = work_dir / "AndroidManifest.xml"
    manifest = manifest_file.read_text(encoding="utf-8")
    manifest = manifest.replace("org.renpy.engine", package_id)
    manifest = re.sub(
        r'android:screenOrientation="[^"]+"',
        f'android:screenOrientation="{orientation}"',
        manifest,
    )
    manifest = re.sub(
        r'android:compileSdkVersion="\d+"',
        f'android:compileSdkVersion="{target_sdk}"',
        manifest,
    )
    manifest_file.write_text(manifest, encoding="utf-8")

    # 2. res/values/strings.xml
    strings_file = work_dir / "res" / "values" / "strings.xml"
    strings_xml = strings_file.read_text(encoding="utf-8")
    escaped_name = xml_escape(app_name)
    for key in ("appName", "app_name", "iconName"):
        strings_xml = re.sub(
            rf'(<string name="{key}">).*?(</string>)',
            rf"\g<1>{escaped_name}\g<2>",
            strings_xml,
        )
    strings_file.write_text(strings_xml, encoding="utf-8")

    # 3. assets/x-android.json
    android_json_file = work_dir / "assets" / "x-android.json"
    if android_json_file.is_file():
        data = json.loads(android_json_file.read_text(encoding="utf-8"))
        data["name"] = app_name
        data["icon_name"] = app_name
        data["package"] = package_id
        data["orientation"] = orientation
        data["version"] = version_name
        data["numeric_version"] = version_code
        android_json_file.write_text(json.dumps(data, indent=4), encoding="utf-8")

    # 4. apktool.yml (Min API, Target API, Version Code & Name)
    yml_file = work_dir / "apktool.yml"
    yml = yml_file.read_text(encoding="utf-8")
    yml = re.sub(r"(minSdkVersion:\s*)\d+", rf"\g<1>{min_sdk}", yml)
    yml = re.sub(r"(targetSdkVersion:\s*)\d+", rf"\g<1>{target_sdk}", yml)
    yml = re.sub(r"(versionCode:\s*)\d+", rf"\g<1>{version_code}", yml)
    yml = re.sub(r"(versionName:\s*).+", rf"\g<1>{version_name}", yml)
    yml_file.write_text(yml, encoding="utf-8")


def apply_custom_icon(work_dir: Path, icon_path: str, log_fn=print):
    if not icon_path:
        return
    src_img_path = Path(icon_path).expanduser().resolve()
    if not src_img_path.is_file() or Image is None:
        return

    log_fn("[*] Generating multi-DPI Android app icons...")
    densities = {
        "mipmap-mdpi": (48, 108),
        "mipmap-hdpi": (72, 162),
        "mipmap-xhdpi": (96, 216),
        "mipmap-xxhdpi": (144, 324),
        "mipmap-xxxhdpi": (192, 432),
    }

    with Image.open(src_img_path).convert("RGBA") as img:
        bg_color = img.getpixel((0, 0))
        for folder, (legacy_px, adaptive_px) in densities.items():
            out_dir = work_dir / "res" / folder
            if not out_dir.is_dir():
                continue
            img.resize((legacy_px, legacy_px), Image.Resampling.LANCZOS).save(out_dir / "icon.png", format="PNG")
            fg_canvas = Image.new("RGBA", (adaptive_px, adaptive_px), (0, 0, 0, 0))
            inner_px = int(adaptive_px * 0.66)
            offset = (adaptive_px - inner_px) // 2
            fg_resized = img.resize((inner_px, inner_px), Image.Resampling.LANCZOS)
            fg_canvas.paste(fg_resized, (offset, offset), fg_resized)
            fg_canvas.save(out_dir / "icon_foreground.png", format="PNG")
            Image.new("RGBA", (adaptive_px, adaptive_px), bg_color).save(out_dir / "icon_background.png", format="PNG")


def run_cmd(cmd: list, step_label: str):
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"{step_label} failed:\n{proc.stdout}")
    return proc.stdout


def build_apk(
    source_path: str,
    app_name: str,
    package_id: str,
    version_name: str = "1.0",
    version_code: int = 100,
    orientation: str = "sensorLandscape",
    min_sdk: int = 23,
    target_sdk: int = 36,
    icon_path: str = "",
    keystore_name: str = "renpystudio.jks",
    keystore_pass: str = "renpystudio",
    key_alias: str = "renpykey",
    copy_to_downloads: bool = True,
    enable_exit_dialog: bool = True,
    log_fn=print,
) -> dict:
    ensure_base_template(log_fn=log_fn)
    ensure_default_keystore(log_fn=log_fn)

    ks_path = KEYSTORES_DIR / Path(keystore_name).name
    if not ks_path.is_file():
        raise FileNotFoundError(f"Selected keystore '{keystore_name}' not found.")

    BUILDS_DIR.mkdir(parents=True, exist_ok=True)
    work_root = Path(tempfile.mkdtemp(prefix="renpy_build_"))

    try:
        src = Path(source_path).expanduser().resolve()
        if src.is_file() and src.suffix.lower() == ".zip":
            log_fn(f"[1/6] Extracting ZIP archive ({src.name})...")
            extract_dir = work_root / "extracted_src"
            extract_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(src, "r") as zf:
                zf.extractall(extract_dir)
            game_dir = find_game_dir(extract_dir)
        elif src.is_dir():
            log_fn(f"[1/6] Reading project folder ({src.name})...")
            game_dir = find_game_dir(src)
        else:
            raise ValueError("Invalid project source path.")

        log_fn("[2/6] Cloning Ren'Py 8.6.1 ARM64 runtime template...")
        app_work = work_root / "app_work"
        shutil.copytree(BASE_DECODED_DIR, app_work)

        log_fn("[3/6] Packing game scripts & assets with x- prefix...")
        file_count = copy_game_with_x_prefix(game_dir, app_work / "assets" / "x-game")
        if file_count == 0:
            raise RuntimeError("No valid game files found inside the game/ folder.")
        log_fn(f"      Bundled {file_count} game files into assets/x-game/")
        if enable_exit_dialog:
            inject_exit_dialog(app_work / "assets" / "x-game")
            log_fn("      Injected Android Back-button exit confirmation dialog")

        log_fn(f"[4/6] Patching manifest ({package_id} | API {min_sdk}->{target_sdk})...")
        patch_manifest_and_metadata(
            work_dir=app_work,
            app_name=app_name,
            package_id=package_id,
            version_name=version_name,
            version_code=int(version_code),
            orientation=orientation,
            min_sdk=int(min_sdk),
            target_sdk=int(target_sdk),
        )
        apply_custom_icon(app_work, icon_path, log_fn=log_fn)

        unaligned_apk = work_root / "unaligned.apk"
        aligned_apk = work_root / "aligned.apk"
        safe_slug = re.sub(r"[^a-zA-Z0-9._-]+", "_", app_name).strip("_") or "RenPyGame"
        out_filename = f"{safe_slug}-v{version_name}-{datetime.now().strftime('%Y%m%d_%H%M%S')}-signed.apk"
        final_apk = BUILDS_DIR / out_filename

        log_fn("[5/6] Compiling APK resources with apktool & aapt2...")
        run_cmd(["apktool", "b", str(app_work), "-o", str(unaligned_apk)], "apktool build")

        log_fn(f"[6/6] Aligning & signing with {ks_path.name} (alias: {key_alias})...")
        run_cmd(["zipalign", "-f", "-p", "4", str(unaligned_apk), str(aligned_apk)], "zipalign")
        run_cmd(
            [
                "apksigner", "sign",
                "--ks", str(ks_path),
                "--ks-pass", f"pass:{keystore_pass}",
                "--ks-key-alias", key_alias,
                "--out", str(final_apk),
                str(aligned_apk),
            ],
            "apksigner",
        )

        downloads_path = ""
        if copy_to_downloads:
            dl_dir = Path.home() / "storage" / "downloads"
            if dl_dir.is_dir():
                dl_target = dl_dir / out_filename
                shutil.copy2(final_apk, dl_target)
                downloads_path = str(dl_target)
                log_fn(f"[✓] Copied signed APK to Downloads: {out_filename}")

        size_mb = round(final_apk.stat().st_size / (1024 * 1024), 2)
        log_fn(f"[✓] Build complete! {out_filename} ({size_mb} MB)")
        return {
            "status": "success",
            "filename": out_filename,
            "size_mb": size_mb,
            "files_bundled": file_count,
            "package_id": package_id,
        }
    finally:
        shutil.rmtree(work_root, ignore_errors=True)


EXIT_HOOK_RPY = '# Auto-injected by RenPy Studio: Double-Tap Android Back -> Exit Dialog\ninit 1000 python:\n    import time as _rs_time\n    _rs_last_back = 0.0\n    config.quit_action = Quit(confirm=True)\n\n    def _rs_on_back():\n        global _rs_last_back\n        if renpy.get_screen("confirm"):\n            renpy.hide_screen("confirm")\n            renpy.restart_interaction()\n            return\n        now = _rs_time.time()\n        if now - _rs_last_back <= 2.0:\n            _rs_last_back = 0.0\n            renpy.hide_screen("_rs_back_toast")\n            renpy.run(Quit(confirm=True))\n        else:\n            _rs_last_back = now\n            renpy.show_screen("_rs_back_toast")\n            renpy.restart_interaction()\n\n    def _rs_install_back_keymap():\n        for _k, _vals in list(config.keymap.items()):\n            if isinstance(_vals, list):\n                config.keymap[_k] = [_v for _v in _vals if "K_AC_BACK" not in str(_v)]\n        _km = renpy.Keymap(K_AC_BACK=_rs_on_back, any_K_AC_BACK=_rs_on_back)\n        config.underlay = [_u for _u in config.underlay if getattr(_u, "_rs_tag", "") != "back_exit"]\n        _km._rs_tag = "back_exit"\n        config.underlay.insert(0, _km)\n\n    if _rs_install_back_keymap not in config.start_callbacks:\n        config.start_callbacks.append(_rs_install_back_keymap)\n    if _rs_install_back_keymap not in config.after_load_callbacks:\n        config.after_load_callbacks.append(_rs_install_back_keymap)\n\nscreen _rs_back_toast():\n    zorder 1000\n    timer 2.0 action Hide("_rs_back_toast")\n    frame:\n        xalign 0.5\n        yalign 0.92\n        background "#11161dE6"\n        padding (24, 12)\n        text "Press Back again to exit" size 26 color "#FFFFFF"\n'


def inject_exit_dialog(dst_x_game: Path):
    hook_file = dst_x_game / "x-zz_android_exit.rpy"
    hook_file.write_text(EXIT_HOOK_RPY, encoding="utf-8")


def inspect_built_apk(filename: str) -> dict:
    safe_name = Path(filename).name
    target = BUILDS_DIR / safe_name
    if not target.is_file():
        raise FileNotFoundError("APK not found.")
    badging = subprocess.run(
        ["aapt2", "dump", "badging", str(target)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    ).stdout
    pkg_m = re.search(r"package: name='([^']+)' versionCode='([^']+)' versionName='([^']+)'", badging)
    sdk_m = re.search(r"sdkVersion:'(\d+)'", badging)
    tgt_m = re.search(r"targetSdkVersion:'(\d+)'", badging)
    lbl_m = re.search(r"application-label:'([^']+)'", badging)
    return {
        "filename": safe_name,
        "size_mb": round(target.stat().st_size / (1024 * 1024), 2),
        "app_name": lbl_m.group(1) if lbl_m else "Unknown",
        "package_id": pkg_m.group(1) if pkg_m else "Unknown",
        "version_code": pkg_m.group(2) if pkg_m else "?",
        "version_name": pkg_m.group(3) if pkg_m else "?",
        "min_sdk": sdk_m.group(1) if sdk_m else "?",
        "target_sdk": tgt_m.group(1) if tgt_m else "?",
    }


def rename_built_apk(old_name: str, new_name: str) -> str:
    src = BUILDS_DIR / Path(old_name).name
    if not src.is_file():
        raise FileNotFoundError("Original APK not found.")
    clean = re.sub(r"[^a-zA-Z0-9._-]+", "_", new_name.strip()).strip("_")
    if not clean:
        raise ValueError("Invalid new filename.")
    if not clean.lower().endswith(".apk"):
        clean += ".apk"
    dst = BUILDS_DIR / clean
    if dst.exists():
        raise FileExistsError(f"'{clean}' already exists.")
    src.rename(dst)
    return clean


def delete_built_apk(filename: str):
    target = BUILDS_DIR / Path(filename).name
    if not target.is_file():
        raise FileNotFoundError("APK not found.")
    target.unlink()
