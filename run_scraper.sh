#!/bin/bash
# ============================================================
# Judicial & Tribunal Vacancy Scraper - Daily Runner
# Activates venv, runs scraper, logs output, sends notification
# ============================================================

set -euo pipefail

# --- Configuration ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/venv"
SCRAPER="${SCRIPT_DIR}/scraper.py"
LOG_DIR="${SCRIPT_DIR}/logs"
LOG_FILE="${LOG_DIR}/scraper.log"
DATA_FILE="${SCRIPT_DIR}/data.json"

# --- Create logs directory if needed ---
mkdir -p "${LOG_DIR}"

# --- Timestamp helper ---
timestamp() {
    date "+%Y-%m-%d %H:%M:%S"
}

# --- Log separator ---
{
    echo ""
    echo "============================================================"
    echo "Scraper run started at $(timestamp)"
    echo "============================================================"
} >> "${LOG_FILE}"

# --- Activate virtual environment ---
if [ ! -d "${VENV_DIR}" ]; then
    echo "[$(timestamp)] ERROR: Virtual environment not found at ${VENV_DIR}" | tee -a "${LOG_FILE}"
    osascript -e 'display notification "Virtual environment not found. Run setup first." with title "Vacancy Scraper" subtitle "Error" sound name "Basso"'
    exit 1
fi

source "${VENV_DIR}/bin/activate"

# --- Verify scraper exists ---
if [ ! -f "${SCRAPER}" ]; then
    echo "[$(timestamp)] ERROR: Scraper not found at ${SCRAPER}" | tee -a "${LOG_FILE}"
    osascript -e 'display notification "scraper.py not found." with title "Vacancy Scraper" subtitle "Error" sound name "Basso"'
    deactivate
    exit 1
fi

# --- Run the scraper ---
echo "[$(timestamp)] Starting scraper..." >> "${LOG_FILE}"
START_TIME=$(date +%s)

if python3 "${SCRAPER}" >> "${LOG_FILE}" 2>&1; then
    END_TIME=$(date +%s)
    ELAPSED=$(( END_TIME - START_TIME ))

    # Extract vacancy count from data.json
    VACANCY_COUNT=0
    ERROR_COUNT=0
    SOURCE_COUNT=0
    if [ -f "${DATA_FILE}" ]; then
        VACANCY_COUNT=$(python3 -c "import json; d=json.load(open('${DATA_FILE}')); print(len(d.get('vacancies', [])))" 2>/dev/null || echo "0")
        ERROR_COUNT=$(python3 -c "import json; d=json.load(open('${DATA_FILE}')); print(len(d.get('errors', [])))" 2>/dev/null || echo "0")
        SOURCE_COUNT=$(python3 -c "import json; d=json.load(open('${DATA_FILE}')); print(len(d.get('sources', [])))" 2>/dev/null || echo "0")
    fi

    echo "[$(timestamp)] Scraper finished successfully in ${ELAPSED}s. Vacancies: ${VACANCY_COUNT}, Sources: ${SOURCE_COUNT}, Errors: ${ERROR_COUNT}" >> "${LOG_FILE}"

    # macOS notification
    osascript -e "display notification \"${VACANCY_COUNT} vacancies found from ${SOURCE_COUNT} sources (${ELAPSED}s)\" with title \"Vacancy Scraper\" subtitle \"Completed Successfully\" sound name \"Glass\""
else
    EXIT_CODE=$?
    END_TIME=$(date +%s)
    ELAPSED=$(( END_TIME - START_TIME ))

    echo "[$(timestamp)] ERROR: Scraper failed with exit code ${EXIT_CODE} after ${ELAPSED}s" >> "${LOG_FILE}"

    # macOS error notification
    osascript -e "display notification \"Scraper failed with exit code ${EXIT_CODE}. Check logs.\" with title \"Vacancy Scraper\" subtitle \"Error\" sound name \"Basso\""
fi

# --- Deactivate venv ---
deactivate 2>/dev/null || true

echo "[$(timestamp)] Run complete." >> "${LOG_FILE}"
