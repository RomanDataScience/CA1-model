from pathlib import Path


_CELLS_DIR = Path(__file__).resolve().parents[2] / "cells"


def apply_cells_config(cfg):
    # src_network diverges from src/ here: expand each resident CA1 population
    # from one representative cell to a 10-cell ensemble.
    cfg.cellsPerType = 10
    cfg.PYR = cfg.cellsPerType
    cfg.PYRFile = str(_CELLS_DIR / "PC2B.json")
    cfg.OLM = cfg.cellsPerType
    cfg.OLMFile = str(_CELLS_DIR / "OLMCell.json")
    cfg.VIP = cfg.cellsPerType
    cfg.VIPFile = str(_CELLS_DIR / "BilashVIP.json")
    cfg.vipInputResistanceScale = 1.0

    # src_network diverges from src/ here: assign each population a CA1 depth
    # band so the replicated network keeps the laminar organization explicit.
    # ynorm=0.0 corresponds to deep stratum oriens and ynorm=1.0 to distal SLM.
    cfg.netSizeX = 100.0
    cfg.netSizeY = 1000.0
    cfg.netSizeZ = 100.0
    cfg.popYNormRanges = {
        "OLM": [0.05, 0.18],   # stratum oriens
        "MS": [2.0, 2.2],      # septal-drive coming from different brain area
        "PC2B": [0.46, 0.54],  # stratum pyramidale
        "VIP": [0.58, 0.72],   # SP/SR border and proximal stratum radiatum
        "SC": [2.0, 2.2],      # Schaffer-collateral coming from different brain area
        "PP": [2.0, 2.2],      # perforant-path coming from different brain area
    }

    cfg.applyControlPC2B = False
    cfg.controlKmSomaDivisor = 0.05
    cfg.controlIcanGbar = 0.0
    cfg.controlIcanConcrelease = 1.0
    cfg.IcanGbarFactor = 1.25
    cfg.overrideIcanConcrelease = None
