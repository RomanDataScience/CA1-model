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

sim.gatherData()                  			# gather spiking data and cell info from each node

sim.saveData()                    			# save params, cell info and sim output to file (pickle,mat,txt,etc)#
sim.analysis.plotData()         			# plot spike raster etc

print('completed simulation...')

