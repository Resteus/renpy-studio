import os
import re
import shutil
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

import bottle
from bottle import request, response, static_file
from waitress import serve

from core.builder import (
    BUILDS_DIR,
    build_apk,
    inspect_source,
)

# Allow large Ren'Py project ZIP uploads (up to 1 GB)
bottle.BaseRequest.MEMFILE_MAX = 1024 * 1024 * 1024

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"
UPLOADS_DIR = BUILDS_DIR / "_uploads"
RENPY_PROJECTS_DIR = Path.home() / "storage" / "shared" / "RenPyProjects"

app = bottle.Bottle()

BUILD_LOCK = threading.Lock()
BUILD_STATE = {
    "running": False,
    "logs": [],
    "result": None,
    "error": None,
    "started_at": None,
}


def append_log(line: str):
    ts = datetime.now().strftime("%H:%M:%S")
    with BUILD_LOCK:
        BUILD_STATE["logs"].append(f"[{ts}] {line}")


def sanitize_filename(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", name).strip("_")
    return cleaned or "upload.bin"


@app.get("/")
def index():
    return static_file("index.html", root=str(WEB_DIR))


@app.get("/api/projects")
def list_local_projects():
    projects = []
    if RENPY_PROJECTS_DIR.is_dir():
        for entry in sorted(RENPY_PROJECTS_DIR.iterdir(), key=lambda p: p.name.lower()):
            if entry.is_dir() and not entry.name.startswith("."):
                has_game = (entry / "game").is_dir() or any(entry.glob("*.rpy")) or any(entry.glob("*.rpyc"))
                if has_game:
                    projects.append({
                        "name": entry.name,
                        "path": str(entry),
                    })
    return {"projects": projects, "base_dir": str(RENPY_PROJECTS_DIR)}


@app.post("/api/inspect/local")
def api_inspect_local():
    data = request.json or {}
    raw_path = (data.get("path") or "").strip()
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
    if not upload or not upload.filename:
        response.status = 400
        return {"error": "Please choose a .zip file to upload."}

    if not upload.filename.lower().endswith(".zip"):
        response.status = 400
        return {"error": "Only .zip archives are supported."}

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = sanitize_filename(upload.filename)
    saved_path = UPLOADS_DIR / f"{uuid.uuid4().hex[:8]}_{safe_name}"

    try:
        upload.save(str(saved_path), overwrite=True)
        meta = inspect_source(str(saved_path))
        meta["source_path"] = str(saved_path)
        meta["zip_name"] = upload.filename
        return {"status": "ok", "meta": meta}
    except Exception as e:
        if saved_path.exists():
            saved_path.unlink(missing_ok=True)
        response.status = 400
        return {"error": str(e)}


@app.post("/api/build")
def api_start_build():
    with BUILD_LOCK:
        if BUILD_STATE["running"]:
            response.status = 409
            return {"error": "A build is already running. Please wait for it to finish."}

    source_path = (request.forms.get("source_path") or "").strip()
    app_name = (request.forms.get("app_name") or "").strip()
    package_id = (request.forms.get("package_id") or "").strip()
    version_name = (request.forms.get("version_name") or "1.0").strip()
    orientation = (request.forms.get("orientation") or "sensorLandscape").strip()
    copy_dl_raw = (request.forms.get("copy_to_downloads") or "true").strip().lower()
    copy_to_downloads = copy_dl_raw in ("1", "true", "yes", "on")

    try:
        version_code = int(request.forms.get("version_code") or 100)
    except ValueError:
        version_code = 100

    if not source_path or not Path(source_path).exists():
        response.status = 400
        return {"error": "Project source not found. Select a project or import a .zip first."}

    if not app_name:
        response.status = 400
        return {"error": "App Name is required."}

    if not re.match(r"^[a-zA-Z][a-zA-Z0-9_]*(\.[a-zA-Z][a-zA-Z0-9_]*)+$", package_id):
        response.status = 400
        return {"error": "Invalid Package ID. Use format like com.studio.gamename"}

    icon_saved_path = ""
    icon_upload = request.files.get("icon_file")
    if icon_upload and icon_upload.filename:
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        icon_name = sanitize_filename(icon_upload.filename)
        icon_target = UPLOADS_DIR / f"icon_{uuid.uuid4().hex[:8]}_{icon_name}"
        icon_upload.save(str(icon_target), overwrite=True)
        icon_saved_path = str(icon_target)

    with BUILD_LOCK:
        BUILD_STATE["running"] = True
        BUILD_STATE["logs"] = []
        BUILD_STATE["result"] = None
        BUILD_STATE["error"] = None
        BUILD_STATE["started_at"] = time.time()

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
                icon_path=icon_saved_path,
                copy_to_downloads=copy_to_downloads,
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
        return {
            "running": BUILD_STATE["running"],
            "logs": list(BUILD_STATE["logs"]),
            "result": BUILD_STATE["result"],
            "error": BUILD_STATE["error"],
        }


@app.get("/api/builds")
def api_list_builds():
    BUILDS_DIR.mkdir(parents=True, exist_ok=True)
    apks = []
    for f in sorted(BUILDS_DIR.glob("*.apk"), key=lambda p: p.stat().st_mtime, reverse=True):
        stat = f.stat()
        apks.append({
            "filename": f.name,
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
        })
    return {"builds": apks}


@app.get("/download/<filename>")
def download_apk(filename):
    safe_name = Path(filename).name
    target = BUILDS_DIR / safe_name
    if not target.is_file() or target.suffix.lower() != ".apk":
        response.status = 404
        return {"error": "APK file not found."}
    return static_file(safe_name, root=str(BUILDS_DIR), download=safe_name)


if __name__ == "__main__":
    host = os.environ.get("RENPY_STUDIO_HOST", "127.0.0.1")
    port = int(os.environ.get("RENPY_STUDIO_PORT", "8070"))
    print(f"RenPy Studio Web UI running at http://{host}:{port}")
    serve(app, host=host, port=port, threads=4)
