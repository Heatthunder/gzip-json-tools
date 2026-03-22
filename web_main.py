"""PyScript web bridge: connects DOM events to pure core_logic functions."""

from __future__ import annotations

from js import Blob, Uint8Array, URL, document as js_document
from pyodide.ffi import to_js
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


def set_status(message: str, is_error: bool = False) -> None:
    """Render status text in the UI."""
    status_el.innerText = message
    status_el.style.color = "#b00020" if is_error else "#1f2937"


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


@when("change", "#file-upload")
async def on_file_selected(event):
    """Load a .json.gz file, then populate both Base64 and JSON editor views."""
    try:
        files = event.target.files
        if not files or files.length == 0:
            set_status("No file selected.", is_error=True)
            return

        file_obj = files.item(0)
        buffer = await file_obj.arrayBuffer()
        gz_bytes = bytes(Uint8Array.new(buffer).to_py())

        base64_el.value = gz_bytes_to_base64(gz_bytes)
        editor_el.value = extract_logic(gz_bytes)
        set_status(f"Loaded and converted: {file_obj.name}")
    except Exception as exc:
        set_status(f"Failed to load file: {exc}", is_error=True)


@when("click", "#b64-to-json-btn")
def on_base64_to_json_clicked(event):
    """Decode Base64 text and populate the JSON editor."""
    try:
        base64_text = base64_el.value or ""
        editor_el.value = base64_to_json_text(base64_text)
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
        base64_el.value = json_text_to_base64(json_text, filename="save.json", mtime=0)
        set_status("Converted JSON editor content to Base64.")
    except Exception as exc:
        set_status(f"Failed to convert JSON: {exc}", is_error=True)


@when("click", "#download-btn")
def on_download_clicked(event):
    """Pack editor JSON as gzip and trigger download."""
    try:
        json_text = editor_el.value or ""
        gz_bytes = pack_logic(json_text, filename="save.json", mtime=0)
        _trigger_download("save.json.gz", gz_bytes, "application/gzip")
        set_status("Packed JSON editor and downloaded save.json.gz")
    except Exception as exc:
        set_status(f"Failed to pack file: {exc}", is_error=True)
