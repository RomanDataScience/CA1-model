: This mechanism describes a current clamp
: Val G. Rousseau - 04/29/2020

NEURON {
    POINT_PROCESS CurrentClamp
    RANGE Delay,Duration,Amplitude,i
    ELECTRODE_CURRENT i
}

UNITS {
    (nA)=(nanoamp)
}

PARAMETER {
    Delay (ms)
    Duration (ms) <0,1e9>
    Amplitude (nA)
}

ASSIGNED {
    i (nA)
}

INITIAL {
    i=0
}

BREAKPOINT {
    at_time(Delay)
    at_time(Delay+Duration)
    
    if (t>Delay && t<Delay+Duration) {
        i=Amplitude
    } else {
        i=0
    }
}
