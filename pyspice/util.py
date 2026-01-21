# This file is directly copied from the tutorial repo [https://github.com/benedictjones/engineeringthings-pyspice/blob/main/utils/methods.py]
import base64
import io
from matplotlib.figure import Figure
import numpy as np
import os
from typing import List, Dict, Optional
import PySpice
import PySpice.Probe.WaveForm
from PySpice.Spice.Netlist import Circuit
import matplotlib.pyplot as plt


def cast_waveform(waveform) -> np.ndarray|float:
    """
    Function to cast PySpice wafe forms to a numpy array,
    or a float (if only a single value).
    """
    if len(waveform) == 1:
        return float(waveform[0])
    else:
        return np.array(waveform)


def format_analysis(
    analysis,
    cast:bool=True,
) -> Dict[str|int, np.ndarray|float|PySpice.Probe.WaveForm.WaveForm]:
    '''
    Extracts dictionary containing SPICE sim values.
    The typical waveform analysis result can be cast to a numpy array.

    Args:
        analysis (pysepice simulation run object):
            The run analysis
        cast (bool):
            Whether to convert waveform outputs to
            single float value or numpy array.

    Returns:
        dict: analysis results dictionary
    '''

    if hasattr(analysis, 'nodes') is False:
        raise ValueError('Must pass a completed analysis')

    res = {}
    
    # Include node voltages in a nested structure
    node_voltages = {}
    for node, waveform in analysis.nodes.items():
        node_voltages[node] = cast_waveform(waveform) if cast else waveform
    res['node_voltages'] = node_voltages

    node_currents = {}
    # Note, in the tutorial, they use analysis.branches.values(), but that did not work for me
    # Kept getting that error [TypeError: unhashable type: 'WaveForm']
    # So, I kind of took a guess based on the first tutorial series, and used the functions I took from github, and it worked. lol
    for branch_name, waveform in analysis.branches.items():
        node_currents[branch_name] = cast_waveform(waveform) if cast else waveform
    res['node_currents'] = node_currents

    # Include time if it exists
    if hasattr(analysis, 'time'):
        res['time'] = cast_waveform(analysis.time) if cast else analysis.time

    # Include frequency if it exists
    if hasattr(analysis, 'frequency'):
        res['frequency'] = cast_waveform(analysis.frequency) if cast else analysis.frequency


    return res


def write_line_to_netlist(
    circuit:Circuit,
    new_line:str
) -> Circuit:
    """
    Wite a string as a new line to a circuit's netlist.

    Args:
        cir (Circuit):
            PySpice Circuit object.
        new_line (str):
            String to become the new line.

    Returns:
        Circuit: PySpice circuit object with added Raw SPICE line
    """
    circuit.raw_spice += new_line + os.linesep
    return circuit


def build_simulation_response(simulation_results: Dict[str, float], resistor_nodes_and_currents: Dict[str, float]) -> Dict[str, float]:
    response = simulation_results.copy()
    if 'node_currents' in response:
        response['node_currents'] = resistor_nodes_and_currents
    return response



# This is a logical validation function that I thought about, was thinking about allowed start , final, vals, and realized it's a free game as long as step size agrees
def validate_sweep_parameters(initial_voltage, final_voltage, step):

    # Check if all values are numeric
    if not isinstance(initial_voltage, (int, float)):
        raise ValueError("initial_voltage must be numeric")
    if not isinstance(final_voltage, (int, float)):
        raise ValueError("final_voltage must be numeric")
    if not isinstance(step, (int, float)):
        raise ValueError("step must be numeric")
    
    # Check if range is non-zero
    if initial_voltage == final_voltage:
        raise ValueError("initial_voltage and final_voltage cannot be equal")
    
    # Forward sweep (initial < final)
    if initial_voltage < final_voltage:
        if step <= 0:
            raise ValueError("For forward sweep (initial < final), step must be positive")
        if step > (final_voltage - initial_voltage):
            raise ValueError("Step magnitude cannot exceed the voltage range")
    
    # Backward sweep (initial > final)
    elif initial_voltage > final_voltage:
        if step >= 0:
            raise ValueError("For backward sweep (initial > final), step must be negative")
        if abs(step) > (initial_voltage - final_voltage):
            raise ValueError("Step magnitude cannot exceed the voltage range")
    
    return True, None


