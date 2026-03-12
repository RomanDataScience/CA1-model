from pathlib import Path


_CELLS_DIR = Path(__file__).resolve().parents[2] / "cells"


def apply_cells_config(cfg):
    cfg.PYR = 1
    cfg.PYRFile = str(_CELLS_DIR / "PC2B_new.json")
    cfg.OLM = 1
    cfg.OLMFile = str(_CELLS_DIR / "OLMCell.json")
    cfg.VIP = 1
    cfg.VIPFile = str(_CELLS_DIR / "BilashVIP.json")

    cfg.applyControlPC2B = False
    cfg.controlKmSomaDivisor = 0.05
    cfg.controlIcanGbar = 0.0
    cfg.controlIcanConcrelease = 1.0
    cfg.IcanGbarFactor = 1.25
    cfg.overrideIcanConcrelease = None
