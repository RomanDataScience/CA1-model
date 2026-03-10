import json

from netpyne import specs

from cfg import cfg


cfg.update()

netParams = specs.NetParams()
netParams.version = 1

def apply_pc2b_condition_mods(cell_rule, cfg):
    secs = cell_rule.get('secs', {})
    if not isinstance(secs, dict):
        return cell_rule

    def _iter_ican_mechs(sec_data):
        mechs = sec_data.get('mechs', {})
        for mech_name in ('ican', 'ican_PYR'):
            mech = mechs.get(mech_name, {})
            if isinstance(mech, dict):
                yield mech

    if getattr(cfg, 'applyControlPC2B', False):
        soma = secs.get('soma', secs.get('soma_0', {}))
        if isinstance(soma, dict):
            soma_mechs = soma.get('mechs', {})
            divisor = float(getattr(cfg, 'controlKmSomaDivisor', 0.05))
            if divisor == 0.0:
                raise ValueError('cfg.controlKmSomaDivisor cannot be 0.')
            for km_name in ('km', 'km_PYR'):
                km = soma_mechs.get(km_name, {})
                if isinstance(km, dict) and 'gbar' in km:
                    km['gbar'] = float(km['gbar']) / divisor

        target_ican_gbar = float(getattr(cfg, 'controlIcanGbar', 0.0))
        target_ican_concrelease = float(getattr(cfg, 'controlIcanConcrelease', 1.0))
        for sec_data in secs.values():
            if not isinstance(sec_data, dict):
                continue
            for ican_mech in _iter_ican_mechs(sec_data):
                ican_mech['gbar'] = target_ican_gbar
                ican_mech['concrelease'] = target_ican_concrelease

    override_concrelease = getattr(cfg, 'overrideIcanConcrelease', None)
    if override_concrelease is not None:
        target = float(override_concrelease)
        for sec_data in secs.values():
            if not isinstance(sec_data, dict):
                continue
            for ican_mech in _iter_ican_mechs(sec_data):
                ican_mech['concrelease'] = target

    return cell_rule


# -----------------------------------------------------------------------------
# Cell rule
# -----------------------------------------------------------------------------
with open(cfg.PYRFile, 'r') as f:
    cellRulePYR = json.load(f)
cellRulePYR = apply_pc2b_condition_mods(cellRulePYR, cfg)

netParams.addCellParams(label='PC2B', params=cellRulePYR)

# -----------------------------------------------------------------------------
# Populations
# -----------------------------------------------------------------------------
netParams.popParams['PC2B'] = {'cellType': 'PC2B', 'numCells': cfg.PYR}
netParams.popParams['SC'] = {'cellModel': 'VecStim', 'numCells': cfg.SC, 'spkTimes': cfg.thetaSpikeTimes}
netParams.popParams['PP'] = {'cellModel': 'VecStim', 'numCells': cfg.PP, 'spkTimes': cfg.thetaSpikeTimes}

# -----------------------------------------------------------------------------
# Synaptic mechanisms (multisyn.hoc)
# -----------------------------------------------------------------------------
netParams.synMechParams['AMPA'] = {
    'mod': 'Exp2Syn',
    'tau1': 0.5,
    'tau2': 1.0,
    'e': 0.0,
}

netParams.synMechParams['NMDA'] = {
    'mod': 'nmdanet',
    'Alpha': 0.35,
    'Beta': 0.035,
}

# -----------------------------------------------------------------------------
# Theta-burst site mapping: SC and PP pathway populations
# -----------------------------------------------------------------------------
for i, (sec, loc, nmda_mult) in enumerate(cfg.thetaScSites):
    netParams.connParams[f'SC->PC2B_{i}'] = {
        'preConds': {'pop': 'SC', 'cellModel': 'VecStim'},
        'postConds': {'pop': 'PC2B', 'cellType': 'PC2B'},
        'sec': sec,
        'loc': loc,
        'synMech': ['AMPA', 'NMDA'],
        'weight': [cfg.thetaAMPAWeight, cfg.thetaNMDAWeight * nmda_mult],
        'delay': cfg.thetaDelay,
        'synsPerConn': 1,
    }

for i, (sec, loc, nmda_mult) in enumerate(cfg.thetaPpSites):
    netParams.connParams[f'PP->PC2B_{i}'] = {
        'preConds': {'pop': 'PP', 'cellModel': 'VecStim'},
        'postConds': {'pop': 'PC2B', 'cellType': 'PC2B'},
        'sec': sec,
        'loc': loc,
        'synMech': ['AMPA', 'NMDA'],
        'weight': [cfg.thetaAMPAWeight, cfg.thetaNMDAWeight * nmda_mult],
        'delay': cfg.thetaDelay,
        'synsPerConn': 1,
    }
