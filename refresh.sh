#!/bin/bash
# ============================================================
# Quick Manual Run - Vacancy Scraper
# Runs the scraper immediately and opens the dashboard
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/venv"
SCRAPER="${SCRIPT_DIR}/scraper.py"
DATA_FILE="${SCRIPT_DIR}/data.json"
DASHBOARD="${SCRIPT_DIR}/index.html"
LOG_DIR="${SCRIPT_DIR}/logs"
LOG_FILE="${LOG_DIR}/scraper.log"

# --- Create logs directory if needed ---
mkdir -p "${LOG_DIR}"

echo "============================================================"
echo "  Vacancy Scraper - Manual Refresh"
echo "============================================================"
echo ""

# --- Check prerequisites ---
if [ ! -d "${VENV_DIR}" ]; then
    echo "ERROR: Virtual environment not found at ${VENV_DIR}"
    echo "Run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

if [ ! -f "${SCRAPER}" ]; then
    echo "ERROR: scraper.py not found at ${SCRAPER}"
    exit 1
fi

# --- Activate venv ---
source "${VENV_DIR}/bin/activate"

# --- Show previous stats if available ---
if [ -f "${DATA_FILE}" ]; then
    PREV_COUNT=$(python3 -c "import json; d=json.load(open('${DATA_FILE}')); print(len(d.get('vacancies', [])))" 2>/dev/null || echo "0")
    PREV_TIME=$(python3 -c "import json; d=json.load(open('${DATA_FILE}')); print(d.get('last_updated', 'unknown'))" 2>/dev/null || echo "unknown")
    echo "Previous run: ${PREV_COUNT} vacancies (${PREV_TIME})"
    echo ""
fi

# --- Run scraper ---
echo "Running scraper..."
echo "------------------------------------------------------------"
START_TIME=$(date +%s)

python3 "${SCRAPER}" 2>&1 | tee -a "${LOG_FILE}"

EXIT_CODE=${PIPESTATUS[0]}
END_TIME=$(date +%s)
ELAPSED=$(( END_TIME - START_TIME ))

echo ""
echo "------------------------------------------------------------"

if [ ${EXIT_CODE} -ne 0 ]; then
    echo ""
    echo "ERROR: Scraper failed with exit code ${EXIT_CODE}"
    echo "Check logs at: ${LOG_FILE}"
    deactivate 2>/dev/null || true
    exit ${EXIT_CODE}
fi

# --- Show summary ---
echo ""
echo "============================================================"
echo "  Results Summary"
echo "============================================================"

if [ -f "${DATA_FILE}" ]; then
    VACANCY_COUNT=$(python3 -c "import json; d=json.load(open('${DATA_FILE}')); print(len(d.get('vacancies', [])))" 2>/dev/null || echo "0")
    SOURCE_COUNT=$(python3 -c "import json; d=json.load(open('${DATA_FILE}')); print(len(d.get('sources', [])))" 2>/dev/null || echo "0")
    ERROR_COUNT=$(python3 -c "import json; d=json.load(open('${DATA_FILE}')); print(len(d.get('errors', [])))" 2>/dev/null || echo "0")
    OK_SOURCES=$(python3 -c "import json; d=json.load(open('${DATA_FILE}')); print(len([s for s in d.get('sources', []) if s.get('status')=='ok']))" 2>/dev/null || echo "0")
    LAST_UPDATED=$(python3 -c "import json; d=json.load(open('${DATA_FILE}')); print(d.get('last_updated', 'unknown'))" 2>/dev/null || echo "unknown")

    echo ""
    echo "  Vacancies found:   ${VACANCY_COUNT}"
    echo "  Sources checked:   ${SOURCE_COUNT} (${OK_SOURCES} successful)"
    echo "  Errors:            ${ERROR_COUNT}"
    echo "  Time taken:        ${ELAPSED}s"
    echo "  Last updated:      ${LAST_UPDATED}"
    echo "  Data file:         ${DATA_FILE}"

    # Show category breakdown
    echo ""
    echo "  Category breakdown:"
    python3 -c "
import json
from collections import Counter
d = json.load(open('${DATA_FILE}'))
cats = Counter(v.get('category', 'Unknown') for v in d.get('vacancies', []))
for cat, count in cats.most_common():
    print(f'    {cat}: {count}')
" 2>/dev/null || true

    # Show change from previous run
    if [ -n "${PREV_COUNT:-}" ] && [ "${PREV_COUNT}" != "0" ]; then
        DIFF=$(( VACANCY_COUNT - PREV_COUNT ))
        if [ ${DIFF} -gt 0 ]; then
            echo ""
            echo "  Change: +${DIFF} new vacancies since last run"
        elif [ ${DIFF} -lt 0 ]; then
            echo ""
            echo "  Change: ${DIFF} vacancies (some may have been removed/deduplicated)"
        else
            echo ""
            echo "  Change: No change in vacancy count"
        fi
    fi
else
    echo "  WARNING: data.json not found after scraping"
fi

echo ""
echo "============================================================"

# --- Deactivate venv ---
deactivate 2>/dev/null || true

# --- Open dashboard ---
if [ -f "${DASHBOARD}" ]; then
    echo "Opening dashboard in browser..."
    open "${DASHBOARD}"
else
    echo "Dashboard (index.html) not found. Skipping browser open."
fi
