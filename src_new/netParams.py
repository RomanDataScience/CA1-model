import json

from netpyne import specs

from cfg import cfg


cfg.update()

netParams = specs.NetParams()
netParams.version = 1
netParams.defaultThreshold = 0.

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

    ican_gbar_factor = float(getattr(cfg, 'IcanGbarFactor', 1.0))
    if ican_gbar_factor != 1.0:
        for sec_data in secs.values():
            if not isinstance(sec_data, dict):
                continue
            for ican_mech in _iter_ican_mechs(sec_data):
                if 'gbar' in ican_mech:
                    ican_mech['gbar'] = float(ican_mech['gbar']) * ican_gbar_factor
    
    return cell_rule

# -----------------------------------------------------------------------------
# Cell rule
# -----------------------------------------------------------------------------
with open(cfg.PYRFile, 'r') as f:
    cellRulePYR = json.load(f)
cellRulePYR = apply_pc2b_condition_mods(cellRulePYR, cfg)

with open(cfg.OLMFile, 'r') as f:
    cellRuleOLM = json.load(f)

with open(cfg.VIPFile, 'r') as f:
    cellRuleVIP = json.load(f)

netParams.addCellParams(label='PC2B', params=cellRulePYR)
netParams.addCellParams(label='OLM', params=cellRuleOLM)
netParams.addCellParams(label='BilashVIP', params=cellRuleVIP)

# -----------------------------------------------------------------------------
# Populations
# -----------------------------------------------------------------------------
netParams.popParams['PC2B'] = {'cellType': 'PC2B', 'numCells': cfg.PYR}
netParams.popParams['OLM'] = {'cellType': 'OLM', 'numCells': cfg.OLM}
netParams.popParams['VIP'] = {'cellType': 'BilashVIP', 'numCells': cfg.VIP}
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

# GABA_A for OLM -> PYR (Slow inhibition)
netParams.synMechParams['GABA_slow'] = {
    'mod': 'Exp2Syn', 
    'tau1': 2.0, 
    'tau2': 20.0, 
    'e': -75
}

# AMPA for PYR -> OLM (Facilitating)
# Note: Requires a mechanism supporting STP, e.g., 'Exp2SynSTP'
netParams.synMechParams['AMPA_facil'] = {
    'mod': 'Exp2Syn', # or custom STP mod
    'tau1': 0.5, 
    'tau2': 3.0, 
    'e': 0
}

# GABA_A for VIP -> OLM (Disinhibitory inhibition)
netParams.synMechParams['GABA_VIP'] = {
    'mod': 'Exp2Syn', 
    'tau1': 0.5, 
    'tau2': 8.0, 
    'e': -80
}

# -----------------------------------------------------------------------------
# Theta-burst site mapping: SC and PP pathway populations
# -----------------------------------------------------------------------------
for i, (sec, loc, nmda_mult) in enumerate(cfg.thetaScSites):
    netParams.connParams[f'SC->PC2B_{i}'] = {
        'preConds': {'pop': 'SC', 'cellModel': 'VecStim'},
        'postConds': {'pop': 'PC2B'},
        'sec': sec,
        'loc': loc,
        'synMech': ['AMPA', 'NMDA'],
        'weight': [cfg.thetaAMPAWeightPYR, cfg.thetaNMDAWeightPYR * nmda_mult],
        'delay': cfg.thetaDelay,
        'synsPerConn': 1,
    }

for i, (sec, loc, nmda_mult) in enumerate(cfg.thetaPpSites):
    netParams.connParams[f'PP->PC2B_{i}'] = {
        'preConds': {'pop': 'PP', 'cellModel': 'VecStim'},
        'postConds': {'pop': 'PC2B'},
        'sec': sec,
        'loc': loc,
        'synMech': ['AMPA', 'NMDA'],
        'weight': [cfg.thetaAMPAWeightPYR, cfg.thetaNMDAWeightPYR * nmda_mult],
        'delay': cfg.thetaDelay,
        'synsPerConn': 1,
    }

# SC and PP pathway inputs onto VIP from cfg-defined target section lists.
vip_sc_targets = list(getattr(cfg, 'vipScTargetSecs', []))
vip_pp_targets = list(getattr(cfg, 'vipPpTargetSecs', []))
vip_input_loc = float(getattr(cfg, 'vipInputLoc', 0.5))
vip_secs = set(cellRuleVIP.get('secs', {}).keys())

invalid_sc_targets = [sec for sec in vip_sc_targets if sec not in vip_secs]
invalid_pp_targets = [sec for sec in vip_pp_targets if sec not in vip_secs]
if invalid_sc_targets or invalid_pp_targets:
    raise ValueError(
        'Invalid VIP target sections in cfg. '
        f'SC invalid: {invalid_sc_targets}; PP invalid: {invalid_pp_targets}'
    )

for i, sec in enumerate(vip_sc_targets):
    netParams.connParams[f'SC->VIP_{i}'] = {
        'preConds': {'pop': 'SC', 'cellModel': 'VecStim'},
        'postConds': {'pop': 'VIP', 'cellType': 'BilashVIP'},
        'sec': sec,
        'loc': vip_input_loc,
        'synMech': ['AMPA', 'NMDA'],
        'weight': [cfg.thetaAMPAWeightVIP, cfg.thetaNMDAWeightVIP],
        'delay': cfg.thetaDelay,
        'synsPerConn': 1,
    }

for i, sec in enumerate(vip_pp_targets):
    netParams.connParams[f'PP->VIP_{i}'] = {
        'preConds': {'pop': 'PP', 'cellModel': 'VecStim'},
        'postConds': {'pop': 'VIP', 'cellType': 'BilashVIP'},
        'sec': sec,
        'loc': vip_input_loc,
        'synMech': ['AMPA', 'NMDA'],
        'weight': [cfg.thetaAMPAWeightVIP, cfg.thetaNMDAWeightVIP],
        'delay': cfg.thetaDelay,
        'synsPerConn': 1,
    }

# -----------------------------------------------------------------------------
# PYR to OLM excitation
# -----------------------------------------------------------------------------

# PYR -> OLM (Feedback Excitation)
netParams.connParams['PYR->OLM'] = {
    'preConds': {'pop': 'PC2B'},
    'postConds': {'pop': 'OLM'},
    'weight': cfg.PYROLMweight,
    'delay': cfg.delayPYROLM,
    'synMech': 'AMPA_facil',
    'probability': 1.,
    'synsPerConn': cfg.synsPerConnPYROLM
}

# OLM secList with sections up to 50 um from soma
netParams.addCellParamsSecList(
    label='OLM',
    secListName='perisom',
    somaDist=[0, 100]
)

# PYR targets OLM in Stratum Oriens (SO)
# OLM dendrites are horizontal and restricted to SO
netParams.subConnParams['PYR->OLM_proximal'] = {
    'preConds': {'pop': 'PC2B'},
    'postConds': {'pop': 'OLM'},
    'groupSynMechs': ['AMPA_facil'],
    'sec': 'perisom', # OLM dendrites are primarily in SO
    'density': 'uniform'
}

# -----------------------------------------------------------------------------
# OLM to PYR inhibition
# -----------------------------------------------------------------------------

# OLM -> PYR (Feedback Inhibition)
netParams.connParams['OLM->PYR'] = {
    'preConds': {'pop': 'OLM'},
    'postConds': {'pop': 'PC2B'},
    'weight': cfg.OLMPYRweight,
    'delay': cfg.delayOLMPYR,
    'synMech': 'GABA_slow',
    'probability': 1.,
    'synsPerConn': cfg.synsPerConnOLMPYR
}

# PC2B secList with only distal apical sections apic_35+
netParams.cellParams['PC2B']['secLists']['apical_distal_35plus'] = [
    secName
    for secName in netParams.cellParams['PC2B']['secs'].keys()
    if secName.startswith('apic_') and int(secName.split('_')[1]) >= 35
]

# OLM targets Distal Tuft (SLM) of PYR cells
# Usually > 250 um from soma or top 15-20% of apical tree
netParams.subConnParams['OLM->PYR_distal'] = {
    'preConds': {'pop': 'OLM'},
    'postConds': {'pop': 'PC2B'},
    'groupSynMechs': ['GABA_slow'],
    'sec': 'apical_distal_35plus', # or use ynorm if using 1D depth
    'density': 'uniform'
}

# -----------------------------------------------------------------------------
# VIP/IS-3 to OLM inhibition
# -----------------------------------------------------------------------------

# VIP -> OLM (Disinhibition)
netParams.connParams['VIP->OLM'] = {
    'preConds': {'pop': 'VIP'},
    'postConds': {'pop': 'OLM'},
    'weight': cfg.VIPOLMweight,
    'delay': cfg.delayVIPOLM,
    'synMech': 'GABA_VIP',
    'probability': 1.,
    'synsPerConn': cfg.synsPerConnVIPOLM
}

# VIP targets OLM dendrites in the Stratum Oriens (SO)
netParams.subConnParams['VIP->OLM_SO'] = {
    'preConds': {'pop': 'VIP'},
    'postConds': {'pop': 'OLM'},
    'groupSynMechs': ['GABA_VIP'],
    'sec': 'perisom', # OLM dendrites are horizontal in SO
    'density': 'uniform'
}
