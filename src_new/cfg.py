from pathlib import Path

from netpyne import specs


cfg = specs.SimConfig()

# -----------------------------------------------------------------------------
# Simulation
# -----------------------------------------------------------------------------
cfg.Transient = 500
cfg.dt = 0.1
cfg.cvode_active = True
cfg.cvode_atol = 1e-5
cfg.progressBar = 0
cfg.hParams = {'v_init': -70.0, 'celsius': 34.0}

cfg.verbose = False
cfg.validateNetParams = False
cfg.recordStep = cfg.dt
cfg.printRunTime = 0.1
cfg.seeds = {'conn': 4321, 'stim': 1234, 'loc': 4321, 'cell': 4321}

cfg.saveFolder = 'output_multisyn_netpyne'
cfg.simLabel = 'multisyn_netpyne'
Path(cfg.saveFolder).mkdir(parents=True, exist_ok=True)

cfg.saveJson = True
cfg.savePickle = False
cfg.saveDataInclude = ['simData', 'simConfig', 'netParams']

# -----------------------------------------------------------------------------
# Cell
# -----------------------------------------------------------------------------
cfg.PYR = 1
cfg.PYRFile = 'cells/PC2B_new.json'

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

# Optional global override for all ican.concrelease (applied after control).
cfg.overrideIcanConcrelease = None

cfg.simLabel += f'_Control{cfg.applyControlPC2B}' 

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
factorSyn = 0.208 # 0.208
cfg.thetaAMPAWeight = 1.2 * 0.00156 * factorSyn
cfg.thetaNMDAWeight = 1.2 * 0.000882 * factorSyn

# One VecStim source population per pathway
cfg.SC = 1
cfg.PP = 1

# -----------------------------------------------------------------------------
# Recording
# -----------------------------------------------------------------------------
cfg.recordTime = True
allpops = ['PC2B', 'OLM', 'VIP', 'SC', 'PP']
timeRange = [cfg.Transient - 200., cfg.duration]
cfg.recordCells = [(pop,0) for pop in allpops if pop not in ['SC', 'PP']]
cfg.recordTraces = {'V_soma':{'sec':'soma','loc':0.5,'var':'v'}}  # Dict with traces to record
cfg.analysis['plotRaster'] = {'include': allpops,'saveFig': True, 'timeRange': timeRange} # Plot a raster
cfg.analysis['plotSpikeHist'] = {'include': allpops, 'saveFig': True, 'timeRange': timeRange, 'binSize': 1, 'measure': 'rate'}                  # Plot a Spike Histogram
cfg.analysis['plotTraces'] = {'include': cfg.recordCells, 'saveFig': True, 'timeRange': timeRange}  # Plot recorded traces for this list of cells
