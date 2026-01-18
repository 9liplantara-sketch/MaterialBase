#!/usr/bin/env bash
set -euo pipefail

python3 -B -m py_compile app.py
python3 -B -m py_compile material_form_detailed.py
python3 -B -m py_compile database.py
