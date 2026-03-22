"""PyScript web bridge: connects DOM events to pure core_logic functions."""

from __future__ import annotations

import io

from js import Blob, Uint8Array, URL, document as js_document
from pyodide.ffi import to_js
from pyscript import document, when

from core_logic import extract_logic, pack_logic


status_el = document.querySelector("#status")
editor_el = document.querySelector("#editor")
file_input_el = document.querySelector("#file-upload")


def set_status(message: str, is_error: bool = False) -> None:
    """Render status text in the UI."""
    status_el.innerText = message
    status_el.style.color = "#b00020" if is_error else "#1f2937"


def _infer_json_filename(upload_name: str) -> str:
    """Map uploaded filename to a stable JSON name for gzip header metadata."""
    if upload_name.lower().endswith(".gz"):
        return f"{upload_name[:-3]}.json"
    return "save.json"


@when("change", "#file-upload")
async def on_file_selected(event):
    """Load a selected gzip save file, decode it, and place JSON in editor."""
    try:
        files = event.target.files
        if not files or files.length == 0:
            set_status("No file selected.", is_error=True)
            return

        file_obj = files.item(0)
        buffer = await file_obj.arrayBuffer()
        gz_bytes = bytes(Uint8Array.new(buffer).to_py())

        # Keep browser-side file work in-memory; core logic remains pure.
        with io.BytesIO(gz_bytes) as _stream:
            json_text = extract_logic(_stream.getvalue())

        editor_el.value = json_text
        set_status(f"Loaded: {file_obj.name}")
    except Exception as exc:  # Surface parse/decompression errors to user.
        set_status(f"Failed to load file: {exc}", is_error=True)


@when("click", "#download-btn")
def on_download_clicked(event):
    """Read JSON from editor, repack as gzip bytes, and trigger download."""
    try:
        json_text = editor_el.value or ""
        if not json_text.strip():
            set_status("Editor is empty; nothing to pack.", is_error=True)
            return

        upload_name = file_input_el.files.item(0).name if file_input_el.files.length else ""
        packed_bytes = pack_logic(json_text, filename=_infer_json_filename(upload_name))

        uint8_data = Uint8Array.new(to_js(memoryview(packed_bytes)))
        blob = Blob.new([uint8_data], to_js({"type": "application/gzip"}))

        download_url = URL.createObjectURL(blob)
        anchor = js_document.createElement("a")
        anchor.href = download_url
        anchor.download = "save.gz"
        js_document.body.appendChild(anchor)
        anchor.click()
        anchor.remove()
        URL.revokeObjectURL(download_url)

        set_status("Packed and downloaded save.gz")
    except Exception as exc:  # Surface JSON validation/compression errors.
        set_status(f"Failed to pack file: {exc}", is_error=True)
