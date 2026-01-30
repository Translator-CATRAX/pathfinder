# curie_ngd_builder

Builds a `curie_ngd` SQLite database for a specified KG2 version, using a PloverDB instance for KG lookups and Redis as a working cache.

---

## Requirements

### Redis
A **running Redis server is required** and must be reachable from the machine running this script.

Default configuration:
- Host: `localhost`
- Port: `6379`
- DB index: `0`

You can override these using CLI arguments.

### Python packages
All required Python dependencies are listed in `requirements.txt`. Install them with:

```bash
pip install -r requirements.txt
```

### SSH access
The script downloads and uploads SQLite files via SSH.

Authentication options:
- SSH agent / default keys (recommended)
- Explicit key file via `--ssh-key`
- Password via `--ssh-password` or the `SSH_PASSWORD` environment variable

---

## Usage

### Minimal example (mandatory arguments)

```bash
python curie_ngd_builder.py \
  --kg-version 2.10.2 \
  --plover-url https://kg2cploverdb.test.transltr.io
```

---

## Command-line arguments

### Required
- `--kg-version VERSION`  
  Knowledge graph version in `X.Y.Z` format (e.g. `2.10.2`).

- `--plover-url URL`  
  Base URL of the PloverDB instance.

### Redis options
- `--redis-host HOST` (default: `localhost`)
- `--redis-port PORT` (default: `6379`)
- `--redis-db INDEX` (default: `0`)

### Remote DB host / SSH options
- `--db-host HOST` (default: `arax-databases.rtx.ai`)
- `--db-username USER` (default: `rtxconfig`)
- `--db-port PORT` (default: `22`)
- `--ssh-key PATH`  
  Path to SSH private key file (optional).
- `--ssh-password PASSWORD`  
  SSH password (optional). Can also be provided via `SSH_PASSWORD`.

### Other options
- `--out-dir PATH`  
  Directory where downloaded and generated SQLite files are stored (default: current directory).
- `--num-pubmed-articles FLOAT`  
  Number of PubMed citations used for NGD normalization (default: `3.5e7`).
- `--avg-mesh-terms-per-article INT`  
  Average number of MeSH terms per article (default: `20`).

---

## Outputs

### Local files
Stored in `--out-dir`:
- `curie_to_pmids_v1.0_KG<kg-version>.sqlite`
- `curie_ngd_v1.0_KG<kg-version>.sqlite`

### Remote upload
Uploaded to the remote host at:
```
~/KG<kg-version>/curie_ngd_v1.0_KG<kg-version>.sqlite
```

---

## Notes and troubleshooting

- **KG version mismatch**  
  The script queries PloverDB for its KG2 version and exits if it does not match `--kg-version`.

- **Redis reuse**  
  Redis stores a `version` key; if it matches the requested KG version, reloading may be skipped.

- **Password-based SSH**  
  If using passwords instead of keys:
  ```bash
  export SSH_PASSWORD="your_password"
  ```

- **Runtime considerations**  
  NGD computation can be time-consuming and resource-intensive depending on data size and environment.

---
