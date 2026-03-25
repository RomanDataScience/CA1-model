# `mechanisms/VIP/`

This folder contains the `.mod` mechanisms used by the VIP cell models.

Key mechanism groups:

- intrinsic sodium and potassium currents: `nafcr`, `kdrcr`, `IKscr`, `gskch`, `iCcr`
- calcium currents and calcium handling: `cancr`, `car_VIP`, `cal_VIP`, `calH_VIP`, `cat_VIP`, `ccanl`, `cad_VIP`
- leak and h-current mechanisms: `pas` in the JSON rules, plus `Ih_VIP`, `h_VIP`
- auxiliary mechanisms inherited from related model families: `kad`, `kap`, `km_VIP`, `mykca`, `bgka`, `constant`
- synaptic helper mechanisms: `my_exp2syn`, `nmda`, `ichan2vip`, `ichan2cck`

These mechanism names are used by:

- `cells/BilashVIP.json`
- leak-scaling logic in `src/netParams.py`
- VIP batch simulations in `src/init_vip_batch.py`
- currentscape exports for the VIP soma
