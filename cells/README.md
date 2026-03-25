# `cells/`

This folder stores the NetPyNE JSON cell rules used by the current CA1 model.

## Files

- `PC2B.json`: pyramidal cell rule used for the CA1 principal cell.
- `OLMCell.json`: OLM interneuron rule imported from the legacy HOC model.
- `BilashVIP.json`: VIP interneuron rule used by the active model.
- `BilashPYR.json`: Bilash pyramidal-cell rule used mainly by the single-cell utilities.

## Format

Each file is a serialized NetPyNE cell rule containing sections, geometry, mechanisms, ions, and topology. These files are loaded directly by `src/netParams.py` or by the single-cell utilities in `singleCellSuite/`.

Typical top-level keys:

- `conds`
- `secs`
- `secLists`
- `globals`

## How These Files Are Used

- `src/netParams.py` loads `PC2B.json`, `OLMCell.json`, and `BilashVIP.json`.
- `singleCellSuite/_run_model.py` can run any of these JSON rules as a one-cell model.
- Some tests export regenerated JSON rules back into this folder after importing legacy HOC or Python cell definitions.

## Editing Guidance

- Treat these files as canonical imported cell rules for the current repo snapshot.
- If you regenerate them from source models, verify section names carefully. Several scripts depend on names such as `soma`, `radTprox`, `radTmed`, `lm_thick1`, and the `apic_*` sections.
- Any mechanism change in the JSON should stay consistent with the compiled `.mod` library in `arm64/`.
