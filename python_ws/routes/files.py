"""Files route — Upload, list, download, delete files."""
import asyncio
import base64
import os
import time
from pathlib import Path
from typing import Any

UPLOAD_DIR = Path("F:/BUREAU/turbo/data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


async def handle_files_request(action: str, payload: dict) -> dict:
    """Handle files channel requests."""
    if action == "upload":
        return _handle_upload(payload)
    elif action == "list_uploads":
        return _list_uploads()
    elif action == "download":
        return _handle_download(payload)
    elif action == "delete":
        return _handle_delete(payload)
    return {"error": f"Unknown files action: {action}"}


def _handle_upload(payload: dict) -> dict:
    """Upload a file (base64 encoded)."""
    name = payload.get("name", "")
    data_b64 = payload.get("data", "")

    if not name or not data_b64:
        return {"error": "Missing name or data"}

    # Sanitize filename
    safe_name = "".join(c for c in name if c.isalnum() or c in ".-_ ").strip()
    if not safe_name:
        safe_name = f"file_{int(time.time())}"

    try:
        data = base64.b64decode(data_b64)
    except Exception:
        return {"error": "Invalid base64 data"}

    if len(data) > MAX_FILE_SIZE:
        return {"error": f"File too large (max {MAX_FILE_SIZE // 1024 // 1024}MB)"}

    # Add timestamp prefix to avoid conflicts
    ts = int(time.time())
    filepath = UPLOAD_DIR / f"{ts}_{safe_name}"
    filepath.write_bytes(data)

    return {
        "uploaded": True,
        "name": safe_name,
        "path": str(filepath),
        "size": len(data),
    }


def _list_uploads() -> dict:
    """List uploaded files."""
    files = []
    for f in sorted(UPLOAD_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if f.is_file():
            stat = f.stat()
            files.append({
                "name": f.name,
                "path": str(f),
                "size": stat.st_size,
                "modified": stat.st_mtime,
            })
    return {"files": files[:100]}


def _handle_download(payload: dict) -> dict:
    """Download a file (return base64)."""
    name = payload.get("name", "")
    if not name:
        return {"error": "Missing filename"}

    filepath = UPLOAD_DIR / name
    if not filepath.exists() or not filepath.is_file():
        return {"error": "File not found"}

    data = filepath.read_bytes()
    return {
        "name": name,
        "data": base64.b64encode(data).decode(),
        "size": len(data),
    }


def _handle_delete(payload: dict) -> dict:
    """Delete an uploaded file."""
    name = payload.get("name", "")
    if not name:
        return {"error": "Missing filename"}

    filepath = UPLOAD_DIR / name
    if not filepath.exists():
        return {"error": "File not found"}

    filepath.unlink()
    return {"deleted": True, "name": name}
