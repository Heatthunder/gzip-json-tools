"""PyScript web bridge: connects DOM events to pure core_logic functions."""

from __future__ import annotations

import io

from js import Blob, Uint8Array, URL, document as js_document
from pyodide.ffi import to_js
from pyscript import document, when

from core_logic import (
    base64_to_gzip_logic,
    extract_base64_logic,
    extract_logic,
    gzip_to_base64_logic,
    pack_base64_logic,
    pack_logic,
)


status_el = document.querySelector("#status")
editor_el = document.querySelector("#editor")
file_input_el = document.querySelector("#file-upload")
base64_el = document.querySelector("#base64-editor")

_last_upload_name = "save.gz"
_last_gz_bytes = b""


def set_status(message: str, is_error: bool = False) -> None:
    """Render status text in the UI."""
    status_el.innerText = message
    status_el.style.color = "#b00020" if is_error else "#1f2937"


def _infer_json_filename(upload_name: str) -> str:
    """Map uploaded filename to a stable JSON name for gzip header metadata."""
    if upload_name.lower().endswith(".gz"):
        return f"{upload_name[:-3]}.json"
    return "save.json"


def _infer_gz_filename(upload_name: str) -> str:
    """Infer a stable .gz filename for browser downloads."""
    if upload_name.lower().endswith(".gz"):
        return upload_name
    if upload_name:
        return f"{upload_name}.gz"
    return "save.gz"


@when("change", "#file-upload")
async def on_file_selected(event):
    """Load a selected gzip save file, decode it, and place JSON in editor."""
    try:
        files = event.target.files
        if not files or files.length == 0:
            set_status("No file selected.", is_error=True)
            return

        file_obj = files.item(0)
        await _load_gzip_file(file_obj)
    except Exception as exc:  # Surface parse/decompression errors to user.
        set_status(f"Failed to load file: {exc}", is_error=True)


async def _load_gzip_file(file_obj) -> None:
    """Load a JS File object containing gzip bytes into editor/base state."""
    global _last_upload_name, _last_gz_bytes
    buffer = await file_obj.arrayBuffer()
    gz_bytes = bytes(Uint8Array.new(buffer).to_py())
    _last_upload_name = file_obj.name or "save.gz"
    _last_gz_bytes = gz_bytes

    # Keep browser-side file work in-memory; core logic remains pure.
    with io.BytesIO(gz_bytes) as _stream:
        json_text = extract_logic(_stream.getvalue())

    editor_el.value = json_text
    set_status(f"Loaded: {file_obj.name}")


@when("click", "#download-btn")
def on_download_clicked(event):
    """Read JSON from editor, repack as gzip bytes, and trigger download."""
    try:
        json_text = editor_el.value or ""
        if not json_text.strip():
            set_status("Editor is empty; nothing to pack.", is_error=True)
            return

        upload_name = _last_upload_name
        packed_bytes = pack_logic(json_text, filename=_infer_json_filename(upload_name))

        uint8_data = Uint8Array.new(to_js(memoryview(packed_bytes)))
        blob = Blob.new([uint8_data], to_js({"type": "application/gzip"}))

        download_url = URL.createObjectURL(blob)
        anchor = js_document.createElement("a")
        anchor.href = download_url
        anchor.download = _infer_gz_filename(upload_name)
        js_document.body.appendChild(anchor)
        anchor.click()
        anchor.remove()
        URL.revokeObjectURL(download_url)

        set_status(f"Packed and downloaded {_infer_gz_filename(upload_name)}")
    except Exception as exc:  # Surface JSON validation/compression errors.
        set_status(f"Failed to pack file: {exc}", is_error=True)


def _download_bytes(filename: str, payload: bytes, mime_type: str) -> None:
    """Browser helper for downloading in-memory bytes."""
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


@when("click", "#json-to-base64-btn")
def on_json_to_base64(event):
    """Encode editor JSON as Base64(gzip(json))."""
    try:
        json_text = editor_el.value or ""
        if not json_text.strip():
            set_status("Editor is empty; nothing to encode.", is_error=True)
            return
        base64_el.value = pack_base64_logic(json_text, filename=_infer_json_filename(_last_upload_name))
        set_status("Converted JSON editor content to Base64 string.")
    except Exception as exc:
        set_status(f"Failed to convert JSON to Base64: {exc}", is_error=True)


@when("click", "#base64-to-json-btn")
def on_base64_to_json(event):
    """Decode Base64(gzip(json)) into pretty JSON."""
    try:
        base64_text = base64_el.value or ""
        if not base64_text.strip():
            set_status("Base64 field is empty; nothing to decode.", is_error=True)
            return
        editor_el.value = extract_base64_logic(base64_text)
        set_status("Decoded Base64 into pretty JSON.")
    except Exception as exc:
        set_status(f"Failed to decode Base64: {exc}", is_error=True)


@when("click", "#gz-to-base64-btn")
def on_gz_to_base64(event):
    """Encode the currently loaded gzip file into Base64 text."""
    try:
        if not _last_gz_bytes:
            set_status("Load or drop a .gz file first.", is_error=True)
            return
        base64_el.value = gzip_to_base64_logic(_last_gz_bytes)
        set_status("Converted loaded .gz data to Base64.")
    except Exception as exc:
        set_status(f"Failed to convert .gz to Base64: {exc}", is_error=True)


@when("click", "#base64-to-gz-btn")
def on_base64_to_gz(event):
    """Decode Base64 text into gzip bytes and download them."""
    try:
        base64_text = base64_el.value or ""
        if not base64_text.strip():
            set_status("Base64 field is empty; nothing to export.", is_error=True)
            return
        gz_bytes = base64_to_gzip_logic(base64_text)
        _download_bytes(_infer_gz_filename(_last_upload_name), gz_bytes, "application/gzip")
        set_status("Decoded Base64 and downloaded .gz file.")
    except Exception as exc:
        set_status(f"Failed to export Base64 as .gz: {exc}", is_error=True)


@when("dragover", "#drop-zone")
def on_drag_over(event):
    """Allow files to be dropped into the drop zone."""
    event.preventDefault()


@when("drop", "#drop-zone")
async def on_drop_file(event):
    """Handle drag-and-drop gzip loading by forwarding to file handler."""
    event.preventDefault()
    files = event.dataTransfer.files
    if not files or files.length == 0:
        set_status("No dropped file detected.", is_error=True)
        return
    await _load_gzip_file(files.item(0))
