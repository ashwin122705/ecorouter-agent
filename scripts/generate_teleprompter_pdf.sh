#!/usr/bin/env bash
# Regenerate docs/EcoRouter_Teleprompter_v2.pdf from the print-ready HTML.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HTML="$ROOT/docs/EcoRouter_Teleprompter_v2.html"
OUT="$ROOT/docs/EcoRouter_Teleprompter_v2.pdf"

CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
if [[ ! -x "$CHROME" ]]; then
  echo "Google Chrome not found. Open $HTML in a browser and use Print -> Save as PDF." >&2
  exit 1
fi

"$CHROME" --headless=new --disable-gpu --no-pdf-header-footer \
  --print-to-pdf="$OUT" "file://$HTML"

echo "Wrote $OUT"
