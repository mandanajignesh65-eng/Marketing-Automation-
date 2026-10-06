#!/bin/bash
# Add a person who can sign in to Meridian. Once one person exists, everyone has to sign in.
set -e
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -c "import fastapi, uvicorn" 2>/dev/null || .venv/bin/python -m pip install -q -r requirements.txt
exec .venv/bin/python -m meridian.accounts add
