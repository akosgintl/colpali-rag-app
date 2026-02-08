#!/usr/bin/env bash
set -e

# Model to download; supports both env-var conventions:
#   COLPALI_MODEL_NAME  - codebase / .env standard
#   COLPALI_MODEL       - docker build-arg / compose override
MODEL_ID="${COLPALI_MODEL_NAME:-${COLPALI_MODEL:-vidore/colqwen2.5-v0.2}}"

echo "==> Model: ${MODEL_ID}"
mkdir -p /models

# Only download once if not already present
if [ ! -d "/models/models--${MODEL_ID//\//--}" ]; then
  echo "==> Downloading model ${MODEL_ID} into /models ..."
  python3 - <<EOF
from huggingface_hub import snapshot_download
snapshot_download("${MODEL_ID}", cache_dir="/models")
EOF
  echo "==> Download complete."
else
  echo "==> Model already cached in /models, skipping download."
fi

exec "$@"
