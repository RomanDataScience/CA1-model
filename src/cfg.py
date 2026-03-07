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
cfg.Transient = 3000 # Transient time
cfg.duration = cfg.Transient +  cfg.Cycles*inter_burst_isi          # Duration of the simulation, in ms
cfg.dt = 1e-1               # Internal integration timestep to use
cfg.hParams = {'v_init': -80}  
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
cfg.PYRFile = 'cells/PC2B.json'

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

cfg.ampaW = 1.2 * 0.00156 # AMPA weight
cfg.nmdaW = 1.2 * 0.000882 # NMDA weight

###############################################################################
## Recording and analysis
###############################################################################
allpops = ['PYR', 'OLM', 'VIP']
timeRange = [0, cfg.duration]
cfg.recordCells = [(pop,0) for pop in allpops]
cfg.recordTraces = {'V_soma':{'sec':'soma','loc':0.5,'var':'v'}}  # Dict with traces to record
cfg.analysis['plotRaster'] = {'include': allpops,'saveFig': True, 'timeRange': timeRange} # Plot a raster
cfg.analysis['plotSpikeHist'] = {'include': ['FS', 'SC'], 'saveFig': True, 'timeRange': timeRange, 'binSize': 1, 'measure': 'rate'}                  # Plot a Spike Histogram
cfg.analysis['plotTraces'] = {'include': cfg.recordCells, 'saveFig': True, 'timeRange': timeRange}  # Plot recorded traces for this list of cells