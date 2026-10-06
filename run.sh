#!/bin/bash
# Start Meridian on http://localhost:8321.
#   ./run.sh            your own data once Zoho is connected, the sample company until then
#   ./run.sh --sample   always the sample company
# The first run installs the Python packages and builds the sample data.
set -e
cd "$(dirname "$0")"
[ "$1" = "--sample" ] && export MERIDIAN_SAMPLE=1
[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -c "import fastapi, uvicorn" 2>/dev/null || .venv/bin/python -m pip install -q -r requirements.txt
[ -f data/sample.db ] || .venv/bin/python -m meridian.seed
exec .venv/bin/uvicorn meridian.api:app --port "${PORT:-8321}"
