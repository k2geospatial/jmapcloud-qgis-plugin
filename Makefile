VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
BLACK := $(VENV)/bin/black
ISORT := $(VENV)/bin/isort
FLAKE8 := $(VENV)/bin/flake8
BANDIT := $(VENV)/bin/bandit
DETECT_SECRETS := $(VENV)/bin/detect-secrets
PLUGIN_NAME := JMapCloud
DIST_DIR := dist
PACKAGE_DIR := $(DIST_DIR)/$(PLUGIN_NAME)
ZIP_PATH := $(DIST_DIR)/$(PLUGIN_NAME).zip

.PHONY: help install-dev format lint scan check clean-dist package

help:
	@echo "Available targets:"
	@echo "  make install-dev  Install development dependencies into .venv"
	@echo "  make format       Sort imports and format Python code"
	@echo "  make lint         Run Flake8 checks"
	@echo "  make scan         Run Bandit and detect-secrets"
	@echo "  make check        Run format, lint, and scan steps"
	@echo "  make package      Build a QGIS plugin zip in dist/"
	@echo "  make clean-dist   Remove built package artifacts"

install-dev:
	$(PIP) install -r requirements-dev.txt

format:
	$(ISORT) .
	$(BLACK) .

lint:
	$(FLAKE8) .

scan:
	$(BANDIT) -r . -x ./.venv,./.venv-*,./dist,./build,./.git,./.vscode
	$(DETECT_SECRETS) scan --exclude-files '(^\.venv/|^dist/|^build/|^\.git/|^\.vscode/|\.DS_Store$$)'

check: format lint scan

clean-dist:
	rm -rf $(DIST_DIR)

package: clean-dist
	mkdir -p $(PACKAGE_DIR)
	rsync -a ./ $(PACKAGE_DIR)/ \
		--exclude ".DS_Store" \
		--exclude "__MACOSX" \
		--exclude "__pycache__/" \
		--exclude "*.py[cod]" \
		--exclude ".git/" \
		--exclude ".github/" \
		--exclude ".gitignore" \
		--exclude ".env" \
		--exclude ".env.*" \
		--exclude ".python-version" \
		--exclude ".pytest_cache/" \
		--exclude ".venv/" \
		--exclude ".venv-*/" \
		--exclude ".vscode/" \
		--exclude ".idea/" \
		--exclude ".vs/" \
		--exclude ".flake8" \
		--exclude "Makefile" \
		--exclude "pyproject.toml" \
		--exclude "requirements*.txt" \
		--exclude "i18n/*.ts" \
		--exclude "i18n/*.pro" \
		--exclude "dist/" \
		--exclude "build/" \
		--exclude "tests/" \
		--exclude "*.zip"
	cd $(DIST_DIR) && zip -r $(PLUGIN_NAME).zip $(PLUGIN_NAME) \
		-x "*.DS_Store" \
		-x "*__pycache__*" \
		-x "*.git*" \
		-x "*.github*" \
		-x "*.env*" \
		-x "*.venv*" \
		-x "*.vscode*" \
		-x "*.idea*" \
		-x "*.vs*" \
		-x "*__MACOSX*" \
		-x "*.python-version" \
		-x "*.gitignore" \
		-x "*.pytest_cache*" \
		-x "*.flake8" \
		-x "*Makefile" \
		-x "*pyproject.toml" \
		-x "*requirements*.txt" \
		-x "*.ts" \
		-x "*.pro" \
		-x "*tests*" \
		-x "*.zip"
	@echo "Created $(ZIP_PATH)"
