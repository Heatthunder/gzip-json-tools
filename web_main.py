"""PyScript web bridge: connects DOM events to pure core_logic functions."""

from __future__ import annotations

import asyncio
import json

from js import Blob, Uint8Array, URL, document as js_document
from pyodide.ffi import create_proxy, to_js
from pyscript import document, when

from core_logic import (
    base64_to_gz_bytes,
    base64_to_json_text,
    extract_logic,
    gz_bytes_to_base64,
    json_text_to_base64,
    pack_logic,
)


status_el = document.querySelector("#status")
editor_el = document.querySelector("#editor")
base64_el = document.querySelector("#base64-text")
file_input_el = document.querySelector("#file-upload")
dropzone_el = document.querySelector("#dropzone")


def set_status(message: str, is_error: bool = False) -> None:
    """Render status text in the UI."""
    status_el.innerText = message
    status_el.style.color = "#fca5a5" if is_error else "#e5e7eb"


def _trigger_download(filename: str, payload: bytes, mime_type: str) -> None:
    """Download raw bytes to the user's machine without filesystem access."""
    uint8_data = Uint8Array.new(to_js(memoryview(payload)))
    blob = Blob.new([uint8_data], to_js({"type": mime_type}))
    download_url = URL.createObjectURL(blob)

    anchor = js_document.createElement("a")
    anchor.href = download_url
    anchor.download = filename
    js_document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    URL.revokeObjectURL(download_url)


def _load_gzip_bytes(gz_bytes: bytes, source_label: str) -> None:
    """Decode gzip payload and populate both JSON and Base64 editors."""
    editor_el.value = extract_logic(gz_bytes)
    base64_el.value = gz_bytes_to_base64(gz_bytes)
    set_status(f"Detected gzip input ({source_label}) -> decoded successfully")


def _load_json_text(json_text: str, source_label: str) -> None:
    """Validate incoming JSON text and load it into editor."""
    parsed = json.loads(json_text)
    normalized_json = json.dumps(parsed, indent=2, ensure_ascii=False)
    editor_el.value = normalized_json
    set_status(f"Detected JSON input ({source_label}) -> loaded to editor")


async def _handle_dropped_file(file_obj) -> None:
    """Route dropped file to decode or encode path based on extension."""
    name = (file_obj.name or "").lower()
    if name.endswith(".json.gz") or name.endswith(".gz") or name.endswith(".gzip"):
        set_status(f"Detected file type: {file_obj.name} (decode path)")
        gz_bytes = bytes(Uint8Array.new(await file_obj.arrayBuffer()).to_py())
        _load_gzip_bytes(gz_bytes, file_obj.name)
        return

    if name.endswith(".json"):
        set_status(f"Detected file type: {file_obj.name} (encode path)")
        _load_json_text(await file_obj.text(), file_obj.name)
        return

    set_status(
        f"Unsupported dropped file type: {file_obj.name}. Use .json.gz/.gz or .json files.",
        is_error=True,
    )


def _handle_dropped_text(raw_text: str, source_label: str = "text drop") -> None:
    """Route dropped text to Base64 decode path when possible."""
    text = (raw_text or "").strip()
    if not text:
        set_status("Dropped text is empty.", is_error=True)
        return

    try:
        gz_bytes = base64_to_gz_bytes("".join(text.split()))
    except Exception:
        set_status("Dropped text is not valid Base64 gzip content.", is_error=True)
        return

    set_status("Detected text payload: Base64 (decode path)")
    _load_gzip_bytes(gz_bytes, source_label)


@when("change", "#file-upload")
async def on_file_selected(event):
    """Load a selected .json.gz file and populate JSON + Base64 views."""
    try:
        files = event.target.files
        if not files or files.length == 0:
            set_status("No file selected.", is_error=True)
            return

        file_obj = files.item(0)
        gz_bytes = bytes(Uint8Array.new(await file_obj.arrayBuffer()).to_py())
        _load_gzip_bytes(gz_bytes, file_obj.name)
    except Exception as exc:
        set_status(f"Failed to load file: {exc}", is_error=True)


