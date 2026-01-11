#!/bin/bash
# Quick validation script for cortex-live installation

set -e

echo "=== Cortex Live Installation Test ==="
echo ""

echo "1. Checking Python version..."
python3 --version

echo ""
echo "2. Installing cortex-live in development mode..."
cd /Users/ryandahlberg/Projects/cortex-platform/services/cortex-live
pip3 install -e . --quiet

echo ""
echo "3. Checking installation..."
python3 -c "import cortex_live; print(f'cortex_live version: {cortex_live.__version__}')"

echo ""
echo "4. Verifying module structure..."
python3 -c "from cortex_live import app, api, widgets, screens; print('All modules imported successfully')"

echo ""
echo "5. Checking command availability..."
which cortex-live

echo ""
echo "=== Installation test complete! ==="
echo ""
echo "To run cortex-live:"
echo "  cortex-live"
echo ""
echo "Or as a module:"
echo "  python3 -m cortex_live"
