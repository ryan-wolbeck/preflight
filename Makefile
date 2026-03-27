# ────────────────────────────────────────────────────────────────────────────
# preflight — Makefile
# Targets: install, test, format, lint, check, coverage, clean, build, publish
# ────────────────────────────────────────────────────────────────────────────

PYTHON     ?= python
PIP        ?= pip
CONDA      ?= conda
ENV_NAME   ?= preflight
TEST_DIR   := tests
SRC_DIR    := preflight
DIST_DIR   := dist

.PHONY: help env env-update install install-dev \
        test test-unit test-integration test-fast test-stdlib coverage \
        format format-check lint typecheck check \
        clean build publish

# ── Default target ────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  preflight — available make targets"
	@echo "  ─────────────────────────────────────────────────────────────────"
	@echo "  make env          Create the conda environment (preflight)"
	@echo "  make install      Install package + runtime deps"
	@echo "  make install-dev  Install package + runtime + dev deps (black, pytest)"
	@echo ""
	@echo "  make test         Run full pytest suite with coverage"
	@echo "  make test-unit    Run unit tests only (exclude integration)"
	@echo "  make test-integration Run integration tests only"
	@echo "  make test-fast    Run pytest without coverage"
	@echo "  make test-stdlib  Run stdlib unittest runner (no pytest needed)"
	@echo "  make coverage     Generate HTML coverage report → htmlcov/"
	@echo ""
	@echo "  make format       Auto-format with black"
	@echo "  make format-check Check formatting without writing (CI-safe)"
	@echo "  make lint         Lint with black --check"
	@echo "  make typecheck    Static type checks with mypy"
	@echo "  make check        format-check + lint + typecheck (full CI gate)"
	@echo ""
	@echo "  make clean        Remove build artefacts and caches"
	@echo "  make build        Build sdist + wheel"
	@echo "  make publish      Upload to PyPI via twine"
	@echo ""

# ── Environment setup (conda) ─────────────────────────────────────────────────
env:
	$(CONDA) env create -f environment.yml
	@echo ""
	@echo "  ✓ Conda environment '$(ENV_NAME)' created."
	@echo "  → Activate with:  conda activate $(ENV_NAME)"
	@echo ""

env-update:
	$(CONDA) env update -f environment.yml --prune
	@echo "  ✓ Conda environment updated."

# ── Installation ──────────────────────────────────────────────────────────────
install:
	$(PIP) install .

install-dev:
	$(PIP) install -e ".[dev]"

# ── Testing ───────────────────────────────────────────────────────────────────
test:
	$(PYTHON) -m pytest $(TEST_DIR) -v --tb=short \
		--cov=$(SRC_DIR) --cov-report=term-missing

test-unit:
	$(PYTHON) -m pytest $(TEST_DIR) -m "not integration" -v --tb=short \
		--cov=$(SRC_DIR) --cov-report=term-missing

test-integration:
	$(PYTHON) -m pytest $(TEST_DIR) -m "integration" -v --tb=short

test-fast:
	$(PYTHON) -m pytest $(TEST_DIR) -v --tb=short

# Stdlib fallback — no pytest required (useful in restricted environments)
test-stdlib:
	PYTHONPATH=. $(PYTHON) $(TEST_DIR)/run_tests.py

# ── Coverage ──────────────────────────────────────────────────────────────────
coverage:
	$(PYTHON) -m pytest $(TEST_DIR) \
		--cov=$(SRC_DIR) \
		--cov-report=html:htmlcov \
		--cov-report=term-missing
	@echo "  ✓ Coverage report written to htmlcov/index.html"

# ── Formatting (black) ────────────────────────────────────────────────────────
format:
	@command -v black >/dev/null 2>&1 || { echo "black not found — run: make install-dev"; exit 1; }
	black $(SRC_DIR) $(TEST_DIR)
	@echo "  ✓ Formatted with black."

format-check:
	@command -v black >/dev/null 2>&1 || { echo "black not found — run: make install-dev"; exit 1; }
	black --check --diff $(SRC_DIR) $(TEST_DIR)

# ── Linting (black-only) ──────────────────────────────────────────────────────
lint:
	@command -v black >/dev/null 2>&1 || { echo "black not found — run: make install-dev"; exit 1; }
	black --check --diff $(SRC_DIR) $(TEST_DIR)

typecheck:
	@command -v mypy >/dev/null 2>&1 || { echo "mypy not found — run: make install-dev"; exit 1; }
	mypy $(SRC_DIR)

# ── Combined CI gate ──────────────────────────────────────────────────────────
check: format-check lint typecheck
	@echo "  ✓ All checks passed."

# ── Build & Publish ───────────────────────────────────────────────────────────
clean:
	rm -rf $(DIST_DIR) build *.egg-info .pytest_cache .coverage htmlcov
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null; true
	find . -type f -name "*.pyc" -delete 2>/dev/null; true
	@echo "  ✓ Clean."

build: clean
	$(PYTHON) -m build
	@echo "  ✓ Build artefacts in $(DIST_DIR)/"

publish: build
	@command -v twine >/dev/null 2>&1 || { echo "twine not found — run: pip install twine"; exit 1; }
	twine upload $(DIST_DIR)/*
