# CA1 Model Starter

This repository now contains a working starter scaffold for the CA1 modeling effort described in the local planning documents:

- Aim 2 first: build a configurable CA1 microcircuit around `PYR`, `OLM`, `VIP`, and `IS3` populations.
- Aim 1 in parallel: keep the pyramidal cell model swappable, with room for TRPM4/ICAN recalibration and nanodomain parameter sweeps.
- User-facing control stays in config files plus a small CLI.

The scaffold is intentionally lightweight. It now builds NetPyNE-shaped payloads and will execute real NetPyNE runs when the target runtime environment is available, while still falling back to manifest-only output if NetPyNE is missing.

## Layout

Key directories:

- `configs/`: JSON-compatible YAML example configurations.
- `mechanisms/`: placeholder `.mod` files for TRPM4 and ICAN.
- `hoc/`: starter HOC templates for legacy cell definitions.
- `src/ca1/`: Python package with config parsing, plugin registry, builders, models, workflows, and analysis helpers.
- `scripts/`: local runner, mod compiler helper, and SLURM submission stub.
- `tests/`: lightweight regression tests for config validation and build assembly.

## Quick Start

The expected runtime is the `M1_CEBRA` conda environment. The helper scripts default to that environment and can be overridden with `CA1_CONDA_ENV`.

Run directly through conda:

```bash
conda run -n M1_CEBRA env PYTHONPATH=src python -m ca1 run configs/microcircuit/base.yaml
conda run -n M1_CEBRA env PYTHONPATH=src python -m ca1 sweep configs/microcircuit/parameter_sweeps/ach_gain_grid.yaml
conda run -n M1_CEBRA env PYTHONPATH=src python -m ca1 analyze outputs/microcircuit_base
```

Or use the helper scripts:

```bash
./scripts/compile_mods.sh
./scripts/run_local.sh configs/microcircuit/base.yaml
./scripts/submit_slurm.sh configs/microcircuit/base.yaml ca1-microcircuit
```

## Notes

- The example config files use JSON syntax stored in `.yaml` files. JSON is valid YAML, which keeps the bootstrap parser stdlib-friendly.
- `python -m ca1` is supported via `src/ca1/__main__.py`.
- `scripts/*.sh` default to `M1_CEBRA` via `conda run -n`, but fall back to the current shell if conda is unavailable.
- Replace the placeholder `.mod` and `.hoc` files with the calibrated mechanisms and templates before compiling or running NEURON.

## Immediate Next Extensions

1. Replace the placeholder cell wrappers with real Carol PYR / OLM / VIP / IS-3 integrations.
2. Wire `network_builder.py` into real NetPyNE `netParams` and `simConfig` objects.
3. Expand `workflows/batch_sweep.py` to emit NetPyNE batch jobs for Tigerfish.
4. Add experimental metrics for plateau onset, burst structure, and BTSP-related readouts.
