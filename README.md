# Gzip-encoder-decoder-python-system
Gzip encoder/decoder made in python

## Usage

```bash
python3 main.py extract file.json.gz -o file.json
python3 main.py pack file.json -o file.json.gz --level 9 --mtime 0
python3 main.py roundtrip file.json.gz
python3 main.py info file.json.gz
```
