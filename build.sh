#!/usr/bin/env bash
# Render build script — installs Python deps + builds React frontend
set -e

pip install -r requirements.txt

cd frontend
npm install
npm run build
