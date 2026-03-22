"""Core save conversion logic (pure Python, no DOM or filesystem access)."""

from __future__ import annotations

import gzip
import io
import json


def extract_logic(gz_bytes: bytes) -> str:
    """Decompress gzip bytes and return pretty-printed JSON text."""
    with io.BytesIO(gz_bytes) as source:
        with gzip.GzipFile(fileobj=source, mode="rb") as gz_file:
            raw = gz_file.read()

    data = json.loads(raw.decode("utf-8"))
    return json.dumps(data, indent=2, ensure_ascii=False)


def pack_logic(json_str: str, filename: str = "save.json") -> bytes:
    """Minify JSON text and return gzip-compressed bytes.

    The filename is written into the gzip member header so metadata-aware
    tooling can preserve and round-trip original-name semantics.
    """
    data = json.loads(json_str)
    minified_json = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    payload = minified_json.encode("utf-8")

    with io.BytesIO() as output:
        with gzip.GzipFile(filename=filename, fileobj=output, mode="wb") as gz_file:
            gz_file.write(payload)
        return output.getvalue()
