# DrugBankNER Automation (Shell Wrapper)

This repository contains a simple automation wrapper that runs the upstream **DrugBankNER** pipeline end-to-end:

- clone (or update) the upstream `KoslickiLab/DrugBankNER` repository
- create/reuse a Conda environment and install dependencies
- download the latest DrugBank “all full database” XML (via HTTP Basic Auth)
- run `perform_NER.py` and `look_for_identifiers.py` with your `KG_VERSION`
- verify `data/DrugBank_aligned_with_KG2.json` exists
- copy the final JSON back to the directory where you launched the script

---

## Files

- `run_drugbankner_pipeline.sh`  
  End-to-end automation script.

- `drugbankner.env`  

  Users must edit this file and replace placeholders with their own values.

---

## Prerequisites

### Required CLI tools
Make sure these are installed and available on your `PATH`:

- `git`
- `curl`
- `unzip`
- `conda` (Miniconda / Anaconda / Mambaforge)

### Optional (GPU/CUDA)
If `nvidia-smi` is available, the script will attempt to detect your CUDA major version and install an appropriate CuPy wheel (`cupy-cuda11x`, `cupy-cuda12x`, etc.).  
If `nvidia-smi` is not available, CuPy installation is skipped automatically.

---

## 1) Configure `drugbankner.env`

Open `drugbankner.env` and set these variables:

```bash
# DrugBank credentials (used for HTTP basic auth download)
DRUGBANK_EMAIL="your@email"
DRUGBANK_PASSWORD="yourpassword"

# Where to clone + run (must be writable)
WORKDIR="$HOME/work/drugbankner_run"

# KG version passed to DrugBankNER scripts
KG_VERSION="2.10.2"
```

### Passwords with special characters (important)
If your DrugBank password contains shell special characters (especially `$`), escape them **inside the quotes**.

Example:

```bash
DRUGBANK_PASSWORD="my\$password"
```

---

## 2) Run the pipeline

From the directory that contains `run_drugbankner_pipeline.sh` and `drugbankner.env`:

```bash
chmod +x run_drugbankner_pipeline.sh
set -a; source ./drugbankner.env; set +a
./run_drugbankner_pipeline.sh
```

What this does:
- `set -a` exports all variables loaded from `drugbankner.env` so the script can read them.
- the script then runs using those configuration values.

---

## Outputs

### Main output (inside the cloned upstream repo)
After a successful run, the output JSON is generated here:

```bash
$WORKDIR/DrugBankNER/data/DrugBank_aligned_with_KG2.json
```

### Convenience copy (where you launched the script)
At the end, the script copies the JSON to the directory where you launched the script:

```bash
./DrugBank_aligned_with_KG2.json
```

---

### Re-running
The script is designed to be re-runnable:
- it reuses the existing clone (and pulls updates)
- it reuses the conda env if it already exists
- it skips downloading the ZIP if it already exists in `DrugBankNER/data/`

If you want a completely fresh run, delete `WORKDIR` and rerun.

---