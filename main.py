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
import sys
from pathlib import Path
from shutil import copy2
from time import time

def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        # Read in 64kb chunks to prevent memory spikes on massive files
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()

def extract(gz_path: Path, out_path: Path | None = None, pretty: bool = True) -> Path:
    if out_path is None:
        out_path = gz_path.with_suffix('')  # remove .gz

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

    # Read JSON and validate before doing any compression work
    text = json_path.read_text(encoding='utf-8')
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Input JSON invalid. Cannot pack: {e}")

    # Minify into bytes
    packed = json.dumps(obj, separators=(',', ':'), ensure_ascii=False).encode('utf-8')

    # Atomic write: write to a temp file in the destination directory, then replace.
    # NamedTemporaryFile with delete=False keeps Windows compatibility for reopen/replace.
    with tempfile.NamedTemporaryFile(
        mode='wb',
        delete=False,
        dir=out_gz.parent,
        prefix="tmp_pack_",
        suffix=".gz",
    ) as tmp_file:
        temp_file = Path(tmp_file.name)

    try:
        with temp_file.open('wb') as raw_f:
            with gzip.GzipFile(fileobj=raw_f, mode='wb', compresslevel=compresslevel, mtime=mtime) as f:
                f.write(packed)
        os.replace(temp_file, out_gz)
    finally:
        # Cleanup in case os.replace failed
        if temp_file.exists():
            temp_file.unlink()

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
    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0

if __name__ == '__main__':
    sys.exit(main())
