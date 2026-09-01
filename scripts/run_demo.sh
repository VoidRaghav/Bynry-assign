#!/usr/bin/env bash
set -euo pipefail

PYTHON="${PYTHON:-python3}"
cd "$(dirname "$0")/.."
set -a; source .env.demo; set +a

mkdir -p reports
rm -rf .auth

$PYTHON mock_app/server.py > reports/mock_app.log 2>&1 &
MOCK_PID=$!
trap 'kill $MOCK_PID 2>/dev/null || true' EXIT

for _ in $(seq 1 40); do
  curl -sf "http://127.0.0.1:${MOCK_PORT}/t/company1/login" > /dev/null && break
  sleep 0.25
done

$PYTHON -m pytest "$@" \
  --junitxml=reports/junit.xml \
  --html=reports/report.html --self-contained-html \
  | tee reports/last-run.txt
