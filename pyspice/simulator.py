# NOTE: Node 0 is ground (gnd)

from typing import Dict
from PySpice.Spice.Netlist import Circuit
from PySpice.Unit import *

from .data import diode_models, transistor_models
from .util import format_analysis

def create_circuit(circuit_data: Dict) -> Circuit:
    """
    Create a PySpice circuit from a payload dictionary.
    
    Args:
        circuit_data: Dictionary containing:
            - name: Name of the circuit
            - nodes: List of node numbers
            - voltage_sources: List of voltage source dicts with 'name', 'from', 'to', 'voltage'
            - resistors: List of resistor dicts with 'name', 'from', 'to', 'resistance'
            - capacitors: List of capacitor dicts with 'name', 'from', 'to', 'capacitance'
            - diodes: List of diode dicts with 'name', 'from', 'to', 'model'
            - bjts: List of BJT dicts with 'name', 'collector', 'base', 'emitter', 'model'
    
    Returns:
        Circuit: PySpice Circuit object
    """
    # Create circuit with a default name
    circuit = Circuit(circuit_data['name'])
    
    # Helper function to convert node number/name to circuit node (0 -> gnd)
    def get_node(node_name):
        return circuit.gnd if node_name == 0 else node_name
    
    # We use this to track which models we already fetched [hashmap, slight optimization ;) ]
    added_models = set()
    
    for vs in circuit_data.get('voltage_sources', []):
        name = vs['name']
        from_node = get_node(vs['from'])
        to_node = get_node(vs['to'])
        voltage = vs['voltage'] @ u_V
        circuit.V(name, from_node, to_node, voltage)
    
    for r in circuit_data.get('resistors', []):
        name = r['name']
        from_node = get_node(r['from'])
        to_node = get_node(r['to'])
        resistance = r['resistance'] @ u_Ohm
        resistor = circuit.R(name, from_node, to_node, resistance)
        resistor.plus.add_current_probe(circuit)

    
    for c in circuit_data.get('capacitors', []):
        name = c['name']
        from_node = get_node(c['from'])
        to_node = get_node(c['to'])
        capacitance = c['capacitance'] @ u_F
        circuit.C(name, from_node, to_node, capacitance)
    
    for d in circuit_data.get('diodes', []):
        name = d['name']
        from_node = get_node(d['from'])
        to_node = get_node(d['to'])
        model_name = d['model']
        
        # Create model if it exists in data.py and hasn't been added yet,
        # This will be used for any model based component
        if model_name in diode_models and model_name not in added_models:
            model_params = diode_models[model_name]
            circuit.model(model_name, 'D', **model_params)
            added_models.add(model_name)
        
        circuit.Diode(name, from_node, to_node, model=model_name)
    
    for bjt in circuit_data.get('bjts', []):
        name = bjt['name']
        bjt_type = bjt['type']
        collector = get_node(bjt['collector'])
        base = get_node(bjt['base'])
        emitter = get_node(bjt['emitter'])
        model_name = bjt['model']
        
        if model_name in transistor_models and model_name not in added_models:
            model = transistor_models[model_name]

            # Nested structure for transistor models
            for bjt_type, model_params in model.items():
                circuit.model(model_name, bjt_type, **model_params)
                added_models.add(model_name)
            
            circuit.BJT(name, collector, base, emitter, model=model_name)
    
    return circuit


def simulate_circuit(circuit: Circuit) -> Dict:
    """
    Simulate a PySpice circuit and return the results.
    
    Args:
        circuit: PySpice Circuit object
    
    Returns:
        Dict: Dictionary containing the simulation results [we format it however we want]
    """
    simulator = circuit.simulator(temperature=25, nominal_temperature=25)
    analysis = simulator.operating_point()

    return format_analysis(analysis)


#IDEA:
# I actually figure the arbitrary nodes on the front-end, and I also do the resistor names
# I tested many combinations, and the result is always the same vr[REISTOR_NAME_SMALLCASE]_plus
# I can use that + the payload passed from the frontend, and I can map the resistors to the nodes
# Which I can use to get the current for each resistor, therefore nodes.

from typing import Dict, Any, List

#what to return:
# e.g. 
# {"resistor1": {"from_node": 1, "to_node": 2, "current": 0.1}}
def map_resistors_and_currents_to_nodes(node_currents: Dict[str, float], resistors: list[dict[str, str]]) -> Dict[str, Any]:
    """
    Map the resistors to the nodes in the circuit.
    """
    resistor_nodes_and_currents = {}
    for resistor in resistors:
        resistor_name = resistor['name']
        resistor_current = node_currents.get(f'vr{resistor_name.lower()}_plus')
        resistor_nodes_and_currents[resistor_name] = {
            "current": resistor_current,
            "from_node": resistor['from'],
            "to_node": resistor['to']
        }
    return resistor_nodes_and_currents