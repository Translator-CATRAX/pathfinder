# curie_ngd_builder

Builds a `curie_ngd` SQLite database for a specified KGX version, using PloverDB or Gandalf instance for KG lookups and Redis as a working cache.

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
python curie_ngd_builder.py --kgx-path <PATH>
```

---

## Command-line arguments

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

## Notes and troubleshooting

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
