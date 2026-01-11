#!/usr/bin/env bash
#
# Installation script for cortex-k8s CLI
#
# This script installs the cortex-k8s CLI and sets up auto-completion
#

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

# Installation directories
INSTALL_DIR="${INSTALL_DIR:-/usr/local/bin}"
COMPLETION_DIR_BASH="/etc/bash_completion.d"
COMPLETION_DIR_ZSH="/usr/local/share/zsh/site-functions"

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log_info() {
    echo -e "${BLUE}ℹ${NC} $*"
}

log_success() {
    echo -e "${GREEN}✓${NC} $*"
}

log_warning() {
    echo -e "${YELLOW}⚠${NC} $*"
}

log_error() {
    echo -e "${RED}✗${NC} $*" >&2
}

banner() {
    cat << 'EOF'
   ____           _               _  ___
  / ___|___  _ __| |_ _____  __  | |/ ( )___
 | |   / _ \| '__| __/ _ \ \/ /  | ' /|// __|
 | |__| (_) | |  | ||  __/>  <   | . \  \__ \
  \____\___/|_|   \__\___/_/\_\  |_|\_\ |___/

  Installation Script
EOF
    echo ""
}

check_prerequisites() {
    local missing=()

    if ! command -v kubectl &> /dev/null; then
        missing+=("kubectl")
    fi

    if ! command -v jq &> /dev/null; then
        missing+=("jq")
    fi

    if [[ ${#missing[@]} -gt 0 ]]; then
        log_warning "Missing optional tools: ${missing[*]}"
        log_info "Install with: brew install ${missing[*]}"
        echo ""
        read -p "Continue anyway? [y/N] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

install_binary() {
    log_info "Installing cortex-k8s to ${BOLD}${INSTALL_DIR}${NC}"

    # Check if we need sudo
    local use_sudo=""
    if [[ ! -w "${INSTALL_DIR}" ]]; then
        log_warning "Installation directory requires sudo access"
        use_sudo="sudo"
    fi

    # Copy the binary
    if ${use_sudo} cp "${SCRIPT_DIR}/cortex-k8s" "${INSTALL_DIR}/cortex-k8s"; then
        ${use_sudo} chmod +x "${INSTALL_DIR}/cortex-k8s"
        log_success "Installed cortex-k8s to ${INSTALL_DIR}/cortex-k8s"
    else
        log_error "Failed to install binary"
        return 1
    fi

    # Verify installation
    if command -v cortex-k8s &> /dev/null; then
        log_success "cortex-k8s is now available in your PATH"
    else
        log_warning "cortex-k8s is not in your PATH"
        log_info "Add ${INSTALL_DIR} to your PATH or use the full path"
    fi
}

install_bash_completion() {
    log_info "Setting up bash completion..."

    # Try system-wide installation first
    if [[ -d "${COMPLETION_DIR_BASH}" ]] && [[ -w "${COMPLETION_DIR_BASH}" || -n "${use_sudo}" ]]; then
        local use_sudo=""
        if [[ ! -w "${COMPLETION_DIR_BASH}" ]]; then
            use_sudo="sudo"
        fi

        if ${use_sudo} cp "${SCRIPT_DIR}/cortex-k8s-completion.bash" \
            "${COMPLETION_DIR_BASH}/cortex-k8s"; then
            log_success "Installed bash completion to ${COMPLETION_DIR_BASH}"
            log_info "Restart your shell or run: source ${COMPLETION_DIR_BASH}/cortex-k8s"
            return 0
        fi
    fi

    # Fallback to user installation
    local user_completion_dir="${HOME}/.bash_completion.d"
    mkdir -p "${user_completion_dir}"

    if cp "${SCRIPT_DIR}/cortex-k8s-completion.bash" \
        "${user_completion_dir}/cortex-k8s"; then
        log_success "Installed bash completion to ${user_completion_dir}"

        # Add to .bashrc if not already there
        local bashrc="${HOME}/.bashrc"
        if [[ -f "${bashrc}" ]]; then
            if ! grep -q "cortex-k8s-completion.bash" "${bashrc}"; then
                echo "" >> "${bashrc}"
                echo "# cortex-k8s completion" >> "${bashrc}"
                echo "source ${user_completion_dir}/cortex-k8s" >> "${bashrc}"
                log_info "Added completion to ${bashrc}"
            fi
        fi

        log_info "Restart your shell or run: source ${user_completion_dir}/cortex-k8s"
    else
        log_warning "Could not install bash completion"
    fi
}

install_zsh_completion() {
    log_info "Setting up zsh completion..."

    # Detect shell
    if [[ ! "${SHELL}" =~ zsh ]]; then
        log_info "Skipping zsh completion (not using zsh)"
        return 0
    fi

    # Try system-wide installation
    if [[ -d "${COMPLETION_DIR_ZSH}" ]]; then
        local use_sudo=""
        if [[ ! -w "${COMPLETION_DIR_ZSH}" ]]; then
            use_sudo="sudo"
        fi

        if ${use_sudo} cp "${SCRIPT_DIR}/cortex-k8s-completion.zsh" \
            "${COMPLETION_DIR_ZSH}/_cortex-k8s"; then
            log_success "Installed zsh completion to ${COMPLETION_DIR_ZSH}"
            log_info "Restart your shell or run: compinit"
            return 0
        fi
    fi

    # Fallback to user installation
    local user_completion_dir="${HOME}/.zsh/completion"
    mkdir -p "${user_completion_dir}"

    if cp "${SCRIPT_DIR}/cortex-k8s-completion.zsh" \
        "${user_completion_dir}/_cortex-k8s"; then
        log_success "Installed zsh completion to ${user_completion_dir}"

        # Add to .zshrc if not already there
        local zshrc="${HOME}/.zshrc"
        if [[ -f "${zshrc}" ]]; then
            if ! grep -q "cortex-k8s.*completion" "${zshrc}"; then
                echo "" >> "${zshrc}"
                echo "# cortex-k8s completion" >> "${zshrc}"
                echo "fpath=(${user_completion_dir} \$fpath)" >> "${zshrc}"
                echo "autoload -Uz compinit && compinit" >> "${zshrc}"
                log_info "Added completion to ${zshrc}"
            fi
        fi

        log_info "Restart your shell or run: compinit"
    else
        log_warning "Could not install zsh completion"
    fi
}

show_summary() {
    echo ""
    log_success "${BOLD}Installation complete!${NC}"
    echo ""
    log_info "Quick start:"
    echo "  cortex-k8s help              # Show help"
    echo "  cortex-k8s list              # List available services"
    echo "  cortex-k8s status            # Show status of all services"
    echo "  cortex-k8s deploy <service>  # Deploy a service"
    echo ""
    log_info "Documentation:"
    echo "  cat ${SCRIPT_DIR}/README.md"
    echo ""
}

uninstall() {
    log_info "Uninstalling cortex-k8s..."

    local use_sudo=""
    if [[ ! -w "${INSTALL_DIR}" ]]; then
        use_sudo="sudo"
    fi

    # Remove binary
    if [[ -f "${INSTALL_DIR}/cortex-k8s" ]]; then
        ${use_sudo} rm -f "${INSTALL_DIR}/cortex-k8s"
        log_success "Removed ${INSTALL_DIR}/cortex-k8s"
    fi

    # Remove completions
    if [[ -f "${COMPLETION_DIR_BASH}/cortex-k8s" ]]; then
        ${use_sudo} rm -f "${COMPLETION_DIR_BASH}/cortex-k8s"
        log_success "Removed bash completion"
    fi

    if [[ -f "${COMPLETION_DIR_ZSH}/_cortex-k8s" ]]; then
        ${use_sudo} rm -f "${COMPLETION_DIR_ZSH}/_cortex-k8s"
        log_success "Removed zsh completion"
    fi

    # User completions
    rm -f "${HOME}/.bash_completion.d/cortex-k8s" 2>/dev/null || true
    rm -f "${HOME}/.zsh/completion/_cortex-k8s" 2>/dev/null || true

    log_success "Uninstallation complete"
}

main() {
    banner

    # Check for uninstall flag
    if [[ "${1:-}" == "--uninstall" ]] || [[ "${1:-}" == "uninstall" ]]; then
        uninstall
        exit 0
    fi

    # Check prerequisites
    check_prerequisites

    # Install
    install_binary
    install_bash_completion
    install_zsh_completion

    # Show summary
    show_summary
}

main "$@"
