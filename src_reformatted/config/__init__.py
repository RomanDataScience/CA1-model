from .cells import apply_cells_config
from .derived import apply_derived_config
from .recording import apply_recording_config
from .sim import apply_sim_config
from .stimuli import apply_stimuli_config
from .synapses import apply_synapse_config


_BASE_LOADERS = (
    apply_sim_config,
    apply_cells_config,
    apply_stimuli_config,
    apply_synapse_config,
    apply_recording_config,
)


def load_base_config(cfg):
    for loader in _BASE_LOADERS:
        loader(cfg)
    return cfg


def load_derived_config(cfg):
    apply_derived_config(cfg)
    return cfg
