#!/bin/bash
# SkillUP Test Runner Script
# ==========================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     SkillUP Test Suite Runner              ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════╝${NC}"
echo ""

# Check if uv is available and pytest is installed
if ! command -v uv &> /dev/null; then
    echo -e "${RED}❌ uv not found. Please install uv first: https://github.com/astral-sh/uv${NC}"
    exit 1
fi

# Ensure pytest dependencies are available
if ! uv run python -c "import pytest" &> /dev/null; then
    echo -e "${RED}❌ pytest not found in uv environment. Installing...${NC}"
    uv add --dev pytest pytest-cov pytest-mock
fi

# Default: run all unit tests
TEST_TARGET="${1:-tests/ -m unit}"
COVERAGE="${2:-yes}"

echo -e "${YELLOW}Running tests: ${TEST_TARGET}${NC}"
echo ""

# Run tests based on argument
case "$TEST_TARGET" in
    "smoke")
        echo -e "${GREEN}🔥 Running smoke tests...${NC}"
        uv run pytest tests/ -m smoke -v
        ;;
    "unit")
        echo -e "${GREEN}🧪 Running unit tests...${NC}"
        uv run pytest tests/ -m unit -v --tb=short
        ;;
    "integration")
        echo -e "${GREEN}🔗 Running integration tests...${NC}"
        uv run pytest tests/ -m integration -v --runxfail
        ;;
    "coverage")
        echo -e "${GREEN}📊 Running tests with coverage...${NC}"
        uv run pytest tests/ -m unit --cov=. --cov-report=term-missing --cov-report=html
        echo ""
        echo -e "${GREEN}✅ Coverage report generated in htmlcov/index.html${NC}"
        ;;
    "all")
        echo -e "${GREEN}🚀 Running all tests...${NC}"
        uv run pytest tests/ -v
        ;;
    "quick")
        echo -e "${GREEN}⚡ Running quick smoke tests...${NC}"
        uv run pytest tests/ -m smoke --tb=line -q
        ;;
    *)
        # Custom pytest command
        echo -e "${GREEN}🎯 Running custom tests: ${TEST_TARGET}${NC}"
        uv run pytest ${TEST_TARGET}
        ;;
esac

EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}╔════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║     ✅ All tests passed!                   ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════╝${NC}"
else
    echo -e "${RED}╔════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║     ❌ Some tests failed                   ║${NC}"
    echo -e "${RED}╚════════════════════════════════════════════╝${NC}"
fi

exit $EXIT_CODE
