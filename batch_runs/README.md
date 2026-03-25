# `batch_runs/`

This is the current root-level output location for Optuna study runs.

## Layout

Each study gets its own subdirectory:

```text
batch_runs/<study-label>/
```

The current default study label defined in `src/batch_vip_optuna.py` is:

```text
vip_optuna_theta_gate
```

## Typical Contents Of A Study Folder

- `*.optuna.journal.log`: Optuna journal storage with trial parameters and objective values.
- `*.sh`: generated shell launchers.
- `*.run`: scheduler or batch-tool bookkeeping files.
- `*.out` and `*.sgl`: optional scheduler side products depending on the backend.
- `*_ms_off_data.json`: NetPyNE output for the no-MS phase of a trial.
- `*_ms_on_data.json`: NetPyNE output for the MS-on phase of a trial.
- `*_vip_traces_ms_off_ms_on.png`: combined VIP trace figure for a trial.

## Relationship To The Code

- written by `src/batch_vip_optuna.py` and `src/init_vip_batch.py`
- read by `src/run_best_vip_trial.py`
- also used by `src/run_best_vip_conditions.py` and `src/run_best_vip_conditions_currentscape.py`

## Current Search Parameters

The Optuna search currently varies:

- `factorSynVIP`
- `nMSweight`
- `synMechParams.nACh_IS3.tau2`
- `nMSinputs`
- `nVipScInputs`
- `nVipPpInputs`
- `vipInputResistanceScale`
- `vipBatchVInit`

`vipBatchVInit` is searched over `-80.0` to `-50.0` mV and is used as the initialization voltage for the VIP-only batch runs.

## Important Note

Older artifacts may still exist under `src/batch_runs/`, including snapshots from earlier study labels such as `vip_optuna_theta_gate_v3`. That older path is deprecated and should not be used for new runs.
