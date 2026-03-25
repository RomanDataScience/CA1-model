# `src/config/`

This folder contains the configuration loaders used to populate the global NetPyNE `SimConfig`.

## Loader Structure

`src/config/__init__.py` defines two entry points:

- `load_base_config(cfg)`: applies the base loaders in order.
- `load_derived_config(cfg)`: computes fields derived from the base configuration.

Base loader order:

1. `sim.py`
2. `cells.py`
3. `stimuli.py`
4. `synapses.py`
5. `recording.py`

Derived quantities are then added by `derived.py`.

## Files

- `sim.py`: low-level simulation settings such as `dt`, CVode, seeds, save behavior, and default output folder.
- `cells.py`: cell counts, paths to the JSON cell rules, and PC2B/VIP condition toggles.
- `stimuli.py`: theta-burst timing, VIP batch protocol timing, SC/PP/MS drive counts, and VIP target sections.
- `synapses.py`: synaptic unit weights, pathway scaling, recurrent connection weights, delays, and synapse mechanism definitions.
- `recording.py`: which populations to record, trace definitions, and default analysis plot settings.
- `derived.py`: computes derived schedules, weights, windows, labels, `recordCells`, and default analysis configuration.

## Key Derived Fields

`derived.py` computes:

- `duration`
- `thetaSpikeTimes`
- `thetaCycleWindows`
- `vipBatchNoMsWindows`
- `vipBatchMsWindows`
- `MS_train`
- `thetaScSites` and `thetaPpSites`
- effective pathway weights onto PYR and VIP
- `simLabel`
- `recordCells`
- default `cfg.analysis` entries

## How To Change Parameters Safely

If a script edits values like `nMSweight`, `factorSynVIP`, `vipBatchVInit`, or `applyControlPC2B`, it must call `refresh_cfg()` afterward so the dependent fields stay consistent. This is especially important before importing or reloading `netParams.py`.

## `v_init` In This Repo

The base simulation config in `sim.py` defines:

- `cfg.hParams["v_init"]`: general simulation initialization voltage
- `cfg.vipBatchVInit`: batch-search-specific initialization voltage used by `src/init_vip_batch.py`

During the VIP-only Optuna workflow, the batch runner copies `cfg.vipBatchVInit` into `cfg.hParams["v_init"]` before initializing the simulation. The replay utilities in `src/run_best_vip_trial.py` and the related condition scripts now do the same, so selected Optuna trials preserve the optimized initial voltage.
