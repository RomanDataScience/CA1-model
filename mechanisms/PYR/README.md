# `mechanisms/PYR/`

This folder contains the `.mod` mechanisms used by the pyramidal cell model (`PC2B`) and related import workflows.

The files cover:

- sodium channels: `na3`, `na3dend`, `na3notrunk`, `nax`, `Nav16_a`, `nap`
- potassium channels: `kv1`, `kd`, `kdr`, `km`, `kca`, `kcasimple`, `Kv2like`, `PotassiumInwardRectifier`
- calcium channels and calcium handling: `cal`, `cal4`, `calH`, `car`, `cat`, `cad`, `cagk`
- ICAN/TRPM-related currents: `ican`, `ican_nov`, `icand`
- synaptic/input helpers: `nmdanet`, `exp2i`, `stim2`, `netstims`, `CurrentClamp`

These names are reflected in:

- `cells/PC2B.json`
- control-condition edits in `src/netParams.py`
- currentscape trace definitions for `PC2B`

If you modify these files, recompile the mechanisms before running the network or the tests.
