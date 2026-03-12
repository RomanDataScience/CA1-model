from pathlib import Path

from netpyne import specs


cfg = specs.SimConfig()

# -----------------------------------------------------------------------------
# Simulation
# -----------------------------------------------------------------------------
cfg.Transient = 500
cfg.dt = 0.1
cfg.cvode_active = True
cfg.cvode_atol = 1e-3
cfg.progressBar = 0
cfg.hParams = {'v_init': -70.0, 'celsius': 34.0}

cfg.verbose = False
cfg.validateNetParams = False
cfg.recordStep = cfg.dt
cfg.printRunTime = 0.1
cfg.seeds = {'conn': 4321, 'stim': 1234, 'loc': 4321, 'cell': 4321}

cfg.saveJson = True
cfg.savePickle = False
cfg.saveDataInclude = ['simData', 'simConfig', 'netParams']

cfg.recordTime = True

# -----------------------------------------------------------------------------
# Cell
# -----------------------------------------------------------------------------
cfg.PYR = 1
cfg.PYRFile = 'cells/PC2B_new.json'
cfg.OLM = 1
cfg.OLMFile = 'cells/OLMCell.json'
cfg.VIP = 1
cfg.VIPFile = 'cells/BilashVIP.json'

# -----------------------------------------------------------------------------
# PC2B condition modifiers
# -----------------------------------------------------------------------------
# Control condition transform (applied to imported PC2B cell rule in netParams):
# - soma.km.gbar = soma.km.gbar / controlKmSomaDivisor
# - all ican.gbar = controlIcanGbar
# - all ican.concrelease = controlIcanConcrelease
cfg.applyControlPC2B = False
cfg.controlKmSomaDivisor = 0.05
cfg.controlIcanGbar = 0.0
cfg.controlIcanConcrelease = 1.0
cfg.IcanGbarFactor = 1.25

# Optional global override for all ican.concrelease (applied after control).
cfg.overrideIcanConcrelease = None

# -----------------------------------------------------------------------------
# Theta-burst protocol from original_models/theta_burst_protocol/multisyn.hoc
# -----------------------------------------------------------------------------
def _build_theta_sites():
    sites = []
    # SC-like group: trunk + proximal apical targets
    for j in range(6):
        sites.append((f'trunk_{10 + j}', 0.5, 1.0, 'SC'))
    for i in range(6):
        sites.append((f'apic_{27 + i}', 0.5, 1.0, 'SC'))
    for i in range(4):
        sites.append((f'apic_{28 + i}', 0.2, 1.0, 'SC'))
    for i in range(4):
        sites.append((f'apic_{28 + i}', 0.8, 1.0, 'SC'))
    # PP-like group: distal apicals with NMDA x2
    for i in range(20):
        sites.append((f'apic_{40 + i}', 0.8, 2.0, 'PP'))
    return sites

cfg.thetaCycles = 5
cfg.thetaInterBurstISI = 200.0
cfg.thetaIntraBurstISI = 10.0
cfg.thetaSpikesPerBurst = 5
cfg.thetaDelay = 0.1 
cfg.thetaBurstStart = cfg.Transient
cfg.duration = cfg.Transient + cfg.thetaCycles*cfg.thetaInterBurstISI + 200.

cfg.thetaSpikeTimes = [
    cfg.thetaBurstStart + burst * cfg.thetaInterBurstISI + spike * cfg.thetaIntraBurstISI
    for burst in range(cfg.thetaCycles)
    for spike in range(cfg.thetaSpikesPerBurst)
]

cfg.thetaSites = _build_theta_sites()
cfg.thetaScSites = [(sec, loc, nmda_mult) for sec, loc, nmda_mult, group in cfg.thetaSites if group == 'SC']
cfg.thetaPpSites = [(sec, loc, nmda_mult) for sec, loc, nmda_mult, group in cfg.thetaSites if group == 'PP']

# multisyn.hoc amplitudes
factorSynPYR = 0.208 #(for 500 ms transient)
cfg.thetaAMPAWeightPYR = 1.2 * 0.00156 * factorSynPYR
cfg.thetaNMDAWeightPYR = 1.2 * 0.000882 * factorSynPYR

factorSynVIP = 0.1 #0.9 
cfg.thetaAMPAWeightVIP = 1.2 * 0.00156 * factorSynVIP
cfg.thetaNMDAWeightVIP = 1.2 * 0.000882 * factorSynVIP

