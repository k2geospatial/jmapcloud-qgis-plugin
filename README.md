# JMap Cloud QGIS Plugin

JMap Cloud is a QGIS plugin maintained by K2 Geospatial. It lets you work with JMap Cloud projects directly in QGIS: open cloud-hosted map projects, view or edit data in QGIS, and export QGIS projects back to JMap Cloud.

## Overview

- Plugin name: `JMap Cloud`
- Current version: `1.0.4`
- Author: `K2 Geospatial`
- QGIS compatibility: `3.34` to `4.99`
- User guide: <https://docs.jmapcloud.io/en/jmap-cloud-plugin-for-qgis/jmap-cloud-plugin-user-guide>
- Issues: <https://github.com/k2geospatial/jmapcloud-qgis-plugin/issues>
- Repository: <https://github.com/k2geospatial/jmapcloud-qgis-plugin>

You must have a valid JMap Cloud account to use this plugin.

## Optional Dependency

The `Layer Tree Icons` plugin is optional. It changes some icons in the QGIS layer legend and does not work on macOS.

## Development Configuration

This repository uses a local Python virtual environment in .venv for development tooling.

### Prerequisites

- Python `3.12`
- `make`

### Initial Setup

Create the virtual environment and install development dependencies:

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
```

You can also use the provided target once the virtual environment exists:

```bash
make install-dev
```

### Formatting and Checks

The project uses:

- `isort` for import sorting
- `black` for code formatting
- `flake8` and `flake8-qgis` for linting
- `bandit` and `detect-secrets` for security and secret scanning

Available commands:

```bash
make format
make lint
make scan
make check
```

`make format` currently formats the whole repository.

To format a single file instead, run:

```bash
.venv/bin/isort path/to/file.py
.venv/bin/black path/to/file.py
```

### Make Targets

The `Makefile` also includes helper commands for the Qt Designer and translation workflow:

```bash
make designer
make ui-compile UI=ui/ui_files/export_layer_dialog_base.ui
make translations-update
make translations-compile
```

- `make designer` opens Qt Designer when the `designer` binary is available on your `PATH`.
- `make ui-compile UI=...` converts a `.ui` file into its generated Python file under `ui/py_files`. For example, `export_layer_dialog_base.ui` generates [export_layer_dialog_base_ui.py](ui/py_files/export_layer_dialog_base_ui.py).
- `make translations-update` refreshes the `.ts` translation source files from [i18n/jmap_cloud.pro](i18n/jmap_cloud.pro) using `lupdate-pro`. Run this after changing translatable strings in Python or UI files.
- `make translations-compile` compiles a `.ts` file such as [i18n/jmap_cloud_fr.ts](i18n/jmap_cloud_fr.ts) into the corresponding `.qm` file using `lrelease`. Run this after updating translations so QGIS can use the latest compiled catalog.

If the Qt tools are not on your `PATH`, the targets also support explicit overrides such as `DESIGNER=/path/to/designer`, `PYUIC=/path/to/pyuic6`, `LUPDATE_PRO=/path/to/lupdate-pro`, and `LRELEASE=/path/to/lrelease`.

### VS Code Auto Format

If VS Code is configured for Python format-on-save, saving the current file will automatically format it.

Recommended VS Code settings:

```json
{
  "editor.formatOnSave": true,
  "[python]": {
    "editor.defaultFormatter": "ms-python.black-formatter"
  },
  "isort.args": ["--profile", "black"]
}
```

This project uses `black` and `isort`, so automatic formatting on save depends on having the relevant extensions installed and configured.

### Recommended VS Code Extensions

- `ms-python.python` for Python language support and interpreter selection
- `ms-python.black-formatter` for `black` formatting support
- `ms-python.isort` for import sorting with `isort`
- `ms-python.flake8` for inline linting with `flake8`
- `eamodio.gitlens` for Git history, blame, and file insight in the editor

If you regularly work on this plugin in VS Code, it also helps to point the editor at the correct Python interpreter, typically `.venv/bin/python`.

### Formatting Rules

Formatting is configured in [pyproject.toml](pyproject.toml):
    
- `black` line length: `88`
- `black` target version: `py312`
- `isort` profile: `black`

### Packaging

To build the distributable QGIS plugin archive:

```bash
make package
```

The generated zip file is written to [dist/JMapCloud.zip](dist/JMapCloud.zip).
