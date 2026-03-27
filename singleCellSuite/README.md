# `singleCellSuite/`

This folder contains lightweight utilities for running and visualizing single-cell models outside the full network.

## Files

- `_run_model.py`: shared implementation for the single-cell ramp protocol.
- `run_pc2b.py`: runs `cells/PC2B.json`.
- `run_bilash_vip.py`: runs `cells/BilashVIP.json`.
- `run_olm_cell.py`: runs `cells/OLMCell.json`.
- `run_bilash_pyr.py`: runs `cells/BilashPYR.json`.
- `plotGeometry.py`: renders a cell JSON morphology to a PNG without needing the full network.
- `results/`: default output location for generated CSV and PNG files.

## Ramp Protocol

`_run_model.py` applies a long current-clamp protocol with piecewise current amplitudes and records:

- time
- soma voltage
- injected current

The results are written as:

- `<model>_trace.csv`
- `<model>_trace.png`

## Mechanism Loading

The runner tries to load compiled NEURON mechanisms from the repo, preferring:

- `arm64/libnrnmech.dylib`
- `arm64/.libs/libnrnmech.dylib`
- `x86_64/...` if present

## Typical Usage

```bash
python3 singleCellSuite/run_pc2b.py
python3 singleCellSuite/run_bilash_vip.py --output-dir singleCellSuite/results
python3 singleCellSuite/plotGeometry.py BilashVIP --projection xy
```

## Why This Folder Exists

These scripts are useful for:

- quick sanity checks on imported cell JSON rules
- reproducing the Figure 8 ramp protocol on a single cell
- inspecting geometry without building the full CA1 network
