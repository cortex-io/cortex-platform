#!/usr/bin/env bash
# Inventory Master - Comprehensive Codebase Scanner
#
# Generates inventory of all files, patterns, and dependencies
# Outputs protected files list for cleanup master

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "$SCRIPT_DIR/../../.." && pwd)}"

# Output locations
OUTPUT_DIR="${INVENTORY_OUTPUT_DIR:-$SCRIPT_DIR/output}"
PROTECTED_FILE="${PROTECTED_FILES:-$OUTPUT_DIR/protected-files.txt}"
RESULTS_FILE="${INVENTORY_OUTPUT:-$OUTPUT_DIR/inventory-results.json}"

mkdir -p "$OUTPUT_DIR"

# ANSI colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

echo -e "${CYAN}${BOLD}=== Inventory Master ===${NC}"
echo ""

# ==============================================================================
# FILE COUNTING
# ==============================================================================

count_by_extension() {
    echo -e "${BLUE}Counting files by extension...${NC}"

    # Simple file count (avoid associative arrays for Bash 3.x compatibility)
    local total
    total=$(find "$PROJECT_ROOT" -type f \
        -not -path "*/node_modules/*" \
        -not -path "*/.git/*" \
        -not -path "*/venv/*" \
        -not -path "*/__pycache__/*" \
        2>/dev/null | wc -l | tr -d ' ')

    echo "  Total files: $total"
    echo "$total"
}

# ==============================================================================
# PROTECTED FILES DETECTION
# ==============================================================================

generate_protected_list() {
    echo -e "${BLUE}Generating protected files list...${NC}"

    local protected_count=0

    # Clear existing file
    > "$PROTECTED_FILE"

    # Config files (always protected)
    find "$PROJECT_ROOT" -type f \( \
        -name "*.json" -o \
        -name "*.yaml" -o \
        -name "*.yml" -o \
        -name "*.toml" -o \
        -name "*.ini" -o \
        -name ".env*" -o \
        -name "Makefile" -o \
        -name "Dockerfile*" \
    \) -not -path "*/node_modules/*" \
       -not -path "*/.git/*" \
       2>/dev/null >> "$PROTECTED_FILE" || true

    # Source code entry points
    find "$PROJECT_ROOT" -type f \( \
        -name "index.*" -o \
        -name "main.*" -o \
        -name "app.*" -o \
        -name "run.sh" -o \
        -name "start.sh" \
    \) -not -path "*/node_modules/*" \
       -not -path "*/.git/*" \
       2>/dev/null >> "$PROTECTED_FILE" || true

    # Package manifests
    find "$PROJECT_ROOT" -type f \( \
        -name "package.json" -o \
        -name "package-lock.json" -o \
        -name "requirements.txt" -o \
        -name "pyproject.toml" -o \
        -name "Cargo.toml" -o \
        -name "go.mod" \
    \) 2>/dev/null >> "$PROTECTED_FILE" || true

    # Documentation (protect README files)
    find "$PROJECT_ROOT" -type f -name "README*" \
        -not -path "*/node_modules/*" \
        2>/dev/null >> "$PROTECTED_FILE" || true

    # Remove duplicates
    sort -u "$PROTECTED_FILE" -o "$PROTECTED_FILE"

    protected_count=$(wc -l < "$PROTECTED_FILE" | tr -d ' ')
    echo "  Protected files: $protected_count"
    echo "$protected_count"
}

# ==============================================================================
# DIRECTORY SIZE ANALYSIS
# ==============================================================================

scan_directory_sizes() {
    echo -e "${BLUE}Scanning directory sizes...${NC}"

    local top_dirs=$(du -sh "$PROJECT_ROOT"/*/ 2>/dev/null | sort -rh | head -10)
    echo "$top_dirs" | while read -r size dir; do
        echo "  $size  $(basename "$dir")"
    done
}

# ==============================================================================
# EXECUTABLE SCAN
# ==============================================================================

scan_executables() {
    echo -e "${BLUE}Scanning executable files...${NC}"

    local exec_count=$(find "$PROJECT_ROOT" -type f -perm +111 \
        -not -path "*/node_modules/*" \
        -not -path "*/.git/*" \
        -not -path "*/venv/*" \
        2>/dev/null | wc -l | tr -d ' ')

    echo "  Executable files: $exec_count"
    echo "$exec_count"
}

# ==============================================================================
# MAIN
# ==============================================================================

main() {
    local start_time=$(date +%s)

    # Run scans
    local total_files=$(count_by_extension)
    echo ""

    local protected_count=$(generate_protected_list)
    echo ""

    scan_directory_sizes
    echo ""

    local exec_count=$(scan_executables)
    echo ""

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))

    # Generate results JSON
    cat > "$RESULTS_FILE" << EOF
{
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "duration_seconds": $duration,
    "total_files": $total_files,
    "protected_files": $protected_count,
    "executable_files": $exec_count,
    "protected_file_path": "$PROTECTED_FILE"
}
EOF

    echo -e "${GREEN}${BOLD}=== Inventory Complete ===${NC}"
    echo "  Duration: ${duration}s"
    echo "  Results: $RESULTS_FILE"
    echo "  Protected list: $PROTECTED_FILE"
}

main "$@"
