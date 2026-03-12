from pathlib import Path

from netpyne import specs

from config import load_base_config, load_derived_config


cfg = specs.SimConfig()


def refresh_cfg(target_cfg=None, ensure_output_dir=True):
    target_cfg = cfg if target_cfg is None else target_cfg
    load_derived_config(target_cfg)
    if ensure_output_dir:
        Path(target_cfg.saveFolder).mkdir(parents=True, exist_ok=True)
    return target_cfg


load_base_config(cfg)
refresh_cfg(cfg, ensure_output_dir=False)
cfg.update()
