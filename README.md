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

This repository uses a local Python virtual environment in [`.venv`](/Users/jacobchaar/Documents/k2geospatial/jmapcloud-qgis-plugin/.venv) for development tooling.

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

### Environment Files

Create a local `.env` at the root of the repository for development so VS Code can load the QGIS Python packages.

Example:

```bash
PYTHONPATH=/Applications/QGIS-final-4_0_0.app/Contents/Frameworks/lib/python3.12/site-packages
```

This path should point to your local QGIS Python `site-packages` directory.

VS Code references this file through [`.vscode/settings.json`](/Users/jacobchaar/Documents/k2geospatial/jmapcloud-qgis-plugin/.vscode/settings.json).

VS Code uses it through:

- `python.terminal.useEnvFile`
- `python.envFile=${workspaceFolder}/.env`

This is mainly editor and terminal configuration so imports resolve correctly during development. The plugin code does not appear to load `.env` directly.

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

If you regularly work on this plugin in VS Code, it also helps to point the editor at the correct Python interpreter, typically [`.venv/bin/python`](/Users/jacobchaar/Documents/k2geospatial/jmapcloud-qgis-plugin/.venv/bin/python).

### Formatting Rules

Formatting is configured in [pyproject.toml](/Users/jacobchaar/Documents/k2geospatial/jmapcloud-qgis-plugin/pyproject.toml):

- `black` line length: `88`
- `black` target version: `py312`
- `isort` profile: `black`

### Packaging

To build the distributable QGIS plugin archive:

```bash
make package
```

The generated zip file is written to [dist/JMapCloud.zip](/Users/jacobchaar/Documents/k2geospatial/jmapcloud-qgis-plugin/dist/JMapCloud.zip).
