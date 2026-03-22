#!/usr/bin/env python3
"""
SaveGzip.py - A utility to extract, pack, verify, and backup gzipped JSON files.
"""

import gzip
import json
import os
import tempfile
import argparse
import hashlib
import logging
import sys
import base64
import binascii
from contextlib import suppress
from pathlib import Path
from shutil import copy2
from time import time

from core_logic import (
    INVALID_BASE64_MESSAGE,
    INVALID_GZIP_MESSAGE,
    base64_to_json_text,
    gz_bytes_to_base64,
    json_text_to_base64,
)

logger = logging.getLogger(__name__)

def _read_text_input(input_path: Path | None) -> str:
    """Read text from a file or stdin when no file is provided."""
    if input_path is None:
        return sys.stdin.read()
    return input_path.read_text(encoding="utf-8")


def _write_bytes_output(output_path: Path, payload: bytes) -> Path:
    """Write bytes payload to output path and return resolved path."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(payload)
    return output_path.resolve()


def _decode_base64_gzip_bytes(b64_text: str) -> bytes:
    """Decode Base64 text to gzip bytes with strict Base64 + header checks.

    This avoids full decompression in `b64-to-gz` so large/untrusted payloads
    do not incur avoidable CPU cost during a pass-through conversion.
    """
    normalized = b64_text.strip()
    try:
        gz_bytes = base64.b64decode(normalized, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(INVALID_BASE64_MESSAGE) from exc

    if len(gz_bytes) < 2 or gz_bytes[:2] != b"\x1f\x8b":
        raise ValueError(INVALID_GZIP_MESSAGE)
    return gz_bytes

def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        # Read in 64kb chunks to prevent memory spikes on massive files
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _gzip_original_filename(gz_path: Path) -> str | None:
    """Return the embedded gzip original filename from the first gzip member."""
    with gz_path.open("rb") as f:
        header = f.read(10)
        if len(header) < 10 or header[0:2] != b"\x1f\x8b":
            return None

        # This inspects only the first gzip member header by design.
        flags = header[3]

        # Skip optional extra field.
        if flags & 0x04:
            xlen_bytes = f.read(2)
            if len(xlen_bytes) < 2:
                return None
            xlen = int.from_bytes(xlen_bytes, "little")
            f.read(xlen)

        # Read optional embedded original filename from the gzip header.
        if flags & 0x08:
            name_bytes = bytearray()
            while True:
                b = f.read(1)
                if not b or b == b"\x00":
                    break
                name_bytes.extend(b)
            if name_bytes:
                try:
                    return name_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    # Latin-1 fallback keeps compatibility with legacy producers.
                    # If exact header-byte round-trip is ever required, preserve name_bytes.
                    return name_bytes.decode("latin-1")

    return None


def _dir_is_writable(directory: Path) -> bool:
    """Best-effort writable check used for clearer pack() warnings."""
    probe: Path | None = None
    try:
        fd, name = tempfile.mkstemp(dir=directory, prefix=".write_probe_")
        os.close(fd)
        probe = Path(name)
        return True
    except OSError:
        return False
    finally:
        if probe is not None:
            with suppress(FileNotFoundError):
                probe.unlink()


def _is_windows_reserved_name(name: str) -> bool:
    """Return True for Windows reserved device names."""
    stem = name.split('.')[0].upper()
    reserved = {
        "CON", "PRN", "AUX", "NUL",
        "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
        "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
    }
    return stem in reserved


def _default_extract_path(gz_path: Path, embedded_name: str | None) -> Path:
    """Resolve a safe default extraction path from gzip metadata."""
    fallback = gz_path.with_suffix('')
    if not embedded_name:
        return fallback

    # Normalize Windows and POSIX separators, then keep basename only.
    basename = embedded_name.replace('\\', '/').split('/')[-1]

    # Ignore unusable names (empty/dot entries or control/NUL characters).
    if basename in {"", ".", ".."}:
        return fallback
    if any(ord(ch) < 0x20 or ch == "\x00" for ch in basename):
        return fallback

    if sys.platform.startswith("win"):
        # Windows rejects these characters and has reserved device names.
        if any(ch in set('<>:"/\\|?*') for ch in basename):
            return fallback
        if basename.endswith((" ", ".")):
            return fallback
        if _is_windows_reserved_name(basename):
            return fallback

    try:
        return gz_path.with_name(basename)
    except ValueError:
        # Defensive fallback for any unsupported filename edge cases.
        return fallback

def extract(gz_path: Path, out_path: Path | None = None, pretty: bool = True) -> Path:
    if out_path is None:
        embedded_name = _gzip_original_filename(gz_path)
        out_path = _default_extract_path(gz_path, embedded_name)

    # Read as text stream
    with gzip.open(gz_path, 'rt', encoding='utf-8') as f:
        text = f.read()

    try:
        obj = json.loads(text)
    except json.JSONDecodeError as e:
        # If not valid JSON, write raw text anyway and alert the user
        out_path.write_text(text, encoding='utf-8')
        raise RuntimeError(f"Extracted file is not valid JSON. Raw text dumped. Error: {e}")

    # Write JSON (pretty or minified) directly to the file
    with out_path.open('w', encoding='utf-8') as f:
        if pretty:
            json.dump(obj, f, indent=2, ensure_ascii=False)
        else:
            json.dump(obj, f, separators=(',', ':'), ensure_ascii=False)

    return out_path.resolve()

def pack(
    json_path: Path,
    out_gz: Path | None = None,
    compresslevel: int = 6,
    mtime: int = 0,
) -> Path:
    if out_gz is None:
        out_gz = Path(f"{json_path}.gz")
    if not 0 <= compresslevel <= 9:
        raise ValueError("compresslevel must be between 0 and 9")
    # Ensure destination directory exists so temp/atomic writes work reliably.
    out_gz.parent.mkdir(parents=True, exist_ok=True)
    if not _dir_is_writable(out_gz.parent):
        logger.warning(
            "Destination directory may be protected/unwritable: %s. "
            "Pack may fail due to antivirus or Controlled Folder Access restrictions.",
            out_gz.parent,
        )

    # Read JSON and validate before doing any compression work
    text = json_path.read_text(encoding='utf-8')
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Input JSON invalid. Cannot pack: {e}")

    # Minify into bytes
    packed = json.dumps(obj, separators=(',', ':'), ensure_ascii=False).encode('utf-8')

    # Atomic write: create a temp filename in destination directory, write gzip to that
    # filename directly, then replace target file in a single operation.
    # Use mkstemp to get a stable filename on disk (works reliably on Windows).
    temp_path: Path | None = None
    try:
        fd, name = tempfile.mkstemp(dir=out_gz.parent, prefix="tmp_pack_", suffix=".gz")
        os.close(fd)
        temp_path = Path(name)

        # Open the raw file and write gzip data through it so we can flush+fsync the raw fd.
        # Passing a raw file object as fileobj avoids handle/locking issues on Windows.
        with open(name, "wb") as raw:
            with gzip.GzipFile(
                fileobj=raw,
                mode="wb",
                filename=json_path.name,
                compresslevel=compresslevel,
                mtime=mtime,
            ) as gz:
                gz.write(packed)
            # Ensure all data is flushed to disk before replacing the target file.
            raw.flush()
            os.fsync(raw.fileno())

        # Sanity check: ensure the temp file still exists before attempting replace.
        if not temp_path.exists():
            raise RuntimeError(f"Temporary gzip file disappeared before replace: {temp_path}")

        # Atomic replace (same directory ensures atomicity on most platforms).
        os.replace(temp_path, out_gz)
    finally:
        # Cleanup leftover temp file. Ignore missing-file races only.
        if temp_path is not None:
            with suppress(FileNotFoundError):
                temp_path.unlink()

    return out_gz.resolve()

def backup(gz_path: Path) -> Path:
    if not gz_path.exists():
        raise FileNotFoundError(f"Cannot backup. File not found: {gz_path}")
    
    ts = int(time())
    dest = gz_path.with_name(f"{gz_path.name}.backup.{ts}")
    copy2(gz_path, dest)
    return dest

def roundtrip(gz_path: Path) -> bool:
    # tempfile.TemporaryDirectory automatically cleans up when the block exits
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        extracted = tmp_path / gz_path.with_suffix('').name
        
        # 1. Extract
        extract(gz_path, extracted)
        
        # 2. Repack
        repacked = tmp_path / f"{extracted.name}.gz"
        pack(extracted, repacked)

        # 3. Compare raw bytes first
        orig_bytes = gz_path.read_bytes()
        new_bytes = repacked.read_bytes()
        
        if orig_bytes == new_bytes:
            return True

        # 4. If bytes differ (gzip timestamps/metadata can cause this), compare JSON content
        with gzip.open(gz_path, 'rt', encoding='utf-8') as f1, gzip.open(repacked, 'rt', encoding='utf-8') as f2:
            orig_obj = json.load(f1)
            new_obj = json.load(f2)
            
        return orig_obj == new_obj

def info(gz_path: Path) -> dict[str, str | int]:
    if not gz_path.exists():
        raise FileNotFoundError(f"File not found: {gz_path}")

    with gzip.open(gz_path, 'rt', encoding='utf-8') as f:
        text = f.read()

    # Default fallback values in case JSON is corrupted
    json_size = len(text.encode('utf-8'))
    keys_top_level = -1

    try:
        obj = json.loads(text)
        minified = json.dumps(obj, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
        json_size = len(minified)
        keys_top_level = len(obj) if isinstance(obj, dict) else -1
    except json.JSONDecodeError:
        pass # Will return the fallback values and still provide file size/hash

    return {
        "path": str(gz_path.resolve()),
        "gz_size": gz_path.stat().st_size,
        "json_size": json_size,
        "sha256_gz": _sha256(gz_path),
        "keys_top_level": keys_top_level,
    }

def main():
    parser = argparse.ArgumentParser(
        description="SaveGzip: A tool to extract, pack, verify, and backup gzipped JSON files."
    )
    subparsers = parser.add_subparsers(dest='command', required=True)

    # Setup CLI commands
    extract_parser = subparsers.add_parser('extract', help='Extract a gzipped JSON file (pretty prints by default).')
    extract_parser.add_argument('file', type=Path, help='The .json.gz file to extract.')
    extract_parser.add_argument('-o', '--output', type=Path, help='Optional output JSON path.')
    extract_parser.add_argument('--no-pretty', action='store_true', help='Disable pretty JSON output.')

    pack_parser = subparsers.add_parser('pack', help='Pack a JSON file into a .gz file (minifies JSON).')
    pack_parser.add_argument('file', type=Path, help='The .json file to pack.')
    pack_parser.add_argument('-o', '--output', type=Path, help='Optional output .gz path.')
    pack_parser.add_argument('-l', '--level', type=int, default=6, help='gzip compression level (0-9).')
    pack_parser.add_argument('--mtime', type=int, default=0, help='gzip mtime. Use 0 for reproducible builds.')

    backup_parser = subparsers.add_parser('backup', help='Create a timestamped backup copy of a file.')
    backup_parser.add_argument('file', type=Path, help='The file to backup.')

    roundtrip_parser = subparsers.add_parser('roundtrip', help='Extract -> Pack -> Verify equivalence.')
    roundtrip_parser.add_argument('file', type=Path, help='The .json.gz file to test.')

    info_parser = subparsers.add_parser('info', help='Print metadata and integrity info for a .json.gz file.')
    info_parser.add_argument('file', type=Path, help='The .json.gz file to inspect.')

    gz_to_b64_parser = subparsers.add_parser('gz-to-b64', help='Read .json.gz bytes and print Base64.')
    gz_to_b64_parser.add_argument('file', type=Path, help='Input .json.gz file path.')

    b64_to_gz_parser = subparsers.add_parser('b64-to-gz', help='Decode Base64 input and write .json.gz output.')
    b64_to_gz_parser.add_argument('-i', '--input', type=Path, help='Optional Base64 text input file (default: stdin).')
    b64_to_gz_parser.add_argument('-o', '--output', type=Path, required=True, help='Output .json.gz file path.')

    b64_to_json_parser = subparsers.add_parser('b64-to-json', help='Decode Base64 input and output pretty JSON.')
    b64_to_json_parser.add_argument('-i', '--input', type=Path, help='Optional Base64 text input file (default: stdin).')
    b64_to_json_parser.add_argument('-o', '--output', type=Path, help='Optional JSON output file (default: stdout).')

    json_to_b64_parser = subparsers.add_parser('json-to-b64', help='Read .json and print Base64 gz payload.')
    json_to_b64_parser.add_argument('file', type=Path, help='Input .json file path.')

    # IDE debug sessions often start scripts without CLI args.
    # Print help and exit cleanly instead of raising argparse SystemExit(2).
    if len(sys.argv) == 1:
        parser.print_help()
        return 0

    args = parser.parse_args()

    # Route commands
    try:
        if args.command == 'extract':
            out = extract(args.file, out_path=args.output, pretty=not args.no_pretty)
            print(f"Successfully extracted to: {out}")
        elif args.command == 'pack':
            out = pack(args.file, out_gz=args.output, compresslevel=args.level, mtime=args.mtime)
            print(f"Successfully packed to: {out}")
        elif args.command == 'backup':
            dest = backup(args.file)
            print(f"Backup created at: {dest}")
        elif args.command == 'roundtrip':
            ok = roundtrip(args.file)
            print("Roundtrip OK: Data integrity verified." if ok else "Roundtrip mismatch: Data integrity failed.")
        elif args.command == 'info':
            print(json.dumps(info(args.file), indent=2))
        elif args.command == 'gz-to-b64':
            print(gz_bytes_to_base64(args.file.read_bytes()))
        elif args.command == 'b64-to-gz':
            b64_text = _read_text_input(args.input)
            out = _write_bytes_output(args.output, _decode_base64_gzip_bytes(b64_text))
            print(f"Successfully wrote gzip to: {out}")
        elif args.command == 'b64-to-json':
            b64_text = _read_text_input(args.input)
            pretty_json = base64_to_json_text(b64_text)
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(pretty_json, encoding='utf-8')
                print(f"Successfully wrote JSON to: {args.output.resolve()}")
            else:
                print(pretty_json)
        elif args.command == 'json-to-b64':
            json_text = args.file.read_text(encoding='utf-8')
            print(json_text_to_base64(json_text, filename=args.file.name, mtime=0))
    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0

if __name__ == '__main__':
    sys.exit(main())