def validate_transient_parameters(step_time, end_time):
    # Check if all values are numeric
    if not isinstance(step_time, (int, float)):
        raise ValueError("step_time must be numeric")
    if not isinstance(end_time, (int, float)):
        raise ValueError("end_time must be numeric")
    
    # Check if step_time is positive
    if step_time <= 0:
        raise ValueError("step_time must be positive")
    
    # Check if end_time is greater than step_time
    if end_time <= step_time:
        raise ValueError("end_time must be greater than step_time")
    
    return True


def validate_ac_parameters(start_frequency, stop_frequency, number_of_points, variation):
    # Check if all values are numeric (except variation)
    if not isinstance(start_frequency, (int, float)):
        raise ValueError("start_frequency must be numeric")
    if not isinstance(stop_frequency, (int, float)):
        raise ValueError("stop_frequency must be numeric")
    if not isinstance(number_of_points, (int, float)):
        raise ValueError("number_of_points must be numeric")
    if not isinstance(variation, str):
        raise ValueError("variation must be a string")
    
    # Check if start_frequency is positive
    if start_frequency <= 0:
        raise ValueError("start_frequency must be positive")
    
    # Check if stop_frequency is greater than start_frequency
    if stop_frequency <= start_frequency:
        raise ValueError("stop_frequency must be greater than start_frequency")
    
    # Check if number_of_points is positive integer
    if not isinstance(number_of_points, int) or number_of_points <= 0:
        raise ValueError("number_of_points must be a positive integer")
    
    # Check if variation is valid
    if variation not in ["dec", "lin"]:
        raise ValueError("variation must be 'dec' or 'lin'")
    
    return True




def plot_transient(analysis, nodes_to_track: list):
    # Create figure without using pyplot (thread-safe method)
    fig = Figure(figsize=(12, 6))
    ax = fig.subplots()
    
    # Get time array (x-axis)
    time = np.array(analysis.time)
    
    # Plot each node
    for node in nodes_to_track:
        node_key = str(node)
        voltage = np.array(analysis[node_key])
        ax.plot(time, voltage, label=f"Node {node}")
    
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Voltage (V)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    return fig

# Create a Bode plot (magnitude and phase) for AC analysis.
def plot_ac_sweep(analysis, node_to_track: int):

    # Create figure with 2 subplots (thread-safe method)
    fig = Figure(figsize=(10, 8))
    axes = fig.subplots(2, 1)
    
    # Get frequency array (x-axis)
    frequency = np.array(analysis.frequency)
    
    # Get complex voltage at tracked node
    node_key = str(node_to_track)
    complex_voltage = np.array(analysis[node_key])
    
    # Calculate magnitude in dB
    magnitude_db = 20 * np.log10(np.absolute(complex_voltage))
    
    # Calculate phase in degrees
    phase_degrees = np.angle(complex_voltage, deg=True)
    
    # Plot magnitude (top subplot)
    axes[0].plot(frequency, magnitude_db)
    axes[0].set_xscale('log')
    axes[0].set_xlabel("Frequency (Hz)")
    axes[0].set_ylabel("Magnitude (dB)")
    axes[0].grid(True, alpha=0.3)
    axes[0].set_title(f"Bode Diagram - Node {node_to_track}")
    
    # Plot phase (bottom subplot)
    axes[1].plot(frequency, phase_degrees)
    axes[1].set_xscale('log')
    axes[1].set_xlabel("Frequency (Hz)")
    axes[1].set_ylabel("Phase (degrees)")
    axes[1].grid(True, alpha=0.3)
    
    fig.tight_layout()
    
    return fig


def plot_to_base64(fig: Figure) -> str:

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches='tight')
    buf.seek(0)
    
    data = base64.b64encode(buf.getbuffer()).decode("ascii")
    
    # Close figure to free memory
    plt.close(fig)
    
    return data
