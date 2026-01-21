import numpy as np
from matplotlib.figure import Figure
from PySpice.Spice.Netlist import Circuit
from PySpice.Unit import *


def dc_sweep_analysis(circuit: Circuit, vinput_name: str, initial_voltage: float, final_voltage: float, step: float):
    simulator = circuit.simulator(temperature=25, nominal_temperature=25)



    # This vodo syntax below is apperntly how I create V{input_name} in a proper way, not string concatenation
    analysis = simulator.dc(**{
    f"V{vinput_name}": slice(initial_voltage, final_voltage, step)
    })


        
    return analysis


def plot_dc_sweep(analysis, vinput_from_node: int, nodes_to_track: list):
    # Create figure without using pyplot (thread-safe method!!)
    fig = Figure(figsize=(10, 5))
    ax = fig.subplots()
    
    # Get input voltage array (x-axis) - this is the node where the voltage source is connected
    input_node_key = str(vinput_from_node)
    input_voltage = np.array(analysis[input_node_key])
    
    # Plot each tracked node
    for node in nodes_to_track:
        node_key = str(node)
        tracked_voltage = np.array(analysis[node_key])
        ax.plot(input_voltage, tracked_voltage, label=f"Node {node}")
    
    ax.set_xlabel("Input Voltage (V)")
    ax.set_ylabel("Voltage (V)")
    if len(nodes_to_track) > 1:
        ax.legend()
    ax.grid(True, alpha=0.3)
    
    return fig


def transient_analysis(circuit: Circuit, step_time: float, end_time: float):
    simulator = circuit.simulator(temperature=25, nominal_temperature=25)
    analysis = simulator.transient(step_time=step_time @ u_s, end_time=end_time @ u_s)
    return analysis



def ac_analysis(circuit: Circuit, start_frequency: float, stop_frequency: float, number_of_points: int, variation: str):
    simulator = circuit.simulator(temperature=25, nominal_temperature=25)
    analysis = simulator.ac(
        start_frequency=start_frequency @ u_Hz,
        stop_frequency=stop_frequency @ u_Hz,
        number_of_points=number_of_points,
        variation=variation
    )
    return analysis

