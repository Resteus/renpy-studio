import mimetypes
import os
import re
import threading
import uuid
from datetime import datetime
from pathlib import Path

import bottle
from bottle import request, response, static_file
from waitress import serve

from core.builder import (
    BUILDS_DIR,
    KEYSTORES_DIR,
    build_apk,
    create_keystore,
    delete_built_apk,
    inspect_built_apk,
    inspect_keystore_details,
    inspect_source,
    list_keystores,
    rename_built_apk,
)

mimetypes.add_type("application/vnd.android.package-archive", ".apk")
bottle.BaseRequest.MEMFILE_MAX = 1024 * 1024 * 1024

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"
UPLOADS_DIR = BUILDS_DIR / "_uploads"
RENPY_PROJECTS_DIR = Path.home() / "storage" / "shared" / "RenPyProjects"

app = bottle.Bottle()
BUILD_LOCK = threading.Lock()
BUILD_STATE = {"running": False, "logs": [], "result": None, "error": None}


def append_log(line: str):
    ts = datetime.now().strftime("%H:%M:%S")
    with BUILD_LOCK:
        BUILD_STATE["logs"].append(f"[{ts}] {line}")


def sanitize_filename(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", name).strip("_") or "upload.bin"


@app.get("/")
def index():
    return static_file("index.html", root=str(WEB_DIR))


@app.get("/api/projects")
def api_projects():
    projects = []
    if RENPY_PROJECTS_DIR.is_dir():
        for entry in sorted(RENPY_PROJECTS_DIR.iterdir(), key=lambda p: p.name.lower()):
            if entry.is_dir() and not entry.name.startswith("."):
                if (entry / "game").is_dir() or any(entry.glob("*.rpy")) or any(entry.glob("*.rpyc")):
                    projects.append({"name": entry.name, "path": str(entry)})
    return {"projects": projects}


@app.post("/api/inspect/local")
def api_inspect_local():
    raw_path = ((request.json or {}).get("path") or "").strip()
    if not raw_path:
        response.status = 400
        return {"error": "Project path is required."}
    try:
        meta = inspect_source(raw_path)
        meta["source_path"] = str(Path(raw_path).expanduser().resolve())
        return {"status": "ok", "meta": meta}
    except Exception as e:
        response.status = 400
        return {"error": str(e)}


@app.post("/api/inspect/zip")
def api_inspect_zip():
    upload = request.files.get("zip_file")
    if not upload or not upload.filename or not upload.filename.lower().endswith(".zip"):
        response.status = 400
        return {"error": "Please select a valid .zip archive."}

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    saved_path = UPLOADS_DIR / f"{uuid.uuid4().hex[:8]}_{sanitize_filename(upload.filename)}"
    try:
        upload.save(str(saved_path), overwrite=True)
        meta = inspect_source(str(saved_path))
        meta["source_path"] = str(saved_path)
        return {"status": "ok", "meta": meta}
    except Exception as e:
        saved_path.unlink(missing_ok=True)
        response.status = 400
        return {"error": str(e)}


@app.get("/api/keystores")
def api_keystores():
    return {"keystores": list_keystores()}


@app.post("/api/keystores/create")
def api_create_keystore():
    data = request.json or {}
    name = (data.get("name") or "").strip()
    password = (data.get("password") or "").strip()
    alias = (data.get("alias") or "").strip()
    cn = (data.get("cn") or "RenPyStudio").strip()
    overwrite = bool(data.get("overwrite", False))
    try:
        validity = int(data.get("validity_days") or 10000)
    except ValueError:
        validity = 10000

    if not name or not password or not alias:
        response.status = 400
        return {"error": "Keystore filename, password, and alias are required."}
    try:
        ks_path = create_keystore(name, password, alias, cn=cn, validity_days=validity, overwrite=overwrite)
        return {"status": "ok", "filename": ks_path.name}
    except Exception as e:
        response.status = 400
        return {"error": str(e)}


@app.post("/api/keystores/inspect")
def api_inspect_keystore():
    data = request.json or {}
    name = (data.get("name") or "").strip()
    password = (data.get("password") or "").strip()
    if not name or not password:
        response.status = 400
        return {"error": "Select a keystore and enter its password."}
    try:
        return {"status": "ok", "details": inspect_keystore_details(name, password)}
    except Exception as e:
        response.status = 400
        return {"error": str(e)}


@app.post("/api/keystores/upload")
def api_upload_keystore():
    upload = request.files.get("ks_file")
    if not upload or not upload.filename:
        response.status = 400
        return {"error": "Choose a .jks or .keystore file."}
    KEYSTORES_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = sanitize_filename(upload.filename)
    if not safe_name.endswith((".jks", ".keystore")):
        safe_name += ".jks"
    upload.save(str(KEYSTORES_DIR / safe_name), overwrite=True)
    return {"status": "ok", "filename": safe_name}


@app.get("/api/keystores/download/<filename>")
def api_download_keystore(filename):
    safe_name = Path(filename).name
    target = KEYSTORES_DIR / safe_name
    if not target.is_file():
        response.status = 404
        return {"error": "Keystore not found."}
    return static_file(safe_name, root=str(KEYSTORES_DIR), download=safe_name, mimetype="application/octet-stream")


@app.post("/api/build")
def api_start_build():
    with BUILD_LOCK:
        if BUILD_STATE["running"]:
            response.status = 409
            return {"error": "A build is already running."}

    source_path = (request.forms.get("source_path") or "").strip()
    app_name = (request.forms.get("app_name") or "").strip()
    package_id = (request.forms.get("package_id") or "").strip()
    version_name = (request.forms.get("version_name") or "1.0").strip()
    orientation = (request.forms.get("orientation") or "sensorLandscape").strip()
    ks_name = (request.forms.get("keystore_name") or "renpystudio.jks").strip()
    ks_pass = (request.forms.get("keystore_pass") or "renpystudio").strip()
    key_alias = (request.forms.get("key_alias") or "renpykey").strip()
    copy_dl = (request.forms.get("copy_to_downloads") or "true").strip().lower() in ("1", "true", "yes", "on")
    exit_dlg = (request.forms.get("enable_exit_dialog") or "true").strip().lower() in ("1", "true", "yes", "on")

    try:
        version_code = int(request.forms.get("version_code") or 100)
        min_sdk = int(request.forms.get("min_sdk") or 23)
        target_sdk = int(request.forms.get("target_sdk") or 36)
    except ValueError:
        response.status = 400
        return {"error": "Version Code, Minimum API, and Target API must be numbers."}

    if not source_path or not Path(source_path).exists():
        response.status = 400
        return {"error": "Load a .zip archive or project folder first."}
    if not app_name:
        response.status = 400
        return {"error": "App Name is required."}
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9_]*(\.[a-zA-Z][a-zA-Z0-9_]*)+$", package_id):
        response.status = 400
        return {"error": "Invalid Package ID (use format like com.studio.gamename)."}

    icon_saved_path = ""
    icon_upload = request.files.get("icon_file")
    if icon_upload and icon_upload.filename:
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        icon_target = UPLOADS_DIR / f"icon_{uuid.uuid4().hex[:8]}_{sanitize_filename(icon_upload.filename)}"
        icon_upload.save(str(icon_target), overwrite=True)
        icon_saved_path = str(icon_target)

    with BUILD_LOCK:
        BUILD_STATE.update({"running": True, "logs": [], "result": None, "error": None})

    def worker():
        try:
            append_log(f"Starting build for '{app_name}' ({package_id})...")
            res = build_apk(
                source_path=source_path,
                app_name=app_name,
                package_id=package_id,
                version_name=version_name,
                version_code=version_code,
                orientation=orientation,
                min_sdk=min_sdk,
                target_sdk=target_sdk,
                icon_path=icon_saved_path,
                keystore_name=ks_name,
                keystore_pass=ks_pass,
                key_alias=key_alias,
                copy_to_downloads=copy_dl,
                enable_exit_dialog=exit_dlg,
                log_fn=append_log,
            )
            with BUILD_LOCK:
                BUILD_STATE["result"] = res
        except Exception as exc:
            append_log(f"[ERROR] {exc}")
            with BUILD_LOCK:
                BUILD_STATE["error"] = str(exc)
        finally:
            if icon_saved_path:
                Path(icon_saved_path).unlink(missing_ok=True)
            with BUILD_LOCK:
                BUILD_STATE["running"] = False

    threading.Thread(target=worker, daemon=True).start()
    return {"status": "started"}


@app.get("/api/build/status")
def api_build_status():
    with BUILD_LOCK:
        return dict(BUILD_STATE)


@app.get("/api/builds")
def api_builds():
    BUILDS_DIR.mkdir(parents=True, exist_ok=True)
    apks = []
    for f in sorted(BUILDS_DIR.glob("*.apk"), key=lambda p: p.stat().st_mtime, reverse=True):
        st = f.stat()
        apks.append({
            "filename": f.name,
            "size_mb": round(st.st_size / (1024 * 1024), 2),
            "modified": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
        })
    return {"builds": apks}


@app.post("/api/builds/inspect")
def api_inspect_build():
    filename = ((request.json or {}).get("filename") or "").strip()
    try:
        return {"status": "ok", "details": inspect_built_apk(filename)}
    except Exception as e:
        response.status = 400
        return {"error": str(e)}


@app.post("/api/builds/rename")
def api_rename_build():
    data = request.json or {}
    old_name = (data.get("old_name") or "").strip()
    new_name = (data.get("new_name") or "").strip()
    try:
        renamed = rename_built_apk(old_name, new_name)
        return {"status": "ok", "filename": renamed}
    except Exception as e:
        response.status = 400
        return {"error": str(e)}


@app.post("/api/builds/delete")
def api_delete_build():
    filename = ((request.json or {}).get("filename") or "").strip()
    try:
        delete_built_apk(filename)
        return {"status": "ok"}
    except Exception as e:
        response.status = 400
        return {"error": str(e)}


@app.post("/api/builds/clear")
def api_clear_builds():
    BUILDS_DIR.mkdir(parents=True, exist_ok=True)
    removed = 0
    for f in BUILDS_DIR.glob("*.apk"):
        f.unlink(missing_ok=True)
        removed += 1
    return {"status": "ok", "removed": removed}


@app.get("/download/<filename>")
def download_apk(filename):
    safe_name = Path(filename).name
    target = BUILDS_DIR / safe_name
    if not target.is_file() or target.suffix.lower() != ".apk":
        response.status = 404
        return {"error": "APK file not found."}
    return static_file(
        safe_name,
        root=str(BUILDS_DIR),
        download=safe_name,
        mimetype="application/vnd.android.package-archive",
    )


if __name__ == "__main__":
    host = os.environ.get("RENPY_STUDIO_HOST", "127.0.0.1")
    port = int(os.environ.get("RENPY_STUDIO_PORT", "8070"))
    print(f"RenPy Studio Web UI running at http://{host}:{port}")
    serve(app, host=host, port=port, threads=4)
