"""Core save conversion logic (pure Python, no DOM or filesystem access)."""

from __future__ import annotations

import gzip
import io
import json
from base64 import b64decode, b64encode


def extract_logic(gz_bytes: bytes) -> str:
    """Decompress gzip bytes and return pretty-printed JSON text."""
    with io.BytesIO(gz_bytes) as source:
        with gzip.GzipFile(fileobj=source, mode="rb") as gz_file:
            raw = gz_file.read()

    data = json.loads(raw.decode("utf-8"))
    return json.dumps(data, indent=2, ensure_ascii=False)


def gzip_to_base64_logic(gz_bytes: bytes) -> str:
    """Encode raw gzip bytes to a Base64 ASCII string."""
    return b64encode(gz_bytes).decode("ascii")


def base64_to_gzip_logic(base64_str: str) -> bytes:
    """Decode a Base64 string into raw gzip bytes."""
    normalized = "".join(base64_str.split())
    return b64decode(normalized, validate=True)


def extract_base64_logic(base64_str: str) -> str:
    """Decode Base64-encoded gzip data and return pretty JSON text."""
    return extract_logic(base64_to_gzip_logic(base64_str))


def pack_logic(json_str: str, filename: str = "save.json") -> bytes:
    """Minify JSON text and return gzip-compressed bytes.

    The filename is written into the gzip member header so metadata-aware
    tooling can preserve and round-trip original-name semantics.
    """
    data = json.loads(json_str)
    minified_json = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    payload = minified_json.encode("utf-8")

    with io.BytesIO() as output:
        with gzip.GzipFile(
            filename=filename,
            fileobj=output,
            mode="wb",
            mtime=0,
        ) as gz_file:
            gz_file.write(payload)
        return output.getvalue()


def pack_base64_logic(json_str: str, filename: str = "save.json") -> str:
    """Minify JSON, gzip it, and return a Base64 string."""
    return gzip_to_base64_logic(pack_logic(json_str, filename=filename))
