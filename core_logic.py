"""Core save conversion logic (pure Python, no DOM or filesystem access)."""

from __future__ import annotations

import base64
import binascii
import gzip
import json

INVALID_BASE64_MESSAGE = "Invalid Base64 input."
INVALID_GZIP_MESSAGE = "Invalid gzip data."
INVALID_JSON_MESSAGE = "Invalid JSON input."


CORE_SLOT_ENVELOPE_KEYS = (
    "save_version",
    "save_kind",
    "saved_at_utc",
    "slot_name",
    "player",
    "world",
)
CORE_GLOBAL_ENVELOPE_KEYS = (
    "save_version",
    "lifetime_stats",
    "achievements",
    "meta_unlocks",
    "streak_chests",
)


def _normalize_base64_text(b64: str) -> str:
    """Remove transport whitespace so wrapped Base64 still decodes reliably."""
    return "".join(b64.split())


def _assert_valid_gzip(gz_bytes: bytes) -> None:
    """Validate gzip framing/integrity and raise standardized error on failure."""
    try:
        # Fully reading through gzip members validates framing and trailers.
        gzip.decompress(gz_bytes)
    except (OSError, EOFError, ValueError) as exc:
        raise ValueError(INVALID_GZIP_MESSAGE) from exc


def _json_payload_bytes(json_str: str) -> bytes:
    """Parse and minify JSON text to deterministic UTF-8 bytes.

    Matches core/save packing conventions:
    - separators=(",", ":")
    - default ensure_ascii=True behavior
    - bytes via .encode() (UTF-8)
    """
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise ValueError(INVALID_JSON_MESSAGE) from exc

    minified_json = json.dumps(data, separators=(",", ":"))
    return minified_json.encode()


def _repack_gzip_bytes(raw_json_bytes: bytes) -> bytes:
    """Compress payload exactly like gzip.compress(..., level=9, mtime=0)."""
    return gzip.compress(raw_json_bytes, compresslevel=9, mtime=0)


def parity_diff_reason(original_gz_bytes: bytes, repacked_gz_bytes: bytes) -> str | None:
    """Best-effort QA hint for first likely byte-parity mismatch reason."""
    if original_gz_bytes == repacked_gz_bytes:
        return None

    if len(original_gz_bytes) >= 10 and len(repacked_gz_bytes) >= 10:
        orig_flags = original_gz_bytes[3]
        new_flags = repacked_gz_bytes[3]
        if (orig_flags ^ new_flags) & 0x08:
            return "gzip header filename"

        # gzip mtime is bytes [4:8] little-endian.
        if original_gz_bytes[4:8] != repacked_gz_bytes[4:8]:
            return "mtime/compression"

    try:
        if gzip.decompress(original_gz_bytes) != gzip.decompress(repacked_gz_bytes):
            return "JSON escaping"
    except (OSError, EOFError, ValueError):
        return "mtime/compression"

    return "mtime/compression"


def extract_logic(gz_bytes: bytes) -> str:
    """Decompress gzip bytes and return pretty-printed JSON text."""
    try:
        raw = gzip.decompress(gz_bytes)
    except (OSError, EOFError, ValueError) as exc:
        raise ValueError(INVALID_GZIP_MESSAGE) from exc

    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(INVALID_JSON_MESSAGE) from exc

    # Preserve keys and values exactly; only whitespace/formatting changes.
    return json.dumps(data, indent=2, ensure_ascii=False)


def pack_logic(json_str: str, filename: str = "save.json", mtime: int = 0) -> bytes:
    """Minify JSON text and return deterministic gzip-compressed bytes.

    Note: `filename`/`mtime` are intentionally ignored for converter parity with
    core save packing (`gzip.compress(..., compresslevel=9, mtime=0)`).
    """
    del filename, mtime
    payload = _json_payload_bytes(json_str)
    return _repack_gzip_bytes(payload)


def qa_roundtrip_parity(json_str: str, original_gz_bytes: bytes) -> tuple[bool, str | None]:
    """Optional QA-only parity check helper for decode->repack validation."""
    repacked = pack_logic(json_str)
    reason = parity_diff_reason(original_gz_bytes, repacked)
    return reason is None, reason


def gz_bytes_to_base64(gz_bytes: bytes) -> str:
    """Encode raw gzip bytes as a Base64 ASCII string."""
    return base64.b64encode(gz_bytes).decode("ascii")


def base64_to_gz_bytes(b64: str) -> bytes:
    """Decode Base64 text to gzip bytes with permissive Base64 + gzip validation."""
    normalized = _normalize_base64_text(b64)
    try:
        gz_bytes = base64.b64decode(normalized)
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