# SC/PP pathway targets onto BilashVIP (editable from cfg without touching netParams)
cfg.vipScTargetSecs = [
    'radTprox', 'radTmed', 'radTdist1', 'radTdist2', 'radTdist3',
    'rad_thick1', 'rad_medium1', 'rad_thin1a', 'rad_thin1b', 'rad_thick2'
]
cfg.vipPpTargetSecs = [
    'lm_thick1', 'lm_medium1', 'lm_thin1a', 'lm_thin1b',
    'lm_thick2', 'lm_medium2', 'lm_thin2a', 'lm_thin2b',
    'lmM1', 'lmt1'
]
cfg.vipInputLoc = 0.5

# One VecStim source population per pathway
cfg.SC = 1
cfg.PP = 1

# -----------------------------------------------------------------------------
# Example MS cholinergic source:
# 8 Hz theta, with 2 spikes per theta cycle separated by 20 ms
# -----------------------------------------------------------------------------

cfg.nMS = 1
cfg.nMSweight = 1e-4
cfg.nMSinputs = 5
# cfg.MSIntraBurstISI = 10.
# cfg.MSSpikesPerBurst = 5

# cfg.MS_train = [
#     cfg.thetaBurstStart + burst * cfg.thetaInterBurstISI + spike * cfg.MSIntraBurstISI
#     for burst in range(cfg.thetaCycles)
#     for spike in range(cfg.MSSpikesPerBurst)
# ]

cfg.MSRateHz = 10.0
cfg.MSISI = 1000.0 / cfg.MSRateHz  # ms between spikes

cfg.MS_train = [
    spike * cfg.MSISI
    for spike in range(int(cfg.duration / cfg.MSISI) + 1)
]

# -----------------------------------------------------------------------------
# OLM <-> PYR connectivity
# -----------------------------------------------------------------------------
# Best combos
# (5e-3, 1e-2, 5e-3); (5e-3, 0, 0)
cfg.PYROLMweight = 0*5e-3
cfg.OLMPYRweight = 0*1e-2
cfg.VIPOLMweight = 0*5e-3

# Best combos
# (2, 8, 3)
cfg.synsPerConnPYROLM = 2
cfg.synsPerConnOLMPYR = 8
cfg.synsPerConnVIPOLM = 3

cfg.delayPYROLM = 1.5
cfg.delayOLMPYR = 1.1
cfg.delayVIPOLM = 1.

cfg.saveFolder = 'output_4'
cfg.simLabel = 'CA1_1'
Path(cfg.saveFolder).mkdir(parents=True, exist_ok=True)

cfg.simLabel += f'_Control{cfg.applyControlPC2B}_VIPx{factorSynVIP}_GLU{cfg.PYROLMweight}_GABAOLM{cfg.OLMPYRweight}_GABAVIP{cfg.VIPOLMweight}_Achinput{cfg.nMSweight}' 

# -----------------------------------------------------------------------------
# Recording
# -----------------------------------------------------------------------------
allpops = ['PC2B', 'OLM', 'VIP', 'SC', 'PP', 'MS']
timeRange = [cfg.Transient - 200., cfg.duration]
cfg.recordCells = [(pop,0) for pop in allpops if pop not in ['SC', 'PP']]
allpopsHistogram = [pop for pop in allpops if pop not in ['SC', 'PP']]
cfg.recordTraces = {
    'V_soma': {'sec': 'soma', 'loc': 0.5, 'var': 'v'},
    'I_AMPA_facil': {'synMech': 'AMPA_facil', 'var': 'i', 'conds': {'pop': 'OLM'}},
    'I_GABA_slow': {'synMech': 'GABA_slow', 'var': 'i', 'conds': {'pop': 'PC2B'}},
    'I_nAch': {'synMech': 'nACh_IS3', 'var': 'i', 'conds': {'pop': 'VIP'}},
}  # Dict with traces to record
cfg.analysis['plotRaster'] = {'include': allpops,'saveFig': True, 'timeRange': timeRange, 'marker': '|'} # Plot a raster
cfg.analysis['plotSpikeHist'] = {'include': allpops, 'saveFig': True, 'timeRange': timeRange, 'binSize': 1, 'measure': 'rate'}                  # Plot a Spike Histogram
cfg.analysis['plotTraces'] = {'include': cfg.recordCells, 'saveFig': True, 'timeRange': timeRange, 'oneFigPer': 'trace', 'legend': True}  # Plot recorded traces for this list of cells
