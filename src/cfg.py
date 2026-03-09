from netpyne import specs
import numpy as np

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
cfg.Transient = 1000 # Transient time
cfg.duration = cfg.Transient +  cfg.Cycles*inter_burst_isi          # Duration of the simulation, in ms
cfg.dt = 1e-1               # Internal integration timestep to use
cfg.hParams = {'v_init': -80}  
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
cfg.CCh = False
cfg.saveFolder = 'output_CCh' if cfg.CCh else 'output_control' # Folder to save output
# PYR cells properties 
cfg.PYR = 1 # Number of Pyramidal neurons
cfg.PYRFile = 'cells/PC2B_CCh.json' if cfg.CCh else 'cells/PC2B.json'

# OLM cells properties 
cfg.OLM = 1 # Number of OLM cells
cfg.OLMFile = 'cells/OLMCell.json'

# VIP cells properties 
cfg.VIP = 1 # Number of OLM cells
cfg.VIPFile = 'cells/BilashVIP.json'

# ---------------- SC stimulation ----------------
start = cfg.Transient
intra_burst_isi = 10.0   # 100 Hz
n_spikes_per_burst = 5

cfg.sc_spike_times = [
    cfg.Transient + burst * inter_burst_isi + spike * intra_burst_isi
    for burst in range(cfg.Cycles)
    for spike in range(n_spikes_per_burst)
]


SCsyn_factor = 0.05#1.2
PPsyn_factor = 0.05

cfg.ampaWSC = SCsyn_factor * 0.00156 # AMPA weight
cfg.nmdaWSC = SCsyn_factor * 0.000882 # NMDA weight

cfg.ampaWPP = PPsyn_factor * 0.00156 # AMPA weight
cfg.nmdaWPP = PPsyn_factor * 0.000882 # NMDA weight

cfg.sc_secs = [
    'trunk_10', 'trunk_11', 'trunk_12', 'trunk_13', 'trunk_14', 'trunk_15',
    'apic_27', 'apic_28', 'apic_29', 'apic_30', 'apic_31', 'apic_32',
    'apic_28', 'apic_29', 'apic_30', 'apic_31',
    'apic_28', 'apic_29', 'apic_30', 'apic_31',
]

cfg.sc_locs = [
    0.5, 0.5, 0.5, 0.5, 0.5, 0.5,
    0.5, 0.5, 0.5, 0.5, 0.5, 0.5,
    0.2, 0.2, 0.2, 0.2,
    0.8, 0.8, 0.8, 0.8,
]
cfg.sc_syn_sites = list(zip(cfg.sc_secs, cfg.sc_locs))

cfg.SC = len(cfg.sc_secs)
cfg.PP = len(cfg.sc_secs)

###############################################################################
## Recording and analysis
###############################################################################
allpops = ['PC2B', 'OLM', 'VIP', 'SC', 'PP']
timeRange = [cfg.Transient, cfg.duration]
cfg.recordCells = [(pop,0) for pop in allpops if pop not in ['SC', 'PP']]
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
    'weight': [cfg.ampaWSC, cfg.nmdaWSC],
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
    'weight': cfg.ampaWSC,
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
    'weight': cfg.ampaWSC,
    'delay': 1.0,
    'start': cfg.Transient + 75.0,
    'interval': inter_burst_isi,
    'number': cfg.Cycles,
    'noise': 0.0
}
