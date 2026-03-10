from netpyne import specs
import pickle, json
from pathlib import Path
from cfg import cfg

cfg.update()
if cfg._batchtk_path_pointer is not None:
    cfg.saveFolder = cfg._batchtk_path_pointer
    cfg.simLabel = cfg._batchtk_label_pointer

cwd = str(Path.cwd())

netParams = specs.NetParams()   # object of class NetParams to store the network parameters

netParams.version = 1

def apply_pc2b_condition_mods(cell_rule, cfg):
    secs = cell_rule.get('secs', {})

    if getattr(cfg, 'applyControlPC2B', False):
        soma = secs.get('soma', secs.get('soma_0', {}))
        if isinstance(soma, dict):
            km = soma.get('mechs', {}).get('km', {})
            if isinstance(km, dict) and 'gbar' in km:
                divisor = float(getattr(cfg, 'controlKmSomaDivisor', 0.05))
                if divisor == 0:
                    raise ValueError('cfg.controlKmSomaDivisor cannot be 0.')
                km['gbar'] = float(km['gbar']) / divisor

        target_ican_gbar = float(getattr(cfg, 'controlIcanGbar', 0.0))
        target_ican_concrelease = float(getattr(cfg, 'controlIcanConcrelease', 1.0))
        for sec_data in secs.values():
            if not isinstance(sec_data, dict):
                continue
            ican = sec_data.get('mechs', {}).get('ican', {})
            if isinstance(ican, dict):
                # ican['gbar'] = target_ican_gbar
                ican['concrelease'] = target_ican_concrelease

    override_concrelease = getattr(cfg, 'overrideIcanConcrelease', None)
    if override_concrelease is not None:
        target_concrelease = float(override_concrelease)
        for sec_data in secs.values():
            if not isinstance(sec_data, dict):
                continue
            ican = sec_data.get('mechs', {}).get('ican', {})
            if isinstance(ican, dict):
                ican['concrelease'] = target_concrelease

    return cell_rule


def define_CA1_zones(netParams, label):
    netParams.addCellParamsSecList(label=label, secListName='perisom', somaDist=[0, 50])
    netParams.addCellParamsSecList(label=label, secListName='basal', somaDist=[0, 200])
    netParams.addCellParamsSecList(label=label, secListName='below_soma', somaDistY=[-600, 0]) 

# Load cellRules file
with open(cfg.PYRFile, 'r') as f:
    cellRulePYR = json.load(f)
cellRulePYR = apply_pc2b_condition_mods(cellRulePYR, cfg)

with open(cfg.OLMFile, 'r') as f:
    cellRuleOLM = json.load(f)

with open(cfg.VIPFile, 'r') as f:
    cellRuleVIP = json.load(f)

# Add to netParams
netParams.addCellParams(label='PC2B', params=cellRulePYR)
netParams.addCellParams(label='OLM', params=cellRuleOLM)
netParams.addCellParams(label='VIP', params=cellRuleVIP)

###############################################################################
# NETWORK PARAMETERS
###############################################################################
# Population parameters
netParams.popParams['PC2B'] = {'cellType': 'PC2B', 'numCells': cfg.PYR} # add dict with params for this pop
netParams.popParams['OLM'] = {'cellType': 'OLM', 'numCells': cfg.OLM} # add dict with params for this pop
netParams.popParams['VIP'] = {'cellType': 'BilashVIP', 'numCells': cfg.VIP} # add dict with params for this pop
netParams.popParams['SC'] = {'cellModel': 'VecStim', 'numCells': cfg.SC, 'spkTimes': cfg.thetaSpikeTimes}
netParams.popParams['PP'] = {'cellModel': 'VecStim', 'numCells': cfg.PP, 'spkTimes': cfg.thetaSpikeTimes}

# ---------------- synapses ----------------
netParams.synMechParams['AMPA'] = {
    'mod': 'Exp2Syn',
    'tau1': 0.5,
    'tau2': 1.0,
    # 'e': 0.0
}

netParams.synMechParams['NMDA'] = {
    'mod': 'nmdanet',
    'Alpha': 0.35,
    'Beta': 0.035,
}

# ---------------- target secList ----------------
label = 'PC2B'
define_CA1_zones(netParams, label = label)

# Theta-burst site-specific mapping using two VecStim populations (SC and PP),
# with one source cell per pathway and shared spike times.
theta_inputs = (
    ('SC', cfg.thetaScSites),
    ('PP', cfg.thetaPpSites),
)
for pop_name, site_list in theta_inputs:
    for i, (sec, loc, nmda_mult) in enumerate(site_list):
        netParams.connParams[f'{pop_name}->PC2B_theta_site_{i}'] = {
            'preConds': {'pop': pop_name, 'cellModel': 'VecStim'},
            'postConds': {'pop': 'PC2B', 'cellType': 'PC2B'},
            'sec': sec,
            'loc': loc,
            'synMech': ['AMPA', 'NMDA'],
            'weight': [cfg.thetaAMPAWeight, cfg.thetaNMDAWeight * nmda_mult],
            'delay': 1.,
            'synsPerConn': 1,
        }

#------------------------------------------------------------------------------
# Current inputs (IClamp)
#------------------------------------------------------------------------------
if cfg.addIClamp:
    for key in [k for k in dir(cfg) if k.startswith('IClamp')]:
        params = getattr(cfg, key, None)
        [pop,sec,loc,start,dur,amp] = [params[s] for s in ['pop','sec','loc','start','dur','amp']]

        # add stim source
        netParams.stimSourceParams[key] = {'type': 'IClamp', 'delay': start, 'dur': dur, 'amp': amp}
        
        # connect stim source to target
        netParams.stimTargetParams[key+'_'+pop] =  {
            'source': key, 
            'conds': {'pop': pop},
            'sec': sec, 
            'loc': loc}

#------------------------------------------------------------------------------
# NetStim inputs
#------------------------------------------------------------------------------
if getattr(cfg, 'addNetStim', False):
    for key in [k for k in dir(cfg) if k.startswith('NetStim')]:
        params = getattr(cfg, key, None)
        [pop, sec, loc, synMech, weight, delay, start, interval, number, noise] = [
            params[s] for s in ['pop', 'sec', 'loc', 'synMech', 'weight', 'delay', 'start', 'interval', 'number', 'noise']
        ]

        # add stim source
        netParams.stimSourceParams[key] = {
            'type': 'NetStim',
            'start': start,
            'interval': interval,
            'number': number,
            'noise': noise
        }

        # connect stim source to target
        netParams.stimTargetParams[key+'_'+pop] = {
            'source': key,
            'conds': {'pop': pop},
            'sec': sec,
            'loc': loc,
            'synMech': synMech,
            'weight': weight,
            'delay': delay
        }
