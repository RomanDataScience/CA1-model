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

def define_CA1_zones(netParams, label):
    netParams.addCellParamsSecList(label=label, secListName='perisom', somaDist=[0, 50])
    netParams.addCellParamsSecList(label=label, secListName='basal', somaDist=[0, 200])
    netParams.addCellParamsSecList(label=label, secListName='SC_zone', somaDist=[200, 300])
    netParams.addCellParamsSecList(label=label, secListName='PP_zone', somaDist=[320, 1000])
    netParams.addCellParamsSecList(label=label, secListName='below_soma', somaDistY=[-600, 0]) 

# Load cellRules file
with open(cfg.PYRFile, 'r') as f:
    cellRulePYR = json.load(f)

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
netParams.popParams['SC'] = {'cellModel': 'VecStim', 'numCells': 22, 'spkTimes': cfg.sc_spike_times}
netParams.popParams['PP'] = {'cellModel': 'VecStim', 'numCells': 22, 'spkTimes': cfg.sc_spike_times}

# ---------------- synapses ----------------
netParams.synMechParams['AMPA'] = {
    'mod': 'Exp2Syn',
    # 'tau1': 0.5,
    # 'tau2': 1.0,
    # 'e': 0.0
}

netParams.synMechParams['NMDA'] = {
    'mod': 'nmdanet',
    # 'Alpha': 0.35,
    # 'Beta': 0.035,
    # 'mg': 1.0
}

# ---------------- target secList ----------------
label = 'PC2B'
define_CA1_zones(netParams, label = label)

# ---------------- SC -> CA1 ----------------
netParams.connParams['SC->PC2B_SC_zone'] = {
    'preConds': {'pop': 'SC', 'cellModel': 'VecStim'},
    'postConds': {'pop': 'PC2B', 'cellType': 'PC2B'},
    'sec': 'SC_zone',
    'loc': 0.5,
    'synMech': ['AMPA', 'NMDA'],
    'weight': [cfg.ampaW, cfg.nmdaW],
    'delay': 0,
    'synsPerConn': 1,
}
# ---------------- PP -> CA1 ----------------
netParams.connParams['PP->PC2B_SC_zone'] = {
    'preConds': {'pop': 'PP', 'cellModel': 'VecStim'},
    'postConds': {'pop': 'PC2B', 'cellType': 'PC2B'},
    'sec': 'PP_zone',
    'loc': 0.5,
    'synMech': ['AMPA', 'NMDA'],
    'weight': [cfg.ampaW, cfg.nmdaW],
    'delay': 0,
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
