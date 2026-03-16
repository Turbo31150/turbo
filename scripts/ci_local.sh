#!/bin/bash
# Script CI local pour JARVIS Linux
# Lance toutes les verifications sans passer par GitHub Actions
# Usage : ./scripts/ci_local.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PASS=0
FAIL=0

run_step() {
    local name="$1"
    shift
    echo -e "\n${BLUE}=== ${name} ===${NC}"
    if "$@"; then
        echo -e "${GREEN}[PASS] ${name}${NC}"
        PASS=$((PASS + 1))
    else
        echo -e "${RED}[FAIL] ${name}${NC}"
        FAIL=$((FAIL + 1))
    fi
}

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  JARVIS CI Local Pipeline${NC}"
echo -e "${BLUE}  $(date '+%Y-%m-%d %H:%M:%S')${NC}"
echo -e "${BLUE}============================================${NC}"

# Etape 1 : Linting avec ruff
# Utilise uv run pour acceder a ruff dans le venv
run_step "LINT (ruff)" uv run ruff check src/ --select E,F --ignore E501

# Etape 2 : Tests des modules Linux
run_step "TEST Linux Modules" uv run pytest tests/test_linux_modules.py -v --tb=short

# Etape 3 : Tests d'integration du pipeline vocal
run_step "TEST Voice Pipeline Integration" uv run pytest tests/test_voice_pipeline_integration.py -v --tb=short

# Etape 4 : Scan de securite (secrets hardcodes)
security_scan() {
    local found=0
    if grep -rE "AIzaSy[a-zA-Z0-9_-]{33}" src/ scripts/ --include="*.py" --include="*.sh" 2>/dev/null; then
        echo "Google API key detected!"
        found=1
    fi
    if grep -rE "sk-[a-zA-Z0-9]{32,}" src/ scripts/ --include="*.py" --include="*.sh" 2>/dev/null; then
        echo "OpenAI API key detected!"
        found=1
    fi
    if grep -rE "ghp_[a-zA-Z0-9]{36}" src/ scripts/ --include="*.py" --include="*.sh" 2>/dev/null; then
        echo "GitHub token detected!"
        found=1
    fi
    if [ "$found" -eq 1 ]; then
        echo "SECRETS FOUND!"
        return 1
    fi
    echo "OK - No secrets detected"
    return 0
}
run_step "SECURITY SCAN" security_scan

# Etape 5 : Verification syntaxique des fichiers critiques
syntax_check() {
    local errors=0
    local files
    files=$(find src/ -name "linux_*.py" -o -name "voice_*.py" 2>/dev/null)
    if [ -z "$files" ]; then
        echo "No matching files found"
        return 0
    fi
    for f in $files; do
        if ! python3 -m py_compile "$f" 2>&1; then
            echo "Syntax error: $f"
            errors=$((errors + 1))
        fi
    done
    if [ "$errors" -gt 0 ]; then
        echo "$errors file(s) with syntax errors"
        return 1
    fi
    echo "All files OK"
    return 0
}
run_step "SYNTAX CHECK" syntax_check

# Resume final
echo -e "\n${BLUE}============================================${NC}"
echo -e "${BLUE}  RESULTS${NC}"
echo -e "${BLUE}============================================${NC}"
echo -e "${GREEN}  Passed: ${PASS}${NC}"
echo -e "${RED}  Failed: ${FAIL}${NC}"
echo -e "${BLUE}============================================${NC}"

if [ "$FAIL" -gt 0 ]; then
    echo -e "${RED}CI FAILED - ${FAIL} step(s) need attention${NC}"
    exit 1
fi

echo -e "${GREEN}CI PASSED - All checks OK${NC}"
exit 0
