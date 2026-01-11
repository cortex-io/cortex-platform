# Makefile for cortex-k8s CLI

.PHONY: help install uninstall test lint clean

# Default installation directory
PREFIX ?= /usr/local
BINDIR = $(PREFIX)/bin

help:
	@echo "Cortex K8s CLI - Makefile"
	@echo ""
	@echo "Usage:"
	@echo "  make install      Install cortex-k8s CLI"
	@echo "  make uninstall    Uninstall cortex-k8s CLI"
	@echo "  make test         Run tests"
	@echo "  make lint         Run shellcheck"
	@echo "  make clean        Clean build artifacts"
	@echo ""
	@echo "Variables:"
	@echo "  PREFIX=$(PREFIX)   Installation prefix"
	@echo "  BINDIR=$(BINDIR)   Binary installation directory"

install:
	@echo "Installing cortex-k8s CLI..."
	@./install.sh
	@echo "Done!"

uninstall:
	@echo "Uninstalling cortex-k8s CLI..."
	@./install.sh --uninstall
	@echo "Done!"

test:
	@echo "Running tests..."
	@bash -n cortex-k8s
	@bash -n install.sh
	@bash -n cortex-k8s-completion.bash
	@echo "Syntax check passed!"

lint:
	@echo "Running shellcheck..."
	@if command -v shellcheck >/dev/null 2>&1; then \
		shellcheck cortex-k8s install.sh cortex-k8s-completion.bash; \
		echo "Shellcheck passed!"; \
	else \
		echo "shellcheck not found, skipping..."; \
		echo "Install with: brew install shellcheck"; \
	fi

clean:
	@echo "Nothing to clean"

# Development targets
dev-install:
	@echo "Installing in development mode..."
	@ln -sf "$(PWD)/cortex-k8s" "$(BINDIR)/cortex-k8s"
	@echo "Created symlink: $(BINDIR)/cortex-k8s -> $(PWD)/cortex-k8s"

dev-uninstall:
	@echo "Removing development symlink..."
	@rm -f "$(BINDIR)/cortex-k8s"
	@echo "Done!"
