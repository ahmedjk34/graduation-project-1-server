# This file will basically be some sort of doc / reference for the ngspice tutorial on youtube
# Will come back to it a lot
# Usually, I write docs for new things I learn on notion, but I have NO INTEREST in using this outside of the grad project if I'm being honest


# Video 1: Nothing in it really. just prerequisites and what to install 

# Video 2: Basic Syntax, Netlists and Operating Point Analysis


import PySpice
import PySpice.Logging.Logging as Logging
from PySpice.Spice.Netlist import Circuit
from PySpice.Unit import *

from ..util import format_analysis


logger = Logging.setup_logging()




# used the bundled ngspice shared library instead of system ngspice [compatibility issue, I have ngspice 36 and tried to downgrade but was really a pain sooo]
if sys.platform == "linux" or sys.platform == "linux2":
    PySpice.Spice.Simulation.CircuitSimulator.DEFAULT_SIMULATOR = 'ngspice-shared'
elif sys.platform == "win32":
    pass


circuit = Circuit('Diode Test') 

# Define a diode model
# Now, it's best to actual mimic a real life diode model
# Will be using (1N4148PH)
# @params:
# 1. name of the model
# 2. type of the model
# 3. IS (reverse saturation current)
# 4. RS (series resistance)
# 5. BV (breakdown voltage)
# 6. IBV (breakdown current)
# 7. N (emission coefficient) [had to google what that even means]
circuit.model("MyDiode" , 'D' , IS=4.325@u_nA , RS=0.6458@u_Ohm, BV=100@u_V, IBV=0.0001@u_V, N=1.906)

circuit.V('input', 1, circuit.gnd, 10@u_V)
circuit.R('r1', 1, 2, 9@u_kOhm)
circuit.Diode('d1', 2, 3, model='MyDiode')

circuit.R('r2', 3, circuit.gnd, 9@u_kOhm)
circuit.Diode('d2', 3, circuit.gnd, model='MyDiode')

# print(circuit)
# .title Diode Test
# Vinput 1 0 10V
# Rr1 1 2 9kOhm
# Dd1 2 3 MyDiode
# Rr2 3 0 9kOhm
# Dd2 3 0 MyDiode
# .model MyDiode D (BV=100V IBV=0.0001V IS=4.325nA N=1.906 RS=0.6458Ohm)


# analysis = circuit.simulator(temperature=25, nominal_temperature=25).operating_point()

# print(format_analysis(analysis))
# {'3': 0.6008275577104337, '2': 1.2051633969829967, '1': 10.0}

# CONCEPT: Raw Spice
# - can add raw spice commands to the circuit object
# - this is useful for adding custom models or commands
# - you should be aware of the proper syntax used though
# - Example: circuit.Diode('d2', 3, circuit.gnd, model='MyDiode' , raw_spice='IS=1@u_nA')


# CONCEPT: Sub circuits
# - According to the yt guy, super powerful not many spice programs can do
# - Basically, you can define a circuit within a circuit
# - And you can play around with the sub circuit as if it was a regular circuit, and observe results easily




# from PySpice.Spice.Netlist import SubCircuit

# class MySubCir(SubCircuit):

#     __nodes__ = ('t_in', 't_out')
#     def __init__(self, name, r=1@u_kOhm):

#         SubCircuit.__init__(self, name, *self.__nodes__)

#         self.R(2, 't_in', 't_out', r)
#         self.Diode(2, 't_in', 't_out', model='MyDiode')

#         return

