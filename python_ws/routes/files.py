"""Files route — Upload, list, download, delete files."""
from __future__ import annotations

import asyncio
import base64
import time
from pathlib import Path
from typing import Any

_TURBO_ROOT = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = _TURBO_ROOT / "data" / "uploads"
try:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    pass  # Will fail gracefully at runtime if dir unavailable

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


async def handle_files_request(action: str, payload: dict) -> dict:
    """Handle files channel requests."""
    if action == "upload":
        return await asyncio.to_thread(_handle_upload, payload)
    elif action == "list_uploads":
        return await asyncio.to_thread(_list_uploads)
    elif action == "download":
        return await asyncio.to_thread(_handle_download, payload)
    elif action == "delete":
        return await asyncio.to_thread(_handle_delete, payload)
    return {"error": f"Unknown files action: {action}"}


def _handle_upload(payload: dict) -> dict:
    """Upload a file (base64 encoded)."""
    name = payload.get("name", "")
    data_b64 = payload.get("data", "")

    if not name or not data_b64:
        return {"error": "Missing name or data"}

    # Sanitize filename — strip path traversal, leading dots, length limit
    basename = name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    safe_name = "".join(c for c in basename if c.isalnum() or c in ".-_ ").strip().lstrip(".")
    if not safe_name:
        safe_name = f"file_{int(time.time())}"
    if len(safe_name) > 200:
        safe_name = safe_name[:200]

    try:
        data = base64.b64decode(data_b64)
    except (ValueError, base64.binascii.Error):
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


def _safe_resolve(name: str) -> Path | None:
    """Resolve filename within UPLOAD_DIR, blocking path traversal and symlinks."""
    candidate = UPLOAD_DIR / name
    # Block symlinks before resolving to prevent escaping UPLOAD_DIR
    if candidate.is_symlink():
        return None
    filepath = candidate.resolve()
    if not filepath.is_relative_to(UPLOAD_DIR.resolve()):
        return None
    return filepath


def _handle_download(payload: dict) -> dict:
    """Download a file (return base64)."""
    name = payload.get("name", "")
    if not name:
        return {"error": "Missing filename"}

    filepath = _safe_resolve(name)
    if not filepath or not filepath.exists() or not filepath.is_file():
        return {"error": "File not found"}

    data = filepath.read_bytes()
    return {
        "name": filepath.name,
        "data": base64.b64encode(data).decode(),
        "size": len(data),
    }


def _handle_delete(payload: dict) -> dict:
    """Delete an uploaded file."""
    name = payload.get("name", "")
    if not name:
        return {"error": "Missing filename"}

    filepath = _safe_resolve(name)
    if not filepath or not filepath.exists():
        return {"error": "File not found"}

    filepath.unlink()
    return {"deleted": True, "name": filepath.name}
