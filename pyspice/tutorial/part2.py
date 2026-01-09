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


# Initialize circuit with Circuit class (@param name: name of the circuit)
circuit = Circuit('Voltage Divider') 

circuit.raw_spice = '.options NOINIT\n.options ngbehavior=all\n'

# Add voltage sources
# @params:
# 1. name of the voltage source
# 2. name of the node where the voltage source is connected
# 3. name of the node where the voltage source is connected to (e.g ground)
# 4. voltage value
circuit.V('input', 'in', circuit.gnd, 10@u_V)

# Notes: gnd is the ground node, and we define 10V as 10@u_V (@u is unit, and _V is voltage)

# Add resistors
# @params:
# 1. name of the resistor
# 2. name of the node where the resistor is connected
# 3. name of the node where the resistor is connected to (e.g ground)
# 4. resistance value
circuit.R('r1', 'in', 'out', 9@u_kOhm) # could use the ASCII for ohm (Ω) or just write Ohm
circuit.R('r2', 'out', circuit.gnd, 1@u_kOhm)

# Create simulator and run analysis
# @params:
# 1. temperature (since it has effect on the semi-conductor properties)
# 2. nominal_temperature (benchmark temperature for the circuit)
simulator = circuit.simulator(temperature=25, nominal_temperature=25)

# Print the netlist
# print(circuit)

#Result:
# .title Voltage Divider
# Vinput in 0 10V
# Rr1 in out 1kOhm
# Rr2 out 0 1kOhm

# Since I'm a superior human-being and use linux as my primary OS, it does not have LTSpice, but a library can help
# sudo apt install ngspice 
# create a netlist file [netlist.cir]
# run with ngspice netlist.cir
# and I can use that to run the netlist and see
# WHO NEEDS A GUI.

# print(simulator)

# .title Voltage Divider
# Vinput in 0 10V
# Rr1 in out 1kOhm
# Rr2 out 0 1kOhm
# .options TEMP = 25C
# .options TNOM = 25C
# .options NOINIT
# .options filetype = binary
# .end


analysis = simulator.operating_point()

# print(analysis)
# print(analysis.nodes['in'])
# print(str(analysis.nodes['in']))
# print(float(analysis.nodes['in']))

# Result:
# <PySpice.Probe.WaveForm.OperatingPoint object at 0x7c273b43bf70> (an object)
# in
# in (string =  node name )
# 10.0 (float = value)


# print(float(analysis.nodes['out']))

# 1.0 [voltage divider!]

print(format_analysis(analysis))

#{'out': 1.0, 'in': 10.0} 
# Note: run as a module: python -m pyspice.tutorial.part2