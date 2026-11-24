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
    seg = sanitize_package_segment(app_name)
    return f"com.renpystudio.{seg}"


def find_game_dir(root: Path) -> Path:
    """Locate the Ren'Py game/ folder inside an extracted zip or project directory."""
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
        found = list(root.rglob(marker))
        for f in found:
            if "__MACOSX" not in f.parts:
                return f.parent

    raise FileNotFoundError("Could not find a valid Ren'Py 'game/' folder or .rpy/.rpyc scripts.")


def parse_options(game_dir: Path) -> dict:
    """Extract config.name and config.version from options.rpy (or fallback to folder name)."""
    fallback_name = game_dir.parent.name if game_dir.name.lower() == "game" else game_dir.name
    if not fallback_name or fallback_name.startswith("renpy_inspect_"):
        fallback_name = "RenPy Game"

    info = {
        "app_name": fallback_name,
        "version": "1.0",
        "numeric_version": 100,
    }

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
    """Inspect a .zip archive or project folder and return detected metadata."""
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
    """Ensure templates/base_decoded exists; decode templates/base_engine.apk if needed."""
    if BASE_DECODED_DIR.is_dir() and (BASE_DECODED_DIR / "AndroidManifest.xml").is_file():
        return
    if not BASE_ENGINE_APK.is_file():
        raise FileNotFoundError(
            f"Base engine APK missing at {BASE_ENGINE_APK}. "
            "Place RenPy-8.6.1-engine-android-universal-arm32-arm64.apk there first."
        )
    log_fn("[1/6] Decoding base Ren'Py engine template...")
    subprocess.run(
        ["apktool", "d", "--no-src", "-f", str(BASE_ENGINE_APK), "-o", str(BASE_DECODED_DIR)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def ensure_keystore(ks_path: Path, ks_pass: str, alias: str, log_fn=print):
    """Create a default signing keystore if none exists."""
    if ks_path.is_file():
        return
    ks_path.parent.mkdir(parents=True, exist_ok=True)
    log_fn(f"[*] Generating default signing keystore at {ks_path.name}...")
    subprocess.run(
        [
            "keytool",
            "-genkeypair",
            "-v",
            "-keystore",
            str(ks_path),
            "-storepass",
            ks_pass,
            "-keypass",
            ks_pass,
            "-alias",
            alias,
            "-keyalg",
            "RSA",
            "-keysize",
            "2048",
            "-validity",
            "10000",
            "-dname",
            "CN=RenPyStudio, OU=MobileDev, O=RenPyStudio, L=CDO, S=MisOr, C=PH",
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def copy_game_with_x_prefix(src_game: Path, dst_x_game: Path) -> int:
    """Copy Ren'Py game assets into assets/x-game/ with 'x-' prefixed on every path component."""
    if dst_x_game.exists():
        shutil.rmtree(dst_x_game)
    dst_x_game.mkdir(parents=True, exist_ok=True)

    copied = 0
    for root, dirs, files in os.walk(src_game):
        rel_root = Path(root).relative_to(src_game)
        # Filter ignored directories in-place
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]

        x_parts = [f"x-{part}" for part in rel_root.parts]
        target_dir = dst_x_game.joinpath(*x_parts) if x_parts else dst_x_game
        target_dir.mkdir(parents=True, exist_ok=True)

        for fname in files:
            if fname in SKIP_FILES or fname.startswith("."):
                continue
            if Path(fname).suffix.lower() in SKIP_EXTS:
                continue
            src_file = Path(root) / fname
            dst_file = target_dir / f"x-{fname}"
            shutil.copy2(src_file, dst_file)
            copied += 1

    return copied


def patch_manifest_and_metadata(
    work_dir: Path,
    app_name: str,
    package_id: str,
    version_name: str,
    version_code: int,
    orientation: str,
):
    # 1. AndroidManifest.xml
    manifest_file = work_dir / "AndroidManifest.xml"
    manifest = manifest_file.read_text(encoding="utf-8")
    manifest = manifest.replace('package="org.renpy.engine"', f'package="{package_id}"')
    manifest = manifest.replace("org.renpy.engine.fileprovider", f"{package_id}.fileprovider")
    manifest = manifest.replace(
        "org.renpy.engine.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION",
        f"{package_id}.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION",
    )
    manifest = re.sub(
        r'android:screenOrientation="[^"]+"',
        f'android:screenOrientation="{orientation}"',
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

    # 4. apktool.yml
    yml_file = work_dir / "apktool.yml"
    yml = yml_file.read_text(encoding="utf-8")
    yml = re.sub(r"(versionCode:\s*)\d+", rf"\g<1>{version_code}", yml)
    yml = re.sub(r"(versionName:\s*).+", rf"\g<1>{version_name}", yml)
    yml_file.write_text(yml, encoding="utf-8")


def apply_custom_icon(work_dir: Path, icon_path: str, log_fn=print):
    if not icon_path:
        return
    src_img_path = Path(icon_path).expanduser().resolve()
    if not src_img_path.is_file():
        return
    if Image is None:
        log_fn("[!] Pillow (PIL) not found; skipping custom icon resize.")
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
        # Sample corner pixel for clean adaptive background fill
        bg_color = img.getpixel((0, 0))
        for folder, (legacy_px, adaptive_px) in densities.items():
            out_dir = work_dir / "res" / folder
            if not out_dir.is_dir():
                continue
            legacy_icon = img.resize((legacy_px, legacy_px), Image.Resampling.LANCZOS)
            legacy_icon.save(out_dir / "icon.png", format="PNG")

            # Adaptive foreground padded to safe zone (66% inner area)
            fg_canvas = Image.new("RGBA", (adaptive_px, adaptive_px), (0, 0, 0, 0))
            inner_px = int(adaptive_px * 0.66)
            offset = (adaptive_px - inner_px) // 2
            fg_resized = img.resize((inner_px, inner_px), Image.Resampling.LANCZOS)
            fg_canvas.paste(fg_resized, (offset, offset), fg_resized)
            fg_canvas.save(out_dir / "icon_foreground.png", format="PNG")

            bg_canvas = Image.new("RGBA", (adaptive_px, adaptive_px), bg_color)
            bg_canvas.save(out_dir / "icon_background.png", format="PNG")


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
    icon_path: str = "",
    keystore_name: str = "renpystudio.jks",
    keystore_pass: str = "renpystudio",
    key_alias: str = "renpykey",
    copy_to_downloads: bool = True,
    log_fn=print,
) -> dict:
    """Build, zipalign, and sign a standalone Ren'Py Android APK."""
    ensure_base_template(log_fn=log_fn)

    ks_path = KEYSTORES_DIR / keystore_name
    ensure_keystore(ks_path, keystore_pass, key_alias, log_fn=log_fn)

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

        log_fn(f"[4/6] Patching manifest ({package_id}) & app metadata...")
        patch_manifest_and_metadata(
            work_dir=app_work,
            app_name=app_name,
            package_id=package_id,
            version_name=version_name,
            version_code=int(version_code),
            orientation=orientation,
        )
        apply_custom_icon(app_work, icon_path, log_fn=log_fn)

        unaligned_apk = work_root / "unaligned.apk"
        aligned_apk = work_root / "aligned.apk"

        safe_slug = re.sub(r"[^a-zA-Z0-9._-]+", "_", app_name).strip("_") or "RenPyGame"
        out_filename = f"{safe_slug}-v{version_name}-signed.apk"
        final_apk = BUILDS_DIR / out_filename

        log_fn("[5/6] Compiling APK resources with apktool & aapt2...")
        run_cmd(["apktool", "b", str(app_work), "-o", str(unaligned_apk)], "apktool build")

        log_fn("[6/6] Aligning (zipalign) & signing (apksigner)...")
        run_cmd(["zipalign", "-f", "-p", "4", str(unaligned_apk), str(aligned_apk)], "zipalign")
        run_cmd(
            [
                "apksigner",
                "sign",
                "--ks",
                str(ks_path),
                "--ks-pass",
                f"pass:{keystore_pass}",
                "--ks-key-alias",
                key_alias,
                "--out",
                str(final_apk),
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
            "apk_path": str(final_apk),
            "downloads_path": downloads_path,
            "size_mb": size_mb,
            "files_bundled": file_count,
            "package_id": package_id,
        }
    finally:
        shutil.rmtree(work_root, ignore_errors=True)
