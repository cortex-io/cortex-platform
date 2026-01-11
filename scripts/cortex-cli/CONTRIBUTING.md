# Contributing to Cortex K8s CLI

Thank you for your interest in contributing to the Cortex K8s CLI! This guide will help you get started.

## Quick Links

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Style Guide](#style-guide)

## Code of Conduct

Be respectful, collaborative, and constructive. We're all here to make Cortex better.

## Getting Started

### Prerequisites

- Bash 4.0 or later
- kubectl installed and configured
- jq for JSON processing
- Access to a Kubernetes/K3s cluster
- Git

### Development Setup

1. Clone the repository:
```bash
git clone https://github.com/your-org/cortex.git
cd cortex/scripts/cortex-cli
```

2. Install development dependencies:
```bash
# macOS
brew install shellcheck shfmt

# Linux
sudo apt-get install shellcheck
```

3. Install the CLI in development mode:
```bash
make dev-install
```

This creates a symlink so your changes are immediately available.

## Development Workflow

### 1. Create a Branch

```bash
git checkout -b feature/my-new-feature
```

Branch naming conventions:
- `feature/` - New features
- `bugfix/` - Bug fixes
- `docs/` - Documentation updates
- `refactor/` - Code refactoring

### 2. Make Changes

Edit the relevant files:
- `cortex-k8s` - Main CLI script
- `cortex-k8s-completion.bash` - Bash completion
- `cortex-k8s-completion.zsh` - Zsh completion
- `README.md` - Documentation
- `examples/` - Example scripts

### 3. Test Your Changes

```bash
# Syntax check
make test

# Lint with shellcheck
make lint

# Manual testing
cortex-k8s your-new-command --verbose
```

### 4. Update Documentation

- Update `README.md` if adding new features
- Update `CHANGELOG.md` with your changes
- Add examples to `examples/` if applicable
- Update completion scripts for new commands

### 5. Commit

```bash
git add .
git commit -m "feat: Add new awesome feature"
```

Commit message format:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation only
- `refactor:` - Code refactoring
- `test:` - Adding tests
- `chore:` - Maintenance tasks

## Adding New Commands

### 1. Add Command Function

In `cortex-k8s`, add a new function:

```bash
cmd_mycommand() {
    local arg1="$1"

    if [[ -z "${arg1}" ]]; then
        log_error "Argument required"
        echo "Usage: cortex-k8s mycommand <arg>"
        return 1
    fi

    log_info "Running mycommand..."

    local kubectl_cmd=$(get_kubectl_cmd)

    # Your command logic here

    log_success "Command completed"
}
```

### 2. Add to Main Router

In the `main()` function:

```bash
case "${command}" in
    # ... existing commands ...
    mycommand)
        cmd_mycommand "$@"
        ;;
```

### 3. Add to Help

Update `cmd_help()`:

```bash
${BOLD}COMMANDS:${NC}
  # ... existing commands ...
  ${GREEN}mycommand${NC} <arg>        Description of command
```

### 4. Add Completion

In `cortex-k8s-completion.bash`:

```bash
local commands="deploy build logs status test restart scale exec list mycommand help version"

# ... later in the file ...

case "${command}" in
    # ... existing cases ...
    mycommand)
        # Add completion for your command
        COMPREPLY=( $(compgen -W "option1 option2" -- "${cur}") )
        ;;
```

In `cortex-k8s-completion.zsh`:

```zsh
commands=(
    # ... existing commands ...
    'mycommand:Description of command'
)

# ... later in the file ...

case $words[1] in
    # ... existing cases ...
    mycommand)
        _arguments \
            '1:arg:(option1 option2)'
        ;;
```

### 5. Add Documentation

Update `README.md`:

```markdown
### My Command

\`\`\`bash
# Example usage
cortex-k8s mycommand arg1

# With flags
cortex-k8s mycommand arg1 --namespace=production
\`\`\`

Description of what the command does...
```

### 6. Add Example (Optional)

Create `examples/mycommand-example.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Example: Using mycommand

echo "Running mycommand example..."
cortex-k8s mycommand example-arg
```

## Testing

### Syntax Testing

```bash
# Check bash syntax
bash -n cortex-k8s

# Check all scripts
make test
```

### Linting

```bash
# Run shellcheck
make lint

# Or manually
shellcheck cortex-k8s install.sh
```

### Manual Testing

```bash
# Test command
cortex-k8s mycommand --verbose

# Test with different namespaces
cortex-k8s mycommand --namespace=test

# Test error handling
cortex-k8s mycommand invalid-input

# Test completion
cortex-k8s myco<TAB>
```

### Integration Testing

```bash
# Deploy test service
cortex-k8s deploy test-service --namespace=test

# Verify
cortex-k8s status test-service --namespace=test

# Clean up
kubectl delete deployment test-service -n test
```

## Style Guide

### Bash Style

Follow these conventions:

**Variables:**
```bash
# Constants in UPPER_CASE
NAMESPACE="cortex"

# Local variables in lower_case
local service="cortex-api"

# Use quotes
service="${1}"  # Good
service=$1      # Bad
```

**Functions:**
```bash
# Function names in snake_case
my_function() {
    local param="$1"

    # Function body
}
```

**Error Handling:**
```bash
# Always check return values
if kubectl apply -f manifest.yaml; then
    log_success "Applied"
else
    log_error "Failed"
    return 1
fi
```

**Logging:**
```bash
# Use log functions
log_info "Information message"
log_success "Success message"
log_warning "Warning message"
log_error "Error message"
log_verbose "Debug message"  # Only shown with --verbose
```

**Flags:**
```bash
# Use long flags in scripts
kubectl get pods --namespace=cortex --output=json

# Short flags are okay for interactive use
```

### Documentation Style

**Code Examples:**
```bash
# Always include comments
# Good:
# Deploy service to production
cortex-k8s deploy cortex-api --namespace=production

# Bad:
cortex-k8s deploy cortex-api --namespace=production
```

**Markdown:**
- Use headers (`#`, `##`, `###`) for structure
- Use code blocks with language tags
- Use bullet points for lists
- Use bold for emphasis
- Keep lines under 100 characters

## Submitting Changes

### 1. Push Your Branch

```bash
git push origin feature/my-new-feature
```

### 2. Create Pull Request

- Go to GitHub and create a PR
- Use a descriptive title
- Fill out the PR template
- Link any related issues

### 3. PR Checklist

- [ ] Code follows style guide
- [ ] All tests pass
- [ ] Documentation updated
- [ ] Changelog updated
- [ ] Completion scripts updated
- [ ] Examples added (if applicable)
- [ ] Tested manually
- [ ] No shellcheck warnings

### 4. Review Process

- Maintainers will review your PR
- Address any feedback
- Once approved, it will be merged

## Release Process

(For maintainers)

1. Update version in:
   - `cortex-k8s` (VERSION variable)
   - `CHANGELOG.md`

2. Create release tag:
```bash
git tag -a v1.1.0 -m "Release v1.1.0"
git push origin v1.1.0
```

3. Create GitHub release with changelog

## Getting Help

- Check existing issues and PRs
- Ask questions in discussions
- Reach out to maintainers

## Recognition

Contributors will be recognized in:
- CHANGELOG.md
- Release notes
- Project README

Thank you for contributing!
