# Gzip-encoder-decoder-python-system

A small command-line utility to extract, pack, verify, and inspect gzipped JSON save files.

## Requirements

- Python 3.10+ (3.11+ recommended)
- No third-party packages required

## Run outside your IDE

Open a terminal (Command Prompt, PowerShell, macOS Terminal, Linux shell), then:

1. Go to the project folder:

```bash
cd /path/to/Gzip-encoder-decoder-python-system
```

2. Check Python is available:

```bash
python3 --version
```

If `python3` is not recognized on Windows, use:

```bash
python --version
```

3. Show command help:

```bash
python3 main.py -h
```

## Usage

### Extract a `.json.gz` file to JSON

```bash
python3 main.py extract file.json.gz -o file.json
```

### Pack a JSON file back to gzip

```bash
python3 main.py pack file.json -o file.json.gz --level 9 --mtime 0
```

### Verify roundtrip integrity

```bash
python3 main.py roundtrip file.json.gz
```

### Inspect file metadata and hash

```bash
python3 main.py info file.json.gz
```

### Create a backup before editing

```bash
python3 main.py backup file.json.gz
```

## Command reference

```text
extract   Extract a gzipped JSON file (pretty output by default)
pack      Pack a JSON file into gzip (minified JSON)
backup    Create a timestamped backup copy of a file
roundtrip Extract -> Pack -> Verify equivalence
info      Print metadata and integrity info
```

## Tips for game-save workflows

- Always run `backup` before manual save edits.
- Use `--mtime 0` while packing for reproducible gzip output.
- If byte-for-byte output differs after repacking, use `roundtrip` to confirm the JSON data still matches.

## Troubleshooting

- **"python3: command not found"**: try `python` instead.
- **"Error: Input JSON invalid"**: fix JSON syntax first (missing commas, bad quotes, etc.).
- **"Error: File not found"**: double-check the path and run command from the correct folder.
