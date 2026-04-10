VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
BLACK := $(VENV)/bin/black
ISORT := $(VENV)/bin/isort
FLAKE8 := $(VENV)/bin/flake8
BANDIT := $(VENV)/bin/bandit
DETECT_SECRETS := $(VENV)/bin/detect-secrets
DESIGNER ?= $(shell command -v designer 2>/dev/null)
PYUIC ?= $(shell command -v pyuic6 2>/dev/null)
LUPDATE_PRO ?= $(shell command -v lupdate-pro 2>/dev/null)
LRELEASE ?= $(shell command -v lrelease 2>/dev/null)
UI ?=
UI_PY_DIR ?= ui/py_files
UI_BASE_NAME = $(basename $(notdir $(UI)))
UI_PY_NAME = $(if $(filter %_base,$(UI_BASE_NAME)),$(UI_BASE_NAME)_ui.py,$(UI_BASE_NAME)_base_ui.py)
UI_PY_FILE = $(UI_PY_DIR)/$(UI_PY_NAME)
TS ?= i18n/jmap_cloud_fr.ts
PRO_FILE ?= i18n/jmap_cloud.pro
PLUGIN_NAME := JMapCloud
DIST_DIR := dist
PACKAGE_DIR := $(DIST_DIR)/$(PLUGIN_NAME)
ZIP_PATH := $(DIST_DIR)/$(PLUGIN_NAME).zip

.PHONY: help install-dev format lint scan check clean-dist package designer ui-compile translations-update translations-compile

help:
	@echo "Available targets:"
	@echo "  make install-dev  Install development dependencies into .venv"
	@echo "  make format       Sort imports and format Python code"
	@echo "  make lint         Run Flake8 checks"
	@echo "  make scan         Run Bandit and detect-secrets"
	@echo "  make check        Run format, lint, and scan steps"
	@echo "  make designer     Open Qt Designer"
	@echo "  make ui-compile UI=path/to/file.ui [UI_PY_DIR=ui/py_files]"
	@echo "  make translations-update [PRO_FILE=i18n/jmap_cloud.pro]"
	@echo "  make translations-compile [TS=i18n/jmap_cloud_fr.ts]"
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

designer:
ifndef DESIGNER
	$(error Qt Designer not found on PATH. Install Qt tools or run with DESIGNER=/path/to/designer)
endif
	"$(DESIGNER)"

ui-compile:
ifndef PYUIC
	$(error pyuic6 not found on PATH. Install PyQt6/Qt tools or run with PYUIC=/path/to/pyuic6)
endif
ifeq ($(strip $(UI)),)
	$(error UI is required. Example: make ui-compile UI=ui/ui_files/export_layer_dialog_base.ui)
endif
	@mkdir -p "$(UI_PY_DIR)"
	"$(PYUIC)" "$(UI)" -o "$(UI_PY_FILE)"
	@echo "Created $(UI_PY_FILE)"

translations-update:
ifndef LUPDATE_PRO
	$(error lupdate-pro not found on PATH. Install Qt Linguist tools or run with LUPDATE_PRO=/path/to/lupdate-pro)
endif
	"$(LUPDATE_PRO)" "$(PRO_FILE)"
	@echo "Updated translation sources from $(PRO_FILE)"

translations-compile:
ifndef LRELEASE
	$(error lrelease not found on PATH. Install Qt Linguist tools or run with LRELEASE=/path/to/lrelease)
endif
	"$(LRELEASE)" "$(TS)"
	@echo "Compiled $(TS)"

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
