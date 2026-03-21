#!/usr/bin/env python3
"""
SaveGzip.py - A utility to extract, pack, verify, and backup gzipped JSON files.
"""

import gzip
import json
import os
import tempfile
import argparse
from pathlib import Path
from shutil import copy2
from time import time

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

    return out_path

def pack(json_path: Path, out_gz: Path | None = None, compresslevel: int = 6) -> Path:
    if out_gz is None:
        out_gz = Path(f"{json_path}.gz")

    # Read JSON and validate before doing any compression work
    text = json_path.read_text(encoding='utf-8')
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Input JSON invalid. Cannot pack: {e}")

    # Minify into bytes
    packed = json.dumps(obj, separators=(',', ':'), ensure_ascii=False).encode('utf-8')

    # Atomic write: Write to temp file in the same directory, then replace
    temp_fd, temp_path = tempfile.mkstemp(dir=out_gz.parent, prefix="._tmp_pack_")
    os.close(temp_fd) 
    temp_file = Path(temp_path)

    try:
        with gzip.open(temp_file, 'wb', compresslevel=compresslevel) as f:
            f.write(packed)
        os.replace(temp_file, out_gz)
    finally:
        # Cleanup in case os.replace failed
        if temp_file.exists():
            temp_file.unlink()

    return out_gz

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

def main():
    parser = argparse.ArgumentParser(
        description="SaveGzip: A tool to extract, pack, verify, and backup gzipped JSON files."
    )
    subparsers = parser.add_subparsers(dest='command', required=True)

    # Setup CLI commands
    extract_parser = subparsers.add_parser('extract', help='Extract a gzipped JSON file (pretty prints by default).')
    extract_parser.add_argument('file', type=Path, help='The .json.gz file to extract.')

    pack_parser = subparsers.add_parser('pack', help='Pack a JSON file into a .gz file (minifies JSON).')
    pack_parser.add_argument('file', type=Path, help='The .json file to pack.')

    backup_parser = subparsers.add_parser('backup', help='Create a timestamped backup copy of a file.')
    backup_parser.add_argument('file', type=Path, help='The file to backup.')

    roundtrip_parser = subparsers.add_parser('roundtrip', help='Extract -> Pack -> Verify equivalence.')
    roundtrip_parser.add_argument('file', type=Path, help='The .json.gz file to test.')

    args = parser.parse_args()

    # Route commands
    try:
        if args.command == 'extract':
            out = extract(args.file)
            print(f"Successfully extracted to: {out}")
        elif args.command == 'pack':
            out = pack(args.file)
            print(f"Successfully packed to: {out}")
        elif args.command == 'backup':
            dest = backup(args.file)
            print(f"Backup created at: {dest}")
        elif args.command == 'roundtrip':
            ok = roundtrip(args.file)
            print("Roundtrip OK: Data integrity verified." if ok else "Roundtrip mismatch: Data integrity failed.")
    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0

if __name__ == '__main__':
    exit(main())
