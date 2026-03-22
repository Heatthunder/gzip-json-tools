"""Core save conversion logic (pure Python, no DOM or filesystem access)."""

from __future__ import annotations

import base64
import binascii
import gzip
import io
import json

INVALID_BASE64_MESSAGE = "Invalid Base64 input."
INVALID_GZIP_MESSAGE = "Invalid gzip data."
INVALID_JSON_MESSAGE = "Invalid JSON input."


def _assert_valid_gzip(gz_bytes: bytes) -> None:
    """Validate gzip framing/integrity and raise standardized error on failure."""
    try:
        with io.BytesIO(gz_bytes) as source:
            with gzip.GzipFile(fileobj=source, mode="rb") as gz_file:
                while gz_file.read(65536):
                    pass
    except (OSError, EOFError) as exc:
        raise ValueError(INVALID_GZIP_MESSAGE) from exc


def extract_logic(gz_bytes: bytes) -> str:
    """Decompress gzip bytes and return pretty-printed JSON text."""
    try:
        with io.BytesIO(gz_bytes) as source:
            with gzip.GzipFile(fileobj=source, mode="rb") as gz_file:
                raw = gz_file.read()
    except (OSError, EOFError) as exc:
        raise ValueError(INVALID_GZIP_MESSAGE) from exc

    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(INVALID_JSON_MESSAGE) from exc

    return json.dumps(data, indent=2, ensure_ascii=False)


def pack_logic(json_str: str, filename: str = "save.json", mtime: int = 0) -> bytes:
    """Minify JSON text and return gzip-compressed bytes.

    The filename is written into the gzip member header so metadata-aware
    tooling can preserve and round-trip original-name semantics.
    """
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise ValueError(INVALID_JSON_MESSAGE) from exc

    minified_json = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    payload = minified_json.encode("utf-8")

    with io.BytesIO() as output:
        with gzip.GzipFile(filename=filename, fileobj=output, mode="wb", mtime=mtime) as gz_file:
            gz_file.write(payload)
        return output.getvalue()


def gz_bytes_to_base64(gz_bytes: bytes) -> str:
    """Encode raw gzip bytes as a Base64 ASCII string."""
    return base64.b64encode(gz_bytes).decode("ascii")


def base64_to_gz_bytes(b64: str) -> bytes:
    """Decode Base64 text to gzip bytes with strict Base64 and gzip validation."""
    normalized = b64.strip()
    try:
        gz_bytes = base64.b64decode(normalized, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(INVALID_BASE64_MESSAGE) from exc

    _assert_valid_gzip(gz_bytes)
    return gz_bytes


def base64_to_json_text(b64: str) -> str:
    """Decode Base64 -> gzip -> pretty JSON text."""
    gz_bytes = base64_to_gz_bytes(b64)
    return extract_logic(gz_bytes)


def json_text_to_base64(json_str: str, filename: str = "save.json", mtime: int = 0) -> str:
    """Convert JSON text -> minified gzip payload -> Base64 text."""
    gz_bytes = pack_logic(json_str, filename=filename, mtime=mtime)
    return gz_bytes_to_base64(gz_bytes)