# Keep a single click binding per action button to avoid duplicate event execution.
@when("click", "#b64-to-json-btn")
def on_base64_to_json_clicked(event):
    """Decode Base64 text and populate the JSON editor."""
    try:
        editor_el.value = base64_to_json_text(base64_el.value or "")
        set_status("Decoded Base64 into JSON editor.")
    except Exception as exc:
        set_status(f"Failed to decode Base64: {exc}", is_error=True)


@when("click", "#b64-to-gz-btn")
def on_base64_to_gz_clicked(event):
    """Decode Base64 text and download a .json.gz file."""
    try:
        gz_bytes = base64_to_gz_bytes(base64_el.value or "")
        _trigger_download("save.json.gz", gz_bytes, "application/gzip")
        set_status("Decoded Base64 and downloaded save.json.gz")
    except Exception as exc:
        set_status(f"Failed to build gzip from Base64: {exc}", is_error=True)


@when("click", "#json-to-b64-btn")
def on_json_to_base64_clicked(event):
    """Convert editor JSON to Base64 and place it in the Base64 box."""
    try:
        json_text = editor_el.value or ""
        base64_el.value = json_text_to_base64(json_text, mtime=0)
        set_status("Converted JSON editor content to Base64.")
    except Exception as exc:
        set_status(f"Failed to convert JSON: {exc}", is_error=True)


@when("click", "#download-btn")
def on_download_clicked(event):
    """Pack editor JSON as gzip and trigger download."""
    try:
        json_text = editor_el.value or ""
        gz_bytes = pack_logic(json_text, mtime=0)
        _trigger_download("save.json.gz", gz_bytes, "application/gzip")
        set_status("Packed JSON editor and downloaded save.json.gz")
    except Exception as exc:
        set_status(f"Failed to pack file: {exc}", is_error=True)


def _register_drag_and_drop() -> None:
    """Attach drag-and-drop listeners to the visible dropzone."""
    if not dropzone_el:
        return

    drag_counter = {"count": 0}

    def _prevent_default(event):
        event.preventDefault()
        event.stopPropagation()

    def _on_dragenter(event):
        _prevent_default(event)
        drag_counter["count"] += 1
        dropzone_el.classList.add("is-active")
        set_status("Drag detected: drop file or Base64 text into the dropzone")

    def _on_dragover(event):
        _prevent_default(event)

    def _on_dragleave(event):
        _prevent_default(event)
        drag_counter["count"] = max(0, drag_counter["count"] - 1)
        if drag_counter["count"] == 0:
            dropzone_el.classList.remove("is-active")

    async def _on_drop_async(event):
        try:
            _prevent_default(event)
            drag_counter["count"] = 0
            dropzone_el.classList.remove("is-active")

            dt = event.dataTransfer
            files = dt.files if dt else None
            if files and files.length > 0:
                await _handle_dropped_file(files.item(0))
                return

            dropped_text = dt.getData("text/plain") if dt else ""
            _handle_dropped_text(dropped_text)
        except Exception as exc:
            set_status(f"Failed to process drop input: {exc}", is_error=True)

    def _on_drop(event):
        asyncio.create_task(_on_drop_async(event))

    def _on_paste(event):
        # Limit decode side-effects to intentional paste inside the dropzone.
        target = event.target
        if target != dropzone_el and not dropzone_el.contains(target):
            return

        clipboard = event.clipboardData
        if not clipboard:
            return

        pasted_text = clipboard.getData("text/plain")
        if pasted_text and pasted_text.strip():
            try:
                _handle_dropped_text(pasted_text, source_label="pasted text")
            except Exception as exc:
                set_status(f"Failed to decode pasted text: {exc}", is_error=True)

    # Keep proxy references alive for listener lifetime.
    global _dnd_proxies
    _dnd_proxies = {
        "dragenter": create_proxy(_on_dragenter),
        "dragover": create_proxy(_on_dragover),
        "dragleave": create_proxy(_on_dragleave),
        "drop": create_proxy(_on_drop),
        "paste": create_proxy(_on_paste),
    }

    for event_name in ("dragenter", "dragover", "dragleave", "drop"):
        js_document.addEventListener(event_name, _dnd_proxies[event_name], False)
        dropzone_el.addEventListener(event_name, _dnd_proxies[event_name], False)
    js_document.addEventListener("paste", _dnd_proxies["paste"], False)


_register_drag_and_drop()
