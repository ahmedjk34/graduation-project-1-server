# This focuses on doing a DC Sweep simulation
import numpy as np
import matplotlib.pyplot as plt
import sys



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

circuit = Circuit('Tutorial 6.1')

# # create the circuit
circuit = Circuit('Tutorial 6.1')

# # add components to the circuit
# circuit.V('input', 'n1', circuit.gnd, 10@u_V) # DC voltage comonent
Vac = circuit.SinusoidalVoltageSource('input', 'n1', circuit.gnd, amplitude=1@u_V, frequency=100@u_Hz)
R = circuit.R(1, 'n1', 'n2', 1@u_kOhm)  # @u_kΩ is a unit of kOhms
C = circuit.C(1, 'n2', circuit.gnd, 1@u_uF)
circuit.Diode(1, 'n2', 'n3', model='MyDiode')  # using cutom defined diode
circuit.R(2, 'n3', circuit.gnd, 1@u_kOhm)  # @u_kΩ is a unit of kOhms

# add our diode
circuit.model('MyDiode', 'D', IS=4.352@u_nA, RS=0.6458@u_Ohm, BV=110@u_V, IBV=0.0001@u_V, N=1.906)  # Define the 1N4148PH (Signal Diode)

# Print the netlist
# print(circuit)


simulator = circuit.simulator(temperature=25, nominal_temperature=25)



# # This is the transient analysis command 
# analysis = simulator.transient(step_time=0.0001, end_time=0.1)



# plt.plot(np.array(analysis.time), np.array(analysis["n1"]), label='V(n1)')
# plt.plot(np.array(analysis.time), np.array(analysis["n2"]), label='V(n2)')
# plt.plot(np.array(analysis.time), np.array(analysis["n3"]), label='V(n3)')
# plt.xlabel("Time (s)")
# plt.ylabel("Output Voltage")
# plt.legend()
# plt.show()


# We can use our defined voltage source to specify our step and end time sensibly.

# analysis = simulator.transient(step_time=Vac.period/1000, end_time=Vac.period)

# plt.plot(np.array(analysis.time), np.array(analysis["n1"]), label='V(n1)')
# plt.plot(np.array(analysis.time), np.array(analysis["n2"]), label='V(n2)')
# plt.plot(np.array(analysis.time), np.array(analysis["n3"]), label='V(n3)')
# plt.xlabel("Time (s)")
# plt.ylabel("Output Voltage")
# plt.legend()
# plt.show()




# ----

# AC
# analysis = simulator.ac(start_frequency=1@u_Hz, stop_frequency=1@u_MHz, number_of_points=10,  variation='dec')


# TO-DO: RESEARCH WHATEVER THIS IS, ITS LIKE SIGNALS BUT I TOOK THAT 2 YEARS AGO. I BARELY REMEMBER WHAT I HAD FOR BREAKFAST


# import math

# break_frequency = 1 / (2 * math.pi * float(R.resistance * C.capacitance))
# print("Break frequency = {:.1f} Hz".format(break_frequency))

# from PySpice.Plot.BodeDiagram import bode_diagram

# fig, axes = plt.subplots(2)
# plt.title("Bode Diagram of a Low-Pass RC Filter")
# bode_diagram(axes=axes,
#              frequency=analysis.frequency,
#              gain=20*np.log10(np.absolute(analysis.n2)),
#              phase=np.angle(analysis.n2, deg=False),
#              marker='.',
#              color='blue',
#              linestyle='-')

# # Add a vertical line at the
# for ax in axes:
#     ax.axvline(x=break_frequency, color='red')

# plt.tight_layout()

# plt.show()