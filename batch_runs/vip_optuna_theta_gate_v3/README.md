# `vip_optuna_theta_gate_v3`

This folder stores the artifacts for the current VIP Optuna study defined in `src/batch_vip_optuna.py`.

## Study Purpose

The study tunes VIP-related parameters for the reduced batch protocol that compares:

- `ms_off`
- `ms_on`

The objective is computed from VIP firing behavior across theta-cycle windows. The loss favors:

- low or zero VIP spiking during `ms_off`
- a target number of spikes per cycle during `ms_on`
- minimal spikes outside the designated windows

## Search Space

The current study varies:

- `factorSynVIP`
- `nMSweight`
- `synMechParams.nACh_IS3.tau2`
- `nMSinputs`
- `nVipScInputs`
- `nVipPpInputs`
- `vipInputResistanceScale`

## File Naming

For a trial number `N`, the directory typically contains:

- `vip_optuna_theta_gate_v3_N.sh`
- `vip_optuna_theta_gate_v3_N.run`
- `vip_optuna_theta_gate_v3_N_ms_off_data.json`
- `vip_optuna_theta_gate_v3_N_ms_on_data.json`
- `vip_optuna_theta_gate_v3_N_vip_traces_ms_off_ms_on.png`

The journal file:

- `vip_optuna_theta_gate_v3_optuna.optuna.journal.log`

records the full parameter history and the objective values used by Optuna.

## Reading Results

Use:

- `src/run_best_vip_trial.py` to replay one selected trial in the full network
- `src/run_best_vip_conditions.py` to test the four named condition variants
- `src/run_best_vip_conditions_currentscape.py` to generate full-network currentscape summaries
