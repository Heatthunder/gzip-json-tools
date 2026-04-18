# gzip-json-tools

**A lightweight command-line utility for managing gzipped JSON save files.**

## Purpose
Many modern games and applications store data as **minified JSON** compressed with **Gzip** to save space. This makes manual editing nearly impossible without the right tools.

**Specifically built for:** [Text-Adventure-Game-REBUILT](https://github.com/Heatthunder/Text-Adventure-Game-REBUILT) and [REBUILT-Web-Build](https://github.com/Heatthunder/Text-Adventure-Game-REBUILT-Web-Build)

This utility provides a reliable "roundtrip" workflow for developers and modders to:
1. **Decompress** and "pretty-print" JSON for easy manual editing.
2. **Recompress** edited JSON back into the specific Gzip format the application expects.
3. **Verify** that the data remains valid and uncorrupted through automated integrity checks.

---

## Disclaimer
**Use this tool at your own risk.** Modifying game saves can lead to data loss or character corruption. Always keep an original, untouched backup of your save files in a separate folder before using this utility. The author is not responsible for any damage caused by the use of this software.

**Specifically built for:** [Text-Adventure-Game-REBUILT](https://github.com/Heatthunder/Text-Adventure-Game-REBUILT) and [REBUILT-Web-Build](https://github.com/Heatthunder/Text-Adventure-Game-REBUILT-Web-Build)

---

## Requirements

* **Python 3.10+** (3.11+ recommended)
* **Standard Library Only**: No third-party packages (like `pip install`) are required.

## Run outside your IDE

Open a terminal (Command Prompt, PowerShell, macOS Terminal, Linux shell), then:

1. **Go to the project folder:**
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

If you run from an IDE debugger, make sure you pass command arguments (for example: `pack your_save.json -o your_save.json.gz`).

## Quick start (first time with your game save)

If your game already creates a `.json.gz` save, inspect it directly:

```bash
python3 main.py info your_save.json.gz
```

If your game save is plain JSON (not gzipped) and you want to create gzip first:

```bash
python3 main.py pack your_save.json -o your_save.json.gz --mtime 0
```

Then verify the roundtrip behavior:

```bash
python3 main.py roundtrip your_save.json.gz
```

And create a backup before editing:

```bash
python3 main.py backup your_save.json.gz
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

### Deterministic gzip output (CLI + Web)

- **CLI**: `pack` supports `--mtime` and defaults to `0`, so repeated packing of
  the same JSON produces stable gzip timestamps. Passing `--mtime 0` explicitly
  is recommended for clarity in scripts/CI.
- **Web (PyScript UI)**: JSON repacking uses deterministic packing with
  `mtime=0` for JSON→gzip and JSON→Base64 flows.

### Web build updates

- The web UI now uses a **dark theme** by default for reduced eye strain during
  long editing sessions.
- A visible **disclaimer note** is shown at the top of the web app to remind
  users to keep backups and use save editing tools carefully.

### Simple how-to-use guide (Web build)

1. Open `index.html` in a PyScript-compatible environment and load the web UI.
2. Drop a `.json.gz` file, `.json` file, or Base64 text into the dropzone.
3. Edit the JSON in the editor as needed.
4. Convert using **JSON → Base64**, **Base64 → JSON**, or download a rebuilt
   `.json.gz` file using the download buttons.

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
- Use deterministic packing (`--mtime 0` in CLI; fixed `mtime=0` in web) for reproducible gzip output.
- `extract` uses the embedded gzip original filename when available, but sanitizes it and falls back to the `.gz`-stripped name when unsafe.
- Embedded filenames are read from the **first gzip member** only (concatenated multi-member `.gz` files are not fully scanned for naming metadata).
- Filename rules can vary across filesystems; when embedded metadata is unsafe for the current platform, extraction falls back to the `.gz`-stripped filename.
- If byte-for-byte output differs after repacking, use `roundtrip` to confirm the JSON data still matches.
- Keep an untouched original save in a separate folder so you can recover quickly if an edit breaks loading.

## Troubleshooting

- **"python3: command not found"**: try `python` instead.
- **"Error: Input JSON invalid"**: fix JSON syntax first (missing commas, bad quotes, etc.).
- **"Error: File not found"**: double-check the path and run command from the correct folder.
- **Windows path issues**: wrap paths with spaces in double quotes (for example: `python main.py pack "my save.json" -o "my save.json.gz"`).
- **`SystemExit: 2` / `the following arguments are required: command`**: the script was started without a subcommand. Add one of: `extract`, `pack`, `backup`, `roundtrip`, `info`.
- **Temp file errors during `pack` on Windows**: run from a normal local folder (not cloud-synced), and retry. Some sync/AV tools can interfere with temporary files; the tool now warns when the destination folder appears protected/unwritable.

## License

This project is licensed under the **Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)**.

### Quick Summary
* **Share** — You can copy and redistribute the material in any medium or format.
* **Adapt** — You can remix, transform, and build upon the material.
* **Attribution** — You must give appropriate credit and link to the license.
* **NonCommercial** — You may not use this work for commercial purposes.
* **ShareAlike** — If you modify this work, you must distribute it under this same license.

---

### How to Attribute
If you use or adapt this work, please use the following format:
> "**[Project Title]**" by **[Your Name/Org]**, used under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/).

*For the full legal terms, please see the [LICENSE.md](./LICENSE.md) file.*
