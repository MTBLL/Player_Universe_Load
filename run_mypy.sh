#!/bin/bash
# Run mypy type checking on all Python files

source .venv/bin/activate

echo "Running basic mypy type checking..."

# Run mypy on the scripts directory with default settings
mypy --config-file=scripts/mypy.ini scripts/

echo "Type checking completed."