from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Optional

import pytest


def _require_neuron():
    try:
        from neuron import h  # type: ignore
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"NEURON not available: {exc}", allow_module_level=True)
    return h


def _require_netpyne():
    try:
        from netpyne import specs, sim  # type: ignore
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"NetPyNE not available: {exc}", allow_module_level=True)
    return specs, sim


_MECHS_LOADED: bool = False
_MECH_PATH: Optional[Path] = None


def _load_compiled_mechanisms(h, candidates: Iterable[Path]) -> Path:
    """Load one of the compiled mechanism libraries for NEURON."""

    global _MECHS_LOADED, _MECH_PATH
    if _MECHS_LOADED and _MECH_PATH is not None:
        return _MECH_PATH

    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            h.nrn_load_dll(str(candidate))
        except RuntimeError as exc:  # pragma: no cover
            msg = str(exc)
            if "already exists" not in msg and "hocobj_call error" not in msg:
                raise
        except OSError as exc:  # pragma: no cover
            pytest.skip(
                f"Compiled mechanisms found at {candidate} but failed to load: {exc}",
                allow_module_level=True,
            )
        _MECHS_LOADED = True
        _MECH_PATH = candidate
        return candidate

    pytest.skip(
        "No compiled NEURON mechanisms were found; run nrnivmodl before this test.",
        allow_module_level=True,
    )


h = _require_neuron()
specs, sim = _require_netpyne()

import json 
def remove_point_processes(cell_rule):
    """
    Remove 'pointps' from all sections in a NetPyNE cell rule.
    Returns a pure Python dict.
    """

    # Convert NetPyNE Dict → pure Python dict safely
    cell_dict = json.loads(json.dumps(cell_rule))

    for sec_name, sec_data in cell_dict.get("secs", {}).items():
        sec_data.pop("pointps", None)

    return cell_dict

def test_load_figure8control_hoc() -> None:
    """Smoke test: load Figure8control.hoc using NEURON inside a NetPyNE-ready environment."""

    repo_root = Path(__file__).resolve().parents[1]
    model_dir = repo_root / "original_models" / "theta_burst_protocol"
    hoc_entry = model_dir / "Figure8control.hoc"

    assert model_dir.is_dir(), "Cholinergic shift model directory is missing."
    assert hoc_entry.is_file(), "Figure8control.hoc is missing."

    _load_compiled_mechanisms(
        h,
        (
            repo_root / "arm64" / "libnrnmech.dylib",
            repo_root / "arm64" / ".libs" / "libnrnmech.dylib",
            repo_root / "x86_64" / "libnrnmech.dylib",
            repo_root / "x86_64" / ".libs" / "libnrnmech.dylib",
            repo_root / "x86_64" / ".libs" / "libnrnmech.so",
        ),
    )

    prev_dir = Path.cwd()
    os.chdir(model_dir)

    try:
        h.load_file(str(hoc_entry.name))
        # 3) now import the *existing* instantiated cell into NetPyNE cellParams
        netParams = specs.NetParams()

        netParams.importCellParams(
                label="PC2B",
                conds={"cellType": "PC2B"},
                fileName=str((repo_root / "tests" / "empty.hoc").resolve()),
                cellName=None,
                cellArgs=None,
                cellInstance=True,
                somaAtOrigin=True
            )

        print(netParams.cellParams["PC2B"]['secs']['soma_0'])

        # rename soma to conform to netpyne standard
        netParams.renameCellParamsSec(label='PC2B', oldSec='soma_0', newSec='soma')


        # Clean PC2B rule
        clean_cell = remove_point_processes(netParams.cellParams["PC2B"])

        # Create cells/ directory if it doesn't exist
        cells_dir = repo_root / "cells"
        cells_dir.mkdir(exist_ok=True)

        # Path to JSON file
        out_file = cells_dir / "PC2B.json"

        # Export only the cell rule
        with open(out_file, "w") as f:
            json.dump(clean_cell, f, indent=4)

        print(f"Cell exported to: {out_file}")

        # assume netParams already contains cellParams["PC2B"]
        cfg = specs.SimConfig()
        cfg.duration = 1
        cfg.dt = 0.025
        cfg.verbose = False

        # make a 1-cell population using that rule
        netParams.popParams["PC2B_pop"] = {"cellType": "PC2B", "cellModel": "HH", "numCells": 1}

        # build network (no need to run)
        sim.create(netParams=netParams, simConfig=cfg)

        # plot morphology
        sim.analysis.plotShape(saveFig=True, fileName="PC2B_morphology.png", dpi=200, showDiam=False)

    finally:
        os.chdir(prev_dir)

    # sections = list(h.allsec())
    # assert sections, "No sections were created after loading Figure8control.hoc."

test_load_figure8control_hoc()