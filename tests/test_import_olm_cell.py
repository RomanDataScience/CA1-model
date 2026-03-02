from __future__ import annotations

import os
from pathlib import Path

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


h = _require_neuron()


def test_load_olm_hoc_model() -> None:
    """Smoke test: load the OLM model HOC stack and ensure sections are created."""

    model_dir = Path(__file__).resolve().parents[1] / "original_models/OLMng-master"
    hoc_entry = model_dir / "init_model.hoc"
    assert hoc_entry.is_file(), "OLM init_model.hoc is missing."

    prev_cwd = Path.cwd()
    os.chdir(model_dir)
    try:
        h.load_file(str(hoc_entry.name))
    finally:
        os.chdir(prev_cwd)

    sections = list(h.allsec())
    assert sections, "No sections were created after loading OLM model."


def test_import_olm_into_netpyne(tmp_path: Path) -> None:
    """Import the OLM HOC model into NetPyNE and run a brief simulation."""

    specs, sim = _require_netpyne()

    model_dir = Path(__file__).resolve().parents[1] / "original_models/OLMng-master"
    hoc_entry = model_dir / "init_model.hoc"
    assert hoc_entry.is_file(), "OLM init_model.hoc is missing."

    net_params = specs.NetParams()
    net_params.importCellParams(
        label="OLMCell",
        conds={"cellType": "OLM", "cellModel": "OLM"},
        fileName=str(hoc_entry),
        cellName="celldef",
        somaAtOrigin=True
    )

    assert "OLMCell" in net_params.cellParams, "OLM cell import did not populate netParams.cellParams."
    net_params.popParams["olmPop"] = {"cellType": "OLM", "cellModel": "OLM", "numCells": 1}

    sim_config = specs.SimConfig()
    sim_config.duration = 5
    sim_config.dt = 0.025
    sim_config.recordTraces = {"v_soma0": {"sec": "soma[0]", "loc": 0.5, "var": "v"}}
    sim_config.saveFolder = str(tmp_path)

    prev_cwd = Path.cwd()
    os.chdir(model_dir)
    try:
        sim.createSimulateAnalyze(netParams=net_params, simConfig=sim_config)
    finally:
        os.chdir(prev_cwd)

    assert "v_soma0" in sim.simData, "NetPyNE did not record the soma voltage trace for OLM cell."
