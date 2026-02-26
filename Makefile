.PHONY: install test test-cov lint setup-db seed run-scrape help

SCRIPTS_DIR = skills/competitor-monitoring/scripts
PYTHON = $(HOME)/miniconda3/bin/python3

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies
	$(PYTHON) -m pip install -r $(SCRIPTS_DIR)/requirements.txt
	$(PYTHON) -m pip install pytest pytest-cov

test: ## Run unit tests
	$(PYTHON) -m pytest tests/ -v -x

test-cov: ## Run tests with coverage report
	$(PYTHON) -m pytest tests/ -v --cov=skills/competitor-monitoring/scripts --cov-report=term-missing

lint: ## Run ruff linter
	ruff check $(SCRIPTS_DIR)/ tests/

setup-db: ## Initialize MongoDB indexes
	$(PYTHON) $(SCRIPTS_DIR)/db.py setup

seed: ## Seed competitors from settings.yaml
	$(PYTHON) $(SCRIPTS_DIR)/manage_sources.py seed

list-sources: ## List all monitored sources
	$(PYTHON) $(SCRIPTS_DIR)/manage_sources.py list

scrape-all: ## Scrape all active sources
	@echo "Use OpenClaw skill for full pipeline. For single URL:"
	@echo "  $(PYTHON) $(SCRIPTS_DIR)/scrape.py <url>"

detect: ## Run change detection on all sources
	$(PYTHON) $(SCRIPTS_DIR)/detect_changes.py --all

report-weekly: ## Generate weekly report
	$(PYTHON) $(SCRIPTS_DIR)/generate_report.py --weekly

report-monthly: ## Generate monthly report
	$(PYTHON) $(SCRIPTS_DIR)/generate_report.py --monthly

sentiment: ## Analyze sentiment for all competitors
	$(PYTHON) $(SCRIPTS_DIR)/analyze_sentiment.py --all

partnerships: ## Detect partnerships across all competitors
	$(PYTHON) $(SCRIPTS_DIR)/detect_partnerships.py --all

cron-print: ## Print OpenClaw cron job commands
	$(PYTHON) $(SCRIPTS_DIR)/setup_cron.py --print

# Dashboard
api-dev: ## Start FastAPI dev server (port 8000)
	$(PYTHON) -m uvicorn api.main:app --reload --port 8000

frontend-install: ## Install frontend dependencies
	cd frontend && npm install

frontend-dev: ## Start React dev server (port 5173)
	cd frontend && npm run dev

frontend-build: ## Build React for production
	cd frontend && npm run build

dashboard: frontend-build api-dev ## Build frontend + start API server
