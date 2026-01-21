import numpy as np
from matplotlib.figure import Figure
from PySpice.Spice.Netlist import Circuit


def dc_sweep_analysis(circuit: Circuit, vinput_name: str, initial_voltage: float, final_voltage: float, step: float):
    simulator = circuit.simulator(temperature=25, nominal_temperature=25)



    # This vodo syntax below is apperntly how I create V{input_name} in a proper way, not string concatenation
    analysis = simulator.dc(**{
    f"V{vinput_name}": slice(initial_voltage, final_voltage, step)
    })


        
    return analysis


def plot_dc_sweep(analysis, vinput_from_node: int, node_to_track: int):
    # Create figure without using pyplot (thread-safe method!!)
    fig = Figure(figsize=(10, 5))
    ax = fig.subplots()
    
    # Get input voltage array (x-axis) - this is the node where the voltage source is connected
    input_node_key = str(vinput_from_node)
    input_voltage = np.array(analysis[input_node_key])
    
    # Get tracked node voltage array (y-axis)
    node_key = str(node_to_track)
    tracked_voltage = np.array(analysis[node_key])
    
    ax.plot(input_voltage, tracked_voltage)
    ax.set_xlabel("Input Voltage (V)")
    ax.set_ylabel(f"Node {node_to_track} Voltage (V)")
    ax.grid(True, alpha=0.3)
    
    return fig
