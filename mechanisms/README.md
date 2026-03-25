# `mechanisms/`

This folder contains the NEURON `.mod` source files used by the cell models.

## Organization

- `PYR/`: mechanisms used by the pyramidal cell models.
- `OLM/`: mechanisms used by the OLM interneuron model.
- `VIP/`: mechanisms used by the VIP cell models.
- `PV/`: PV-related mechanisms retained for completeness, though PV cells are not currently instantiated by `src/netParams.py`.
- `vecstim.mod`: support mechanism for event-driven input sources.
- `MyExp2SynBB.mod`: additional synapse mechanism retained in the repo.

## Workflow

Edit the `.mod` files here, then compile them with:

```bash
nrnivmodl mechanisms
```

On Apple Silicon this produces the `arm64/` build directory already present in this repository.

## Important Notes

- Do not edit the generated `arm64/*.c`, `arm64/*.o`, `special`, or shared libraries by hand.
- If you change a mechanism name or remove a mechanism, verify that the corresponding cell JSON in `cells/` and any currentscape trace definitions in `src/run_best_vip_conditions_currentscape.py` still match.
