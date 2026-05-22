# Knowledge Graph Build & Upload Script

This script automates the process of downloading a specific Translator Knowledge Graph release, building a memory-mapped (`mmap`) Gandalf graph database from it, compressing the output, and deploying it to a remote database server.

## Prerequisites

Before running the script, ensure you have the following installed on your system:
* `wget` (for downloading files)
* `zstd` (required by `tar` to decompress `.zst` archives)
* `python3` with the `gandalf` library installed
* `ssh` and `scp` configured with access to the target remote server

## How to Use

Run the script from your terminal by passing a specific release date as the only argument. The date **must** be in the `YYYY_MM_DD` format.

```bash
chmod +x build_gandalf.sh
./build_gandalf.sh <release_date>