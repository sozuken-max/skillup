# SkillUP Test Runner Script (PowerShell)
# ====================================

# Set error action preference
$ErrorActionPreference = "Stop"

# Colors for output
$RED = "Red"
$GREEN = "Green"
$YELLOW = "Yellow"
$BLUE = "Cyan"
$NC = "White" # Default color

function Write-ColoredOutput {
    param([string]$Text, [string]$Color = $NC)
    Write-Host $Text -ForegroundColor $Color
}

Write-ColoredOutput "╔════════════════════════════════════════════╗" $BLUE
Write-ColoredOutput "║     SkillUP Test Suite Runner              ║" $BLUE
Write-ColoredOutput "╚════════════════════════════════════════════╝" $BLUE
Write-Host ""

# Check if uv is available
try {
    $uvVersion = & uv --version 2>$null
}
catch {
    Write-ColoredOutput "❌ uv not found. Please install uv first: https://github.com/astral-sh/uv" $RED
    exit 1
}

# Ensure pytest dependencies are available
try {
    & uv run python -c "import pytest" 2>$null | Out-Null
}
catch {
    Write-ColoredOutput "❌ pytest not found in uv environment. Installing..." $RED
    & uv add --dev pytest pytest-cov pytest-mock
}

# Default: run all unit tests
$TEST_TARGET = if ($args.Length -gt 0) { $args[0] } else { "tests/ -m unit" }
$COVERAGE = if ($args.Length -gt 1) { $args[1] } else { "yes" }

Write-ColoredOutput "Running tests: $TEST_TARGET" $YELLOW
Write-Host ""

# Run tests based on argument
switch ($TEST_TARGET) {
    "smoke" {
        Write-ColoredOutput "🔥 Running smoke tests..." $GREEN
        & uv run pytest tests/ -m smoke -v
    }
    "unit" {
        Write-ColoredOutput "🧪 Running unit tests..." $GREEN
        & uv run pytest tests/ -m unit -v --tb=short
    }
    "integration" {
        Write-ColoredOutput "🔗 Running integration tests..." $GREEN
        & uv run pytest tests/ -m integration -v --runxfail
    }
    "coverage" {
        Write-ColoredOutput "📊 Running tests with coverage..." $GREEN
        & uv run pytest tests/ -m unit --cov=. --cov-report=term-missing --cov-report=html
        Write-Host ""
        Write-ColoredOutput "✅ Coverage report generated in htmlcov/index.html" $GREEN
    }
    "all" {
        Write-ColoredOutput "🚀 Running all tests..." $GREEN
        & uv run pytest tests/ -v
    }
    "quick" {
        Write-ColoredOutput "⚡ Running quick smoke tests..." $GREEN
        & uv run pytest tests/ -m smoke --tb=line -q
    }
    default {
        # Custom pytest command
        Write-ColoredOutput "🎯 Running custom tests: $TEST_TARGET" $GREEN
        & uv run pytest $TEST_TARGET.Split()
    }
}

$EXIT_CODE = $LASTEXITCODE

Write-Host ""
if ($EXIT_CODE -eq 0) {
    Write-ColoredOutput "╔════════════════════════════════════════════╗" $GREEN
    Write-ColoredOutput "║     ✅ All tests passed!                   ║" $GREEN
    Write-ColoredOutput "╚════════════════════════════════════════════╝" $GREEN
} else {
    Write-ColoredOutput "╔════════════════════════════════════════════╗" $RED
    Write-ColoredOutput "║     ❌ Some tests failed                   ║" $RED
    Write-ColoredOutput "╚════════════════════════════════════════════╝" $RED
}

exit $EXIT_CODE
