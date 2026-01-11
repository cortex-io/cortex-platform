#!/bin/bash
# Generate comprehensive test coverage report for Cortex

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
COVERAGE_DIR="${SCRIPT_DIR}"
REPORT_DIR="${COVERAGE_DIR}/reports"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Generating Cortex Test Coverage Reports${NC}"
echo "=========================================="

# Create report directory
mkdir -p "${REPORT_DIR}"

# Function to check if coverage file exists
check_coverage() {
    local file=$1
    if [ -f "${file}" ]; then
        echo -e "${GREEN}✓${NC} Found: ${file}"
        return 0
    else
        echo -e "${YELLOW}⚠${NC} Missing: ${file}"
        return 1
    fi
}

echo ""
echo "Checking coverage files..."
echo "--------------------------"

# Check JavaScript unit test coverage
check_coverage "${COVERAGE_DIR}/unit/js/lcov.info" && JS_UNIT_COVERAGE=1 || JS_UNIT_COVERAGE=0

# Check Python unit test coverage
check_coverage "${COVERAGE_DIR}/unit/python/coverage.json" && PY_UNIT_COVERAGE=1 || PY_UNIT_COVERAGE=0

# Check JavaScript integration test coverage
check_coverage "${COVERAGE_DIR}/integration/js/lcov.info" && JS_INT_COVERAGE=1 || JS_INT_COVERAGE=0

# Check Python integration test coverage
check_coverage "${COVERAGE_DIR}/integration/python/coverage.json" && PY_INT_COVERAGE=1 || PY_INT_COVERAGE=0

echo ""
echo "Generating combined report..."
echo "-----------------------------"

# Create HTML index
cat > "${REPORT_DIR}/index.html" << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cortex Test Coverage Report</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }
        h1 {
            color: #333;
            border-bottom: 3px solid #4CAF50;
            padding-bottom: 10px;
        }
        .coverage-section {
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .coverage-item {
            display: flex;
            justify-content: space-between;
            padding: 10px;
            border-bottom: 1px solid #eee;
        }
        .coverage-bar {
            width: 200px;
            height: 20px;
            background: #eee;
            border-radius: 10px;
            overflow: hidden;
        }
        .coverage-fill {
            height: 100%;
            background: linear-gradient(90deg, #4CAF50 0%, #8BC34A 100%);
            transition: width 0.3s ease;
        }
        .coverage-fill.low { background: linear-gradient(90deg, #f44336 0%, #ff5722 100%); }
        .coverage-fill.medium { background: linear-gradient(90deg, #ff9800 0%, #ffc107 100%); }
        .coverage-fill.high { background: linear-gradient(90deg, #4CAF50 0%, #8BC34A 100%); }
        .timestamp {
            color: #666;
            font-size: 0.9em;
            margin-top: 10px;
        }
        a {
            color: #2196F3;
            text-decoration: none;
        }
        a:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <h1>🧪 Cortex Test Coverage Report</h1>

    <div class="coverage-section">
        <h2>Unit Tests</h2>
        <div class="coverage-item">
            <span>JavaScript Services</span>
            <a href="../unit/js/html/index.html">View Report</a>
        </div>
        <div class="coverage-item">
            <span>Python Services</span>
            <a href="../unit/python/html/index.html">View Report</a>
        </div>
    </div>

    <div class="coverage-section">
        <h2>Integration Tests</h2>
        <div class="coverage-item">
            <span>JavaScript Services</span>
            <a href="../integration/js/html/index.html">View Report</a>
        </div>
        <div class="coverage-item">
            <span>Python Services</span>
            <a href="../integration/python/html/index.html">View Report</a>
        </div>
    </div>

    <div class="coverage-section">
        <h2>Service-Specific Coverage</h2>
        <div class="coverage-item">
            <span>Issue Parser Service (JavaScript)</span>
            <a href="#">View Details</a>
        </div>
        <div class="coverage-item">
            <span>Repository Context Service (Python)</span>
            <a href="#">View Details</a>
        </div>
        <div class="coverage-item">
            <span>Code Generator Service (JavaScript)</span>
            <a href="#">View Details</a>
        </div>
    </div>

    <div class="timestamp">
        Generated: TIMESTAMP_PLACEHOLDER
    </div>
</body>
</html>
EOF

# Replace timestamp
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
sed -i.bak "s/TIMESTAMP_PLACEHOLDER/${TIMESTAMP}/g" "${REPORT_DIR}/index.html" && rm "${REPORT_DIR}/index.html.bak"

echo ""
echo -e "${GREEN}✓${NC} Coverage report generated: ${REPORT_DIR}/index.html"

# Generate summary
echo ""
echo "Coverage Summary"
echo "================"

if [ $JS_UNIT_COVERAGE -eq 1 ]; then
    echo -e "${GREEN}✓${NC} JavaScript Unit Tests: Coverage available"
fi

if [ $PY_UNIT_COVERAGE -eq 1 ]; then
    echo -e "${GREEN}✓${NC} Python Unit Tests: Coverage available"
fi

if [ $JS_INT_COVERAGE -eq 1 ]; then
    echo -e "${GREEN}✓${NC} JavaScript Integration Tests: Coverage available"
fi

if [ $PY_INT_COVERAGE -eq 1 ]; then
    echo -e "${GREEN}✓${NC} Python Integration Tests: Coverage available"
fi

echo ""
echo -e "${GREEN}Done!${NC} Open ${REPORT_DIR}/index.html in your browser to view the full report."
