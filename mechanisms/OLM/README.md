# `mechanisms/OLM/`

This folder contains `.mod` files used by the OLM interneuron model.

Representative mechanisms include:

- sodium channel variants: `Nasoma`, `Nadend`, `Naaxon`
- delayed rectifiers: `Ikdrf`, `Ikdrs`, `Ikdrfaxon`, `Ikdrsaxon`
- A-type and M-type currents: `IKa`, `IMmintau`
- calcium and calcium-dependent currents: `ICaL`, `ICaT`, `IKCa`, `cad_OLM`
- passive and h-current mechanisms: `Ipasssd`, `Ipassaxon`, `Ih_OLM`

These mechanism names appear directly in `cells/OLMCell.json` and in the currentscape configuration used by `src/run_best_vip_conditions_currentscape.py`.
