from PySpice.Unit import *

# Format for voltage source:
# circuit.V('name', 'node from', 'node to', voltage value)
# Format for resistor:
# circuit.R('name', 'node from', 'node to', resistance value)
# Format for diode:
# circuit.D('name', 'node from', 'node to', model='model name')
# Format for capacitor:
# circuit.C('name', 'node from', 'node to', capacitance value) [https://stackoverflow.com/questions/75275416/pyspice-simulate-circuit-with-capacitor-with-defined-initial-condition]
# Format for BJT transistor:
# circuit.BJT('name', collector, base, emitter, model='model_name')

# Creating different models:
# Might use this lib in the future [https://github.com/kicad-spice-library/KiCad-Spice-Library/tree/master]
# 1. Diode:
# circuit.model('name', 'D', IS=4.325@u_nA , RS=0.6458@u_Ohm, BV=100@u_V, IBV=0.0001@u_V, N=1.906 )
# 2. Transistor [https://www.youtube.com/watch?v=hwm2so_r7Kc]:
# circuit.model('2N2222', 'npn', IS=1E-14, VAF=100, BF=200, IKF=0.3, XTB=1.5, BR=3,
            #   CJC=8E-12, CJE=25E-12, TR=100E-9, TF=400E-12, ITF=1,
            #   VTF=2, XTF=3, RB=10, RC=.3, RE=.2, VCEO=30)
            # ngl do not know what half of these parameters are, but we can look them up later TO-DO

transistor_models = {
    '2N2222': {
        'npn': {
            'IS': 1E-14,
            'VAF': 100,
            'BF': 200,
            'IKF': 0.3,
            'XTB': 1.5,
            'BR': 3,
            'CJC': 8E-12,
            'CJE': 25E-12,
            'TR': 100E-9,
            'TF': 400E-12,
            'ITF': 1,
            'VTF': 2,
            'XTF': 3,
            'RB': 10,
            'RC': .3,
            'RE': .2,
            'VCEO': 30,
        }
    }
}

diode_models = {
    '1N4148': {
        'IS': 4.325@u_nA ,
        'RS': 0.6458@u_Ohm,
        'BV': 100@u_V,
        'IBV': 0.0001@u_V,
        'N': 1.906,
    }
}