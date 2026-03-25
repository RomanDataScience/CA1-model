# `tests/`

This folder contains smoke tests and integration-style regression scripts for imported cells and legacy protocol comparisons.

## Files

- `test_import_bilash_cell.py`: imports Bilash pyramidal and VIP cells into NetPyNE, exports cleaned JSON, and runs a short simulation.
- `test_import_olm_cell.py`: loads the OLM HOC model, imports it into NetPyNE, exports JSON, and runs a brief simulation.
- `test_import_figure8control_hoc.py`: legacy Figure 8 import workflow for the pyramidal model and morphology export.
- `test_sim8_hoc_netpyne.py`: compares a legacy Figure 8 HOC run with an imported NetPyNE cell and writes CSV traces.
- `test_sim8_hoc_netpyne_3.py`: compares the legacy Figure 8 HOC run with the saved `cells/PC2B.json` model.
- `empty.hoc`: minimal helper file used during one of the import workflows.

## Important Caveats

- These tests require `neuron` and `netpyne`.
- Several tests also require compiled mechanisms under `arm64/` or `x86_64/`.
- Some tests expect legacy source-model directories such as `original_models/` and result folders such as `NetPyNE_comparison/`, which are not present in the current repo snapshot.
- Two of the legacy test files invoke their main test function at import time, so they behave more like executable regression scripts than strict pytest-style unit tests.

## Practical Usage

Use these files as:

- smoke tests when the full model environment is available
- reference scripts for how the JSON cell rules were originally generated
- protocol-comparison helpers for the Figure 8 ramp workflow

If you want a smaller current smoke test set, the single-cell runners in `singleCellSuite/` are often the easier starting point.
