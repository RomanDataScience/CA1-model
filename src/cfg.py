from netpyne import specs
import numpy as np
from pathlib import Path

# Simulation options
cfg = specs.SimConfig()       # object of class SimConfig to store simulation configuration

#------------------------------------------------------------------------------
#
# SIMULATION CONFIGURATION
#
#------------------------------------------------------------------------------
cfg._batchtk_label_pointer = None
cfg._batchtk_path_pointer = None

###############################################################################
## Simulation parameters
###############################################################################
inter_burst_isi = 200.0  # 5 Hz
cfg.Cycles = 5          # Number of cycles to simulate
cfg.Cycles2Plot = 5           # Number of cycles to plot
cfg.Transient = 500 # Transient time
cfg.duration = cfg.Transient +  cfg.Cycles*inter_burst_isi + 200.          # Duration of the simulation, in ms
cfg.dt = 1e-3               # Internal integration timestep to use
cfg.hParams = {'v_init': -70, 'celsius': 34}  
cfg.saveFolder = 'output'  # Folder to save output
cfg.simLabel = 'CA1_0'  # Simulation label, used in output file names
cfg.validateNetParams = False
cfg.verbose = False           # Show detailed messages
cfg.progressBar = 0       # Show progress bar
cfg.recordStep = cfg.dt        # Step size in ms to save data (e.g. V traces, LFP, etc)
cfg.seeds = {'conn': 4321, 'stim': 1234, 'loc': 4321, 'cell': 4321} # Random seeds for reproducibility.
cfg.saveDataInclude = ['simData', 'simConfig', 'net']  # Which data to save in the output file
cfg.printRunTime = 0.1 # Print run time every 0.1 seconds
cfg.recordTime = True  
cfg.createNEURONObj = True
cfg.createPyStruct = True
cfg.backupCfgFile = None #['cfg.py', 'backupcfg/']
cfg.gatherOnlySimData = False
cfg.saveCellSecs = False
cfg.saveCellConns = True
cfg.saveJson = True
cfg.savePickle = False
cfg.recordStims = True
cfg.includeParamsLabel = True

###############################################################################
## SimParams
############################################################################### 
# PYR cells properties 
cfg.PYR = 1 # Number of Pyramidal neurons
cfg.PYRFile = 'cells/PC2B_new.json'

# OLM cells properties 
cfg.OLM = 1 # Number of OLM cells
cfg.OLMFile = 'cells/OLMCell.json'

# VIP cells properties 
cfg.VIP = 1 # Number of OLM cells
cfg.VIPFile = 'cells/BilashVIP.json'

# ---------------- PC2B condition modifiers ----------------
# Set to True for control remap relative to loaded cell JSON:
#   soma.km.gbar = soma.km.gbar / controlKmSomaDivisor
#   all ican.gbar = controlIcanGbar
#   all ican.concrelease = controlIcanConcrelease
cfg.applyControlPC2B = False
cfg.controlKmSomaDivisor = 0.05
cfg.controlIcanGbar = 0.0
cfg.controlIcanConcrelease = 1.0

if not cfg.applyControlPC2B: cfg.saveFolder = cfg.saveFolder+'_CCh'  

Path(cfg.saveFolder).mkdir(parents=True, exist_ok=True)

# Optional global override for ican.concrelease (applied after control remap if not None).
cfg.overrideIcanConcrelease = cfg.controlIcanConcrelease if cfg.applyControlPC2B else 400 #400

def _build_theta_sites():
    sites = []
    for j in range(6):
        sites.append((f'trunk_{10 + j}', 0.5, 1.0, 'SC'))
    for i in range(6):
        sites.append((f'apic_{27 + i}', 0.5, 1.0, 'SC'))
    for i in range(4):
        sites.append((f'apic_{28 + i}', 0.2, 1.0, 'SC'))
    for i in range(4):
        sites.append((f'apic_{28 + i}', 0.8, 1.0, 'SC'))
    for i in range(20):
        sites.append((f'apic_{40 + i}', 0.8, 2.0, 'PP'))
    return sites


# ---------------- Theta-burst VecStim protocol (from exampleTheta/run_theta_netpyne.py) ----------------
intra_burst_isi = 10.0   # 100 Hz
n_spikes_per_burst = 5

cfg.thetaCycles = cfg.Cycles
cfg.thetaBurstStart = cfg.Transient
cfg.thetaInterBurstISI = inter_burst_isi
cfg.thetaIntraBurstISI = intra_burst_isi
cfg.thetaSpikesPerBurst = n_spikes_per_burst
cfg.thetaSpikeTimes = [
    cfg.thetaBurstStart + burst * cfg.thetaInterBurstISI + spike * cfg.thetaIntraBurstISI
    for burst in range(cfg.thetaCycles)
    for spike in range(cfg.thetaSpikesPerBurst)
]
cfg.thetaSites = _build_theta_sites()
cfg.thetaScSites = [(sec, loc, nmda_mult) for sec, loc, nmda_mult, group in cfg.thetaSites if group == 'SC']
cfg.thetaPpSites = [(sec, loc, nmda_mult) for sec, loc, nmda_mult, group in cfg.thetaSites if group == 'PP']
cfg.thetaInputPops = ['SC', 'PP']

cfg.thetaAMPAWeight = 1.2 * 0.00156 * 0.22 
cfg.thetaNMDAWeight = 1.2 * 0.000882 * 0.22 

# One VecStim source per pathway; each source projects to all pathway sites.
cfg.SC = 1
cfg.PP = 1

###############################################################################
## Recording and analysis
###############################################################################
input_pops = cfg.thetaInputPops
allpops = ['PC2B', 'OLM', 'VIP'] + input_pops
timeRange = [cfg.Transient-100., cfg.duration]
cfg.recordCells = [(pop,0) for pop in ['PC2B', 'OLM', 'VIP']]
cfg.recordTraces = {'V_soma':{'sec':'soma','loc':0.5,'var':'v'}}  # Dict with traces to record
cfg.analysis['plotRaster'] = {'include': allpops,'saveFig': True, 'timeRange': timeRange} # Plot a raster
cfg.analysis['plotSpikeHist'] = {'include': allpops, 'saveFig': True, 'timeRange': timeRange, 'binSize': 1, 'measure': 'rate'}                  # Plot a Spike Histogram
cfg.analysis['plotTraces'] = {'include': cfg.recordCells, 'saveFig': True, 'timeRange': timeRange}  # Plot recorded traces for this list of cells

#------------------------------------------------------------------------------
# Current inputs 
#------------------------------------------------------------------------------
cfg.addIClamp = False

cfg.IClamp1 = {'pop': 'PC2B', 'sec': 'soma', 'loc': 0.5, 'start': 0, 'dur': 1000, 'amp': 0.50}
cfg.IClamp2 = {'pop': 'OLM', 'sec': 'soma', 'loc': 0.5, 'start': 0, 'dur': 1000, 'amp': 0.50}
cfg.IClamp3 = {'pop': 'VIP', 'sec': 'soma', 'loc': 0.5, 'start': 0, 'dur': 1000, 'amp': 0.50}

#------------------------------------------------------------------------------
# NetStim inputs
#------------------------------------------------------------------------------
cfg.addNetStim = False

cfg.NetStim1 = {
    'pop': 'PC2B',
    'sec': 'soma',
    'loc': 0.5,
    'synMech': ['AMPA', 'NMDA'],
    'weight': [cfg.thetaAMPAWeight, cfg.thetaNMDAWeight],
    'delay': 1.0,
    'start': cfg.Transient + 25.0,
    'interval': inter_burst_isi,
    'number': cfg.Cycles,
    'noise': 0.0
}

cfg.NetStim2 = {
    'pop': 'OLM',
    'sec': 'soma',
    'loc': 0.5,
    'synMech': 'AMPA',
    'weight': cfg.thetaAMPAWeight,
    'delay': 1.0,
    'start': cfg.Transient + 50.0,
    'interval': inter_burst_isi,
    'number': cfg.Cycles,
    'noise': 0.0
}

cfg.NetStim3 = {
    'pop': 'VIP',
    'sec': 'soma',
    'loc': 0.5,
    'synMech': 'AMPA',
    'weight': cfg.thetaAMPAWeight,
    'delay': 1.0,
    'start': cfg.Transient + 75.0,
    'interval': inter_burst_isi,
    'number': cfg.Cycles,
    'noise': 0.0
}
