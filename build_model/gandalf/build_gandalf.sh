#!/bin/bash
# Exit immediately if a command exits with a non-zero status
set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <release_date>"
    echo "Example: $0 2026_04_08"
    exit 1
fi

RELEASE_DATE="$1"

# Validate date format: YYYY_MM_DD
if [[ ! "$RELEASE_DATE" =~ ^[0-9]{4}_[0-9]{2}_[0-9]{2}$ ]]; then
    echo "Error: release_date must be in format YYYY_MM_DD"
    echo "Example: 2026_04_08"
    exit 1
fi

# Convert 2026_04_08 -> 20260408
DATE_NO_UNDERSCORE="${RELEASE_DATE//_/}"

BASE_URL="https://kgx-storage.rtx.ai/releases/translator_kg/${RELEASE_DATE}"
FILE_NAME="translator_kg.tar.zst"
DOWNLOAD_URL="${BASE_URL}/${FILE_NAME}"

OUTPUT_FILE="gandalf_mmap_tier0-${DATE_NO_UNDERSCORE}.tar.gz"
REMOTE_SERVER="rtxconfig@arax-databases.rtx.ai"
REMOTE_DIR="~/tier0-${DATE_NO_UNDERSCORE}"

echo "========================================"
echo "Release date: ${RELEASE_DATE}"
echo "Output file: ${OUTPUT_FILE}"
echo "Remote path: ${REMOTE_SERVER}:${REMOTE_DIR}/"
echo "========================================"

echo ""
echo "========================================"
echo "1. Downloading ${FILE_NAME}"
echo "========================================"
wget --show-progress -O "$FILE_NAME" "$DOWNLOAD_URL"

echo ""
echo "========================================"
echo "2. Extracting ${FILE_NAME}"
echo "========================================"
# Requires zstd to be installed on your system
tar -I zstd -xvf "$FILE_NAME"

echo ""
echo "========================================"
echo "3. Running Gandalf Graph Builder"
echo "========================================"

cat << 'EOF' > build_graph.py
import time
from gandalf import build_graph_from_jsonl

start_time = time.perf_counter()

graph = build_graph_from_jsonl(
    "edges.jsonl",
    "nodes.jsonl",
)

graph.save_mmap("gandalf_mmap")

end_time = time.perf_counter()
execution_time = end_time - start_time

print(f"Executed in {execution_time:.6f} seconds")
EOF

python3 build_graph.py

echo ""
echo "========================================"
echo "4. Compressing gandalf_mmap directory"
echo "========================================"
tar --no-xattrs -czvf "$OUTPUT_FILE" gandalf_mmap

echo ""
echo "========================================"
echo "5. Uploading ${OUTPUT_FILE} to server"
echo "========================================"

# Create remote directory if it does not exist
ssh "$REMOTE_SERVER" "mkdir -p ${REMOTE_DIR}"

# Upload file
scp "$OUTPUT_FILE" "${REMOTE_SERVER}:${REMOTE_DIR}/"

echo ""
echo "========================================"
echo "Process Complete!"
echo "Output file: ${OUTPUT_FILE}"
echo "Uploaded to: ${REMOTE_SERVER}:${REMOTE_DIR}/"
echo "========================================"

rm build_graph.py
