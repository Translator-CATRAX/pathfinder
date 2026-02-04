#!/usr/bin/env bash
set -euo pipefail

START_DIR="$(pwd -P)"
# ---- Config (override via env) ----
REPO_URL="${REPO_URL:-https://github.com/KoslickiLab/DrugBankNER}"
WORKDIR="${WORKDIR:-$PWD/drugbankner_run}"
ENV_NAME="${ENV_NAME:-drug_bank_NER}"
PY_VER="${PY_VER:-3.11.10}"

# DrugBank credentials (required to programmatically download)
: "${DRUGBANK_EMAIL:?Set DRUGBANK_EMAIL}"
: "${DRUGBANK_PASSWORD:?Set DRUGBANK_PASSWORD}"
: "${KG_VERSION:?Set KG_VERSION (e.g. 2.10.2) in drugbankner.env}"

# ---- Helpers ----
need() { command -v "$1" >/dev/null 2>&1 || { echo "Missing required command: $1" >&2; exit 1; }; }

echo "==> Checking base tools..."
need git
need curl
need unzip

# conda is expected (miniconda/anaconda/mambaforge). If you prefer micromamba, adapt below.
need conda

mkdir -p "$WORKDIR"
cd "$WORKDIR"

echo "==> Cloning repo (or updating if already present)..."
if [[ ! -d "DrugBankNER/.git" ]]; then
  git clone "$REPO_URL" DrugBankNER
else
  (cd DrugBankNER && git pull --ff-only)
fi

cd DrugBankNER
mkdir -p data

echo "==> Creating conda env if missing: ${ENV_NAME} (python ${PY_VER})"
if ! conda env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
  conda create -y -n "$ENV_NAME" "python==${PY_VER}"
fi

echo "==> Installing Python deps (pinned per repo README)..."
conda run -n "$ENV_NAME" python -m pip install --upgrade pip
conda run -n "$ENV_NAME" pip install \
  "xmltodict==0.14.2" \
  "pandas==2.2.3" \
  "spacy==3.7.0" \
  "scispacy==0.5.5" \
  "paramiko"

echo "==> Installing CuPy (GPU acceleration) if CUDA detected..."
if command -v nvidia-smi >/dev/null 2>&1; then
  CUDA_LINE="$(nvidia-smi 2>/dev/null | grep -oE 'CUDA Version: [0-9]+\.[0-9]+' | head -n1 || true)"
  if [[ -n "$CUDA_LINE" ]]; then
    CUDA_MAJOR="$(echo "$CUDA_LINE" | awk '{print $3}' | cut -d. -f1)"
    case "$CUDA_MAJOR" in
      11) CUPY_PKG="cupy-cuda11x" ;;
      12) CUPY_PKG="cupy-cuda12x" ;;
      13) CUPY_PKG="cupy-cuda13x" ;;
      *)  CUPY_PKG="" ;;
    esac
    if [[ -n "$CUPY_PKG" ]]; then
      echo "    Detected $CUDA_LINE -> installing ${CUPY_PKG}"
      conda run -n "$ENV_NAME" pip install "$CUPY_PKG"
    else
      echo "    Detected $CUDA_LINE but no matching prebuilt CuPy wheel rule; skipping CuPy."
    fi
  else
    echo "    nvidia-smi present but CUDA version not found; skipping CuPy."
  fi
else
  echo "    No nvidia-smi detected; skipping CuPy."
fi

echo "==> Installing scispaCy models (pip-installable model packages)..."
conda run -n "$ENV_NAME" pip install \
  "https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.3/en_core_sci_lg-0.5.3.tar.gz" \
  "https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.3/en_core_sci_scibert-0.5.3.tar.gz"

echo "==> Downloading DrugBank full XML (official programmatic download endpoint)..."
ZIP_PATH="data/drugbank_all_full.zip"
if [[ ! -f "$ZIP_PATH" ]]; then
  # DrugBank states downloads are accessible via HTTP basic auth; follow redirects with -L
  curl -Lfv -o "$ZIP_PATH" -u "${DRUGBANK_EMAIL}:${DRUGBANK_PASSWORD}" \
    "https://go.drugbank.com/releases/latest/downloads/all-full-database"
else
  echo "    Found existing $ZIP_PATH; skipping download."
fi

echo "==> Unzipping DrugBank XML into ./data ..."
unzip -o "$ZIP_PATH" -d data >/dev/null

# Try to standardize a predictable name if the repo scripts expect one
XML_FOUND="$(ls -1 data/*.xml 2>/dev/null | head -n1 || true)"
if [[ -n "$XML_FOUND" ]]; then
  ln -sf "$(basename "$XML_FOUND")" "data/drugbank.xml"
  echo "    Using XML: $XML_FOUND (also linked as data/drugbank.xml)"
else
  echo "ERROR: No .xml found in data/ after unzip. Check ZIP contents." >&2
  exit 1
fi

echo "==> Running pipeline scripts..."
conda run -n "$ENV_NAME" python perform_NER.py --kg-version "$KG_VERSION"
conda run -n "$ENV_NAME" python look_for_identifiers.py --kg-version "$KG_VERSION"

OUT_JSON="data/DrugBank_aligned_with_KG2.json"
echo "==> Verifying output: $OUT_JSON"
if [[ -s "$OUT_JSON" ]]; then
  echo "SUCCESS: Built $OUT_JSON"
else
  echo "ERROR: Output JSON missing/empty: $OUT_JSON" >&2
  exit 1
fi

echo "==> Copying output JSON to where you launched the script: $START_DIR"
cp -f "$OUT_JSON" "$START_DIR/DrugBank_aligned_with_KG2.json"
echo "    Copied to: $START_DIR/DrugBank_aligned_with_KG2.json"