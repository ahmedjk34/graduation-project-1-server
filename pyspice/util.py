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




def plot_to_base64(fig: Figure) -> str:

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches='tight')
    buf.seek(0)
    
    data = base64.b64encode(buf.getbuffer()).decode("ascii")
    
    # Close figure to free memory
    plt.close(fig)
    
    return data
