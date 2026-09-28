# CreaseIQ — IPL Match Intelligence Platform

> Validated IPL data pipeline, statistically sound analytics and a leakage-safe, calibrated pre-match win-probability engine.
> *Build Your Own Project — VITyarthi · Machine Learning*

**Status:** work in progress. See [PROGRESS.md](PROGRESS.md).

## Overview
CreaseIQ turns a raw, messy IPL match file (1,243 matches, 2008–2026) into:

- a clean, canonical relational dataset;
- analytics that report their uncertainty;
- a win-probability model evaluated honestly: walk-forward validation, calibration and baselines, with no leakage.

## Quick start (Windows / macOS / Linux, Python ≥ 3.12)

```bash
python -m venv .venv
```

Activate the virtual environment. On Windows run `.venv\Scripts\activate`; on macOS or Linux run `source .venv/bin/activate`.

```bash
pip install -r requirements.txt -r requirements-dev.txt && pip install -e . --no-deps
```

```bash
creaseiq --help
```

## Testing

```bash
pytest
```

## Disclaimer
CreaseIQ is an educational analytics project. It is **not** betting, fantasy-sports or financial advice. Match data comes from Cricsheet (cricsheet.org) under the Open Data Commons Attribution License v1.0.
