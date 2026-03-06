TITLE KA
: K-A current for hippocampal interneurons from Lien et al (2002)
: M.Migliore Jan. 2003

NEURON {
	SUFFIX kv1
	USEION k READ ek WRITE ik
	RANGE ik, qtau
	RANGE  gbar, a0h
	GLOBAL pinf, qinf, ptau
}

PARAMETER {
	gbar = 0.0002   	(mho/cm2)	
								
	celsius
	ek		(mV)            : must be explicitly def. in hoc
	v 		(mV)
	a0h=0.17
	vhalfh=-105
	q10=3
	qmin=5
}


UNITS {
	(mA) = (milliamp)
	(mV) = (millivolt)
	(pS) = (picosiemens)
	(um) = (micron)
} 

ASSIGNED {
	ik 		(mA/cm2)
	pinf 		ptau (ms)
	qinf	 	qtau (ms)
}
 

STATE { p q}

BREAKPOINT {
        SOLVE states METHOD cnexp

	ik = gbar*p*q*(v - ek)
} 

INITIAL {
	trates(v)
	p=pinf  
	q=qinf  
}

DERIVATIVE states {   
        trates(v)      
        p' = (pinf-p)/ptau
        q' = (qinf-q)/qtau
}

PROCEDURE trates(v) {  
	LOCAL qt
        qt=q10^((celsius-23)/10)
        pinf = (1/(1 + exp(-(v+41.4)/26.6)))^4
	ptau=0.5/qt
        qinf = 1/(1 + exp((v+78.5)/6))
	qtau = a0h*(v-vhalfh)/qt
	if (qtau<qmin/qt) {qtau=qmin/qt}
}

