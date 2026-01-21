from flask import Blueprint, request, jsonify

import PySpice
import PySpice.Logging.Logging as Logging
import PySpice.Spice.Simulation
import sys

from pyspice.simulator import create_circuit, map_resistors_and_currents_to_nodes, simulate_circuit
from pyspice.util import build_simulation_response, validate_sweep_parameters, plot_to_base64
from pyspice.sweeps import dc_sweep_analysis, plot_dc_sweep

if sys.platform == "linux" or sys.platform == "linux2":
    PySpice.Spice.Simulation.CircuitSimulator.DEFAULT_SIMULATOR = 'ngspice-shared'
elif sys.platform == "win32":
    pass


circuit_bp = Blueprint("circuit", __name__)

logger = Logging.setup_logging()

@circuit_bp.route("/simulate", methods=["POST"])

# BODY PASSED
# {
#     "circuit":{
#   "name": "name",
#   "nodes": [1, 2, 3, 0],
#   "voltage_sources": [
#     {
#       "name": "V1",
#       "from": 1,
#       "to": 0,
#       "voltage": 12
#     },
#     {
#       "name": "V2",
#       "from": 2,
#       "to": 0,
#       "voltage": 5
#     }
#   ],
#   "resistors": [
#     {
#       "name": "R1312312",
#       "from": 1,
#       "to": 2,
#       "resistance": 1000
#     },
#     {
#       "name": "R2",
#       "from": 2,
#       "to": 3,
#       "resistance": 2200
#     }
#   ],
#   "capacitors": [
#     {
#       "name": "C1",
#       "from": 2,
#       "to": 0,
#       "capacitance": 0.001
#     }
#   ],
#   "diodes": [
#     {
#       "name": "D1",
#       "from": 3,
#       "to": 0,
#       "model": "1N4148"
#     }
#   ],
#   "bjts": [
#     {
#       "name": "Q1",
#       "type" : "NPN",
#       "collector": 3,
#       "base": 2,
#       "emitter": 0,
#       "model": "2N2222"
#     }
#   ]
# }
# }
def simulate():
    body = request.get_json()
    if not body:
        return jsonify({"error": "Request must be JSON."}), 400
    circuit_payload = body.get("circuit")
    if not circuit_payload:
        return jsonify({"error": "Circuit is required."}), 400
   
    circuit = create_circuit(circuit_payload)

    simulation_results = simulate_circuit(circuit)
    # print(simulation_results.get("node_currents"))
    # print("---")
    # print(circuit_payload.get("resistors"))
    resistor_nodes_and_currents = map_resistors_and_currents_to_nodes(simulation_results.get("node_currents") ,circuit_payload.get("resistors"))

    simulation_response = build_simulation_response(simulation_results , resistor_nodes_and_currents)

    return jsonify({"status": "ok"} , simulation_response), 200



@circuit_bp.route("/dc-sweep", methods=["POST"])
def dc_sweep():
    body = request.get_json()
    print(body)
    if not body:
        return jsonify({"error": "Request must be JSON."}), 400
    
    circuit_payload = body.get("circuit")
    if not circuit_payload:
        return jsonify({"error": "Circuit is required."}), 400
    
    vinput = body.get("Vinput")
    if not vinput:
        return jsonify({"error": "Vinput is required."}), 400
    
    component_name = vinput.get("component")
    initial_voltage = vinput.get("initial_voltage")
    final_voltage = vinput.get("final_voltage")
    step = vinput.get("step")
    
    if component_name is None:
        return jsonify({"error": "Vinput.component is required."}), 400
    if initial_voltage is None:
        return jsonify({"error": "Vinput.initial_voltage is required."}), 400
    if final_voltage is None:
        return jsonify({"error": "Vinput.final_voltage is required."}), 400
    if step is None:
        return jsonify({"error": "Vinput.step is required."}), 400
    
    node_to_track = body.get("node_to_track")
    if node_to_track is None:
        return jsonify({"error": "node_to_track is required."}), 400
    if not isinstance(node_to_track, (int, float)):
        return jsonify({"error": "node_to_track must be numeric."}), 400
    node_to_track = int(node_to_track)
    
    try:
        validate_sweep_parameters(initial_voltage, final_voltage, step)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    
    # Validate that component exists in circuit voltage_sources
    voltage_sources = circuit_payload.get("voltage_sources", [])
    vinput_source = None
    for vs in voltage_sources:
        if vs.get("name") == component_name:
            vinput_source = vs
            break
    
    if not vinput_source:
        return jsonify({"error": f"Vinput.component '{component_name}' must exist in circuit voltage_sources."}), 400
    
    # Validate that node_to_track is not the same as Vinput.from_node
    vinput_from_node = vinput_source.get("from")
    if node_to_track == vinput_from_node:
        return jsonify({"error": "node_to_track cannot be the same as Vinput.from_node."}), 400
    
    # Validate that node_to_track exists in circuit nodes
    circuit_nodes = circuit_payload.get("nodes", [])
    if node_to_track not in circuit_nodes:
        return jsonify({"error": f"node_to_track {node_to_track} must exist in circuit nodes."}), 400
    
    try:
        circuit = create_circuit(circuit_payload)
        
        analysis = dc_sweep_analysis(circuit, component_name, initial_voltage, final_voltage, step)
        
        # Create plot (use vinput_from_node for x-axis since analysis keys are node numbers)
        fig = plot_dc_sweep(analysis, vinput_from_node, node_to_track)
        
        # Convert to base64
        plot_base64 = plot_to_base64(fig)
        
        return jsonify({
            "status": "ok",
            "plot_base64": plot_base64
        }), 200
    
    except Exception as e:
        logger.error(f"DC sweep error: {str(e)}", exc_info=True)
        return jsonify({"error": f"DC sweep simulation failed: {str(e)}"}), 500