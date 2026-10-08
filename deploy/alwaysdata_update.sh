#!/bin/bash
# Alwaysdata'da (SSH) yangilash: GitHub'dan oxirgi kodni olib, kutubxonalarni yangilaydi.
# Ishlatish:  bash ~/zoom-platform/deploy/alwaysdata_update.sh
set -e
cd "$(dirname "$0")/.."
git pull --ff-only
cd backend
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements.txt -q
echo "Tayyor. Alwaysdata panelida: Advanced -> Services -> zoom-platform -> Restart"
