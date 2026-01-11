.PHONY: help build test lint format deploy clean

help:
	@echo "Cortex Orchestrator - Available Commands:"
	@echo ""
	@echo "  make build          - Build Docker image"
	@echo "  make test           - Run test suite"
	@echo "  make lint           - Run linters (ruff, mypy)"
	@echo "  make format         - Format code (black)"
	@echo "  make deploy         - Deploy to k3s cluster"
	@echo "  make clean          - Clean build artifacts"
	@echo "  make logs           - Follow orchestrator logs"
	@echo "  make status         - Check orchestrator status"
	@echo ""

build:
	@echo "Building Docker image..."
	docker build -t cortex/orchestrator:latest .
	@echo "✅ Build complete: cortex/orchestrator:latest"

test:
	@echo "Running test suite..."
	pytest tests/ -v --cov=server --cov-report=term-missing
	@echo "✅ Tests complete"

lint:
	@echo "Running linters..."
	ruff check server/ tests/
	mypy server/
	@echo "✅ Linting complete"

format:
	@echo "Formatting code..."
	black server/ tests/
	@echo "✅ Formatting complete"

deploy:
	@echo "Deploying to k3s..."
	kubectl create namespace cortex-system 2>/dev/null || true
	kubectl apply -f k8s/rbac.yaml
	kubectl apply -f k8s/configmap.yaml
	kubectl apply -f k8s/deployment.yaml
	@echo "Waiting for pod to be ready..."
	kubectl wait --for=condition=ready pod -l app=cortex-orchestrator -n cortex-system --timeout=60s
	@echo "✅ Deployment complete"
	@echo ""
	@echo "Check status with: make status"
	@echo "View logs with: make logs"

clean:
	@echo "Cleaning build artifacts..."
	rm -rf __pycache__ .pytest_cache .mypy_cache .coverage htmlcov
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Clean complete"

logs:
	@echo "Following orchestrator logs (Ctrl+C to exit)..."
	kubectl logs -n cortex-system -l app=cortex-orchestrator -f --tail=50

status:
	@echo "Orchestrator Status:"
	@echo ""
	@kubectl get pods -n cortex-system -l app=cortex-orchestrator
	@echo ""
	@echo "Recent logs:"
	@kubectl logs -n cortex-system -l app=cortex-orchestrator --tail=10

# Development helpers
dev-install:
	@echo "Installing development dependencies..."
	pip install -e ".[dev]"
	@echo "✅ Dev dependencies installed"

dev-run:
	@echo "Running orchestrator locally (requires kubeconfig)..."
	CONFIG_PATH=k8s/configmap.yaml python -m server.main

port-forward:
	@echo "Port forwarding orchestrator (8080=MCP, 9090=metrics)..."
	kubectl port-forward -n cortex-system svc/cortex-orchestrator 8080:8080 9090:9090
