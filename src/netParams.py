def define_CA1_zones(netParams, label):
    netParams.addCellParamsSecList(label=label, secListName='perisom', somaDist=[0, 50])
    netParams.addCellParamsSecList(label=label, secListName='basal', somaDist=[0, 200], secListExclude=['apic'])
    netParams.addCellParamsSecList(label=label, secListName='SC_zone', somaDist=[120, 300])
    netParams.addCellParamsSecList(label=label, secListName='PP_zone', somaDist=[320, 1000])
    netParams.addCellParamsSecList(label=label, secListName='below_soma', somaDistY=[-600, 0]) 