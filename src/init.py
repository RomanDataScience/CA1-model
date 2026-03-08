import matplotlib; matplotlib.use('Agg')  # to avoid graphics error in servers
from netpyne import sim
import json
from netParams import netParams, cfg
from pathlib import Path

sim.initialize(
    simConfig = cfg, 	
    netParams = netParams)  				# create network object and set cfg and net params
sim.net.createPops()               			# instantiate network populations
sim.net.createCells()              			# instantiate network cells based on defined populations

sim.net.connectCells()            			# create connections between cells based on params
sim.net.addStims() 							# add network stimulation
sim.setupRecording()              			# setup variables to record for each cell (spikes, V traces, etc)

sim.runSim()                              # run parallel Neuron simulation (calling func to modify mechs)
#----------
from neuron import h
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from netpyne import sim
from netpyne.support import morphology as morph

# 1) Base shape (no syns), and force current axis to 3D
fig, _ = sim.analysis.plotShape(includePost=['PC2B'], showSyns=False, saveFig=False)
ax3d = next(ax for ax in fig.axes if hasattr(ax, "get_zlim3d"))
plt.figure(fig.number)
plt.sca(ax3d)

post_cells = sim.getCellsList(['PC2B'])

# 2) gid -> pop map (presyn identity)
gid_to_pop = {c.gid: c.tags.get('pop', 'unknown') for c in sim.net.cells}

# 3) One color per presyn pop
pre_pops = sorted({
    gid_to_pop.get(conn.get('preGid'), 'NetStim')
    for cell in post_cells
    for conn in cell.conns
    if conn.get('preGid') is not None
})
palette = ['#e41a1c', '#377eb8', '#4daf4a', '#ff7f00', '#984ea3', '#a65628', '#f781bf', '#999999']
color_by_pop = {pop: palette[i % len(palette)] for i, pop in enumerate(pre_pops)}

# 4) Plot synapses colored by presyn pop
for cell in post_cells:
    for conn in cell.conns:
        sec_name = conn.get('sec')
        loc = conn.get('loc')
        if sec_name not in cell.secs or loc is None:
            continue

        pre_pop = gid_to_pop.get(conn.get('preGid'), 'NetStim')
        sec_hobj = cell.secs[sec_name]['hObj']
        morph.mark_locations(
            h, sec_hobj, float(loc),
            markspec='o',
            color=color_by_pop[pre_pop],
            markersize=2
        )

# Optional legend
handles = [
    Line2D([0], [0], marker='o', color='w', markerfacecolor=color_by_pop[p], label=p, markersize=6)
    for p in pre_pops
]
ax3d.legend(handles=handles, loc='upper left', fontsize=8)

plt.savefig('SimGeom_by_pre_pop.png', dpi=300, bbox_inches='tight')
#----------


sim.gatherData()                  			# gather spiking data and cell info from each node

sim.saveData()                    			# save params, cell info and sim output to file (pickle,mat,txt,etc)#
sim.analysis.plotData()         			# plot spike raster etc

print('completed simulation...')

# if sim.rank == 0:
#     # netParams.save("{}/{}_params.json".format(cfg.saveFolder, cfg.simLabel))
#     print('transmitting data...')
#     inputs = cfg.get_mappings()
#     # print(json.dumps({**inputs}))
#     results = sim.analysis.popAvgRates(tranges=cfg.timeRanges, show=False) #TODO: Avoid printing firing rates

#     sim.simData['popRates'] = results

#     fitnessFuncArgs = {}
#     pops = {}
#     ## Exc pops
#     Epops = ['IT2', 'IT4', 'IT5A', 'IT5B', 'PT5B', 'IT6', 'CT6']
#     Etune = {'target': 5, 'width': 5, 'min': 0.5}
#     for pop in Epops:
#         pops[pop] = Etune
#     ## Inh pops
#     Ipops = ['NGF1', 'PV2', 'SOM2', 'VIP2', 'NGF2',
#              'PV4', 'SOM4', 'VIP4', 'NGF4',
#              'PV5A', 'SOM5A', 'VIP5A', 'NGF5A',
#              'PV5B', 'SOM5B', 'VIP5B', 'NGF5B',
#              'PV6', 'SOM6', 'VIP6', 'NGF6']
#     Itune = {'target': 10, 'width': 15, 'min': 0.25}
#     for pop in Ipops:
#         pops[pop] = Itune
#     fitnessFuncArgs['pops'] = pops
#     fitnessFuncArgs['maxFitness'] = 1000

#     rateLoss = defs.rateFitnessFunc(sim.simData, **fitnessFuncArgs)
#     results['loss'] = rateLoss
#     out_json = json.dumps({**inputs, **results})

#     print(out_json)
#     sim.send(out_json)
