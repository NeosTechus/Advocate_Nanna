#!/bin/bash
# ============================================================
# Setup Automation for Vacancy Scraper
# Installs the LaunchAgent for daily scheduled scraping
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_NAME="com.vacancies.scraper.plist"
PLIST_SRC="${SCRIPT_DIR}/${PLIST_NAME}"
PLIST_DEST="${HOME}/Library/LaunchAgents/${PLIST_NAME}"
LAUNCH_AGENTS_DIR="${HOME}/Library/LaunchAgents"

echo "============================================================"
echo "  Vacancy Scraper - Automation Setup"
echo "============================================================"
echo ""

# --- Ensure LaunchAgents directory exists ---
if [ ! -d "${LAUNCH_AGENTS_DIR}" ]; then
    echo "Creating ~/Library/LaunchAgents/ ..."
    mkdir -p "${LAUNCH_AGENTS_DIR}"
fi

# --- Ensure logs directory exists ---
mkdir -p "${SCRIPT_DIR}/logs"

# --- Make run_scraper.sh executable ---
chmod +x "${SCRIPT_DIR}/run_scraper.sh"
echo "[OK] run_scraper.sh is executable"

# --- Make refresh.sh executable ---
if [ -f "${SCRIPT_DIR}/refresh.sh" ]; then
    chmod +x "${SCRIPT_DIR}/refresh.sh"
    echo "[OK] refresh.sh is executable"
fi

# --- Unload existing job if present ---
if launchctl list | grep -q "com.vacancies.scraper" 2>/dev/null; then
    echo "Unloading existing LaunchAgent..."
    launchctl unload "${PLIST_DEST}" 2>/dev/null || true
fi

# --- Copy plist ---
cp "${PLIST_SRC}" "${PLIST_DEST}"
echo "[OK] Plist copied to ${PLIST_DEST}"

# --- Load the LaunchAgent ---
launchctl load "${PLIST_DEST}"
echo "[OK] LaunchAgent loaded"

# --- Verify ---
if launchctl list | grep -q "com.vacancies.scraper"; then
    echo "[OK] LaunchAgent is running"
else
    echo "[WARN] LaunchAgent may not have loaded correctly. Check with:"
    echo "       launchctl list | grep vacancies"
fi

echo ""
echo "============================================================"
echo "  Setup Complete!"
echo "============================================================"
echo ""
echo "Schedule: Daily at 8:00 AM and 6:00 PM"
echo "Logs:     ${SCRIPT_DIR}/logs/scraper.log"
echo "Data:     ${SCRIPT_DIR}/data.json"
echo ""
echo "Useful commands:"
echo "  Manual run:    ${SCRIPT_DIR}/refresh.sh"
echo "  View logs:     tail -f ${SCRIPT_DIR}/logs/scraper.log"
echo "  Check status:  launchctl list | grep vacancies"
echo ""
echo "------------------------------------------------------------"
echo "  To UNINSTALL:"
echo "------------------------------------------------------------"
echo "  1. Unload the agent:"
echo "     launchctl unload ~/Library/LaunchAgents/${PLIST_NAME}"
echo ""
echo "  2. Remove the plist:"
echo "     rm ~/Library/LaunchAgents/${PLIST_NAME}"
echo ""
echo "  3. (Optional) Remove logs:"
echo "     rm -rf ${SCRIPT_DIR}/logs"
echo "------------------------------------------------------------"
