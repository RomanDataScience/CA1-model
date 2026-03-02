from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def _require_module(name: str):
    spec = importlib.util.find_spec(name)
    if spec is None:
        pytest.skip(f"Module '{name}' not available in test environment.", allow_module_level=True)


_require_module("neuron")
_require_module("netpyne")

from netpyne import specs, sim  # type: ignore


def test_import_bilash_pyramidal_cell(tmp_path: Path) -> None:
    """Smoke test: import Bilash 2022 PyramidalCell into NetPyNE and build a one-cell network."""

    cell_file = Path(__file__).resolve().parents[1] / "original_models/bilash_2022/_codes/cell_models.py"
    assert cell_file.is_file(), "Bilash cell model file is missing."

    net_params = specs.NetParams()
    net_params.importCellParams(
        label="BilashPYR",
        conds={"cellType": "BilashPYR", "cellModel": "BilashPYR"},
        fileName=str(cell_file),
        cellName="PyramidalCell",
        cellArgs={'gid': -1}
    )
    assert "BilashPYR" in net_params.cellParams, "Cell import did not populate netParams.cellParams."
    net_params.popParams["pyrPop"] = {"cellType": "BilashPYR", "cellModel": "BilashPYR", "numCells": 1}

    sim_config = specs.SimConfig()
    sim_config.duration = 5  # ms
    sim_config.dt = 0.025
    sim_config.recordTraces = {"v_soma": {"sec": "soma", "loc": 0.5, "var": "v"}}
    sim_config.saveFolder = str(tmp_path)

    sim.createSimulateAnalyze(netParams=net_params, simConfig=sim_config)

    assert "v_soma" in sim.simData, "NetPyNE did not record the soma voltage trace."


def test_import_bilash_vip_cell(tmp_path: Path) -> None:
    """Smoke test: import Bilash 2022 VIPCRCell into NetPyNE and build a one-cell network."""

    cell_file = Path(__file__).resolve().parents[1] / "original_models/bilash_2022/_codes/cell_models.py"
    assert cell_file.is_file(), "Bilash cell model file is missing."

    net_params = specs.NetParams()
    net_params.importCellParams(
        label="BilashVIP",
        conds={"cellType": "BilashVIP", "cellModel": "BilashVIP"},
        fileName=str(cell_file),
        cellName="VIPCRCell",
        cellArgs={'gid': -1}
    )
    assert "BilashVIP" in net_params.cellParams, "VIP cell import did not populate netParams.cellParams."
    net_params.popParams["vipPop"] = {"cellType": "BilashVIP", "cellModel": "BilashVIP", "numCells": 1}

    sim_config = specs.SimConfig()
    sim_config.duration = 5  # ms
    sim_config.dt = 0.025
    sim_config.recordTraces = {"v_soma": {"sec": "soma", "loc": 0.5, "var": "v"}}
    sim_config.saveFolder = str(tmp_path)

    sim.createSimulateAnalyze(netParams=net_params, simConfig=sim_config)

    assert "v_soma" in sim.simData, "NetPyNE did not record the soma voltage trace for VIP cell."
