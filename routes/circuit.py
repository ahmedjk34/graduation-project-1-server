from flask import Blueprint, request, jsonify

import PySpice
import PySpice.Logging.Logging as Logging
import PySpice.Spice.Simulation
import sys

from pyspice.simulator import create_circuit, map_resistors_and_currents_to_nodes, simulate_circuit
from pyspice.util import build_simulation_response, plot_ac_sweep, plot_transient, validate_sweep_parameters, plot_to_base64, validate_transient_parameters, validate_ac_parameters
from pyspice.sweeps import dc_sweep_analysis, plot_dc_sweep, transient_analysis, ac_analysis

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
#   "dc_voltage_sources": [
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
    
    nodes_to_track = body.get("nodes_to_track")
    if nodes_to_track is None:
        return jsonify({"error": "nodes_to_track is required."}), 400
    if not isinstance(nodes_to_track, list):
        return jsonify({"error": "nodes_to_track must be an array."}), 400
    if len(nodes_to_track) == 0:
        return jsonify({"error": "nodes_to_track must be a non-empty array."}), 400
    
    # Validate all nodes are numeric
    for i, node in enumerate(nodes_to_track):
        if not isinstance(node, (int, float)):
            return jsonify({"error": f"All nodes in nodes_to_track must be numeric. Found non-numeric at index {i}."}), 400
        nodes_to_track[i] = int(node)
    
    try:
        validate_sweep_parameters(initial_voltage, final_voltage, step)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    
    # Validate that component exists in circuit dc_voltage_sources
    dc_voltage_sources = circuit_payload.get("dc_voltage_sources", [])
    vinput_source = None
    for vs in dc_voltage_sources:
        if vs.get("name") == component_name:
            vinput_source = vs
            break

    if not vinput_source:
        return jsonify({"error": f"Vinput.component '{component_name}' must exist in circuit dc_voltage_sources."}), 400
    
    # Get voltage source nodes
    vinput_from_node = vinput_source.get("from")
    vinput_to_node = vinput_source.get("to")
    
    # Validate all nodes exist in circuit and are not ground or Vinput.from_node
    circuit_nodes = circuit_payload.get("nodes", [])
    for node in nodes_to_track:
        if node not in circuit_nodes:
            return jsonify({"error": f"Node {node} must exist in circuit nodes."}), 400
        if node == 0:
            return jsonify({"error": "Node 0 (ground) cannot be tracked in DC sweep analysis."}), 400
        if node == vinput_from_node:
            return jsonify({"error": "nodes_to_track cannot include Vinput.from_node."}), 400
    
    try:
        circuit = create_circuit(circuit_payload)
        
        analysis = dc_sweep_analysis(circuit, component_name, initial_voltage, final_voltage, step)
        
        # ISSUE FIX: (DC sweep error: 0) 
        # This is because ground (node 0) is not accessible in analysis results (index error)
        # For x-axis: use "to" node if "from" is ground (0), otherwise use "from" node
        x_axis_node = vinput_to_node if vinput_from_node == 0 else vinput_from_node
        
        # Create plot
        fig = plot_dc_sweep(analysis, x_axis_node, nodes_to_track)
        
        # Convert to base64
        plot_base64 = plot_to_base64(fig)
        
        return jsonify({
            "status": "ok",
            "plot_base64": plot_base64
        }), 200
    
    except Exception as e:
        logger.error(f"DC sweep error: {str(e)}", exc_info=True)
        return jsonify({"error": f"DC sweep simulation failed: {str(e)}"}), 500


@circuit_bp.route("/transient", methods=["POST"])
def transient():
    body = request.get_json()
    if not body:
        return jsonify({"error": "Request must be JSON."}), 400
    
    # Validate circuit field
    circuit_payload = body.get("circuit")
    if not circuit_payload:
        return jsonify({"error": "Circuit is required."}), 400
    
    # Validate step_time
    step_time = body.get("step_time")
    if step_time is None:
        return jsonify({"error": "step_time is required."}), 400
    if not isinstance(step_time, (int, float)):
        return jsonify({"error": "step_time must be numeric."}), 400
    
    # Validate end_time
    end_time = body.get("end_time")
    if end_time is None:
        return jsonify({"error": "end_time is required."}), 400
    if not isinstance(end_time, (int, float)):
        return jsonify({"error": "end_time must be numeric."}), 400
    
    # Validate nodes_to_track
    nodes_to_track = body.get("nodes_to_track")
    if nodes_to_track is None:
        return jsonify({"error": "nodes_to_track is required."}), 400
    if not isinstance(nodes_to_track, list):
        return jsonify({"error": "nodes_to_track must be an array."}), 400
    if len(nodes_to_track) == 0:
        return jsonify({"error": "nodes_to_track must be a non-empty array."}), 400
    
    # Validate all nodes are numeric
    for i, node in enumerate(nodes_to_track):
        if not isinstance(node, (int, float)):
            return jsonify({"error": f"All nodes in nodes_to_track must be numeric. Found non-numeric at index {i}."}), 400
        nodes_to_track[i] = int(node)
    
    # Validate transient parameters
    try:
        validate_transient_parameters(step_time, end_time)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    
    # Validate all nodes exist in circuit and are not ground
    circuit_nodes = circuit_payload.get("nodes", [])
    for node in nodes_to_track:
        if node not in circuit_nodes:
            return jsonify({"error": f"Node {node} must exist in circuit nodes."}), 400
        if node == 0:
            return jsonify({"error": "Node 0 (ground) cannot be tracked in transient analysis."}), 400
    
    try:
        circuit = create_circuit(circuit_payload)
        
        analysis = transient_analysis(circuit, step_time, end_time)
        
        fig = plot_transient(analysis, nodes_to_track)
        
        plot_base64 = plot_to_base64(fig)
        
        return jsonify({
            "status": "ok",
            "plot_base64": plot_base64
        }), 200
    
    except Exception as e:
        logger.error(f"Transient analysis error: {str(e)}", exc_info=True)
        return jsonify({"error": f"Transient analysis failed: {str(e)}"}), 500


@circuit_bp.route("/ac-sweep", methods=["POST"])
def ac_sweep():
    body = request.get_json()
    if not body:
        return jsonify({"error": "Request must be JSON."}), 400
    
    # Validate circuit field
    circuit_payload = body.get("circuit")
    if not circuit_payload:
        return jsonify({"error": "Circuit is required."}), 400
    
    # Validate start_frequency
    start_frequency = body.get("start_frequency")
    if start_frequency is None:
        return jsonify({"error": "start_frequency is required."}), 400
    if not isinstance(start_frequency, (int, float)):
        return jsonify({"error": "start_frequency must be numeric."}), 400
    
    # Validate stop_frequency
    stop_frequency = body.get("stop_frequency")
    if stop_frequency is None:
        return jsonify({"error": "stop_frequency is required."}), 400
    if not isinstance(stop_frequency, (int, float)):
        return jsonify({"error": "stop_frequency must be numeric."}), 400
    
    # Validate number_of_points
    number_of_points = body.get("number_of_points")
    if number_of_points is None:
        return jsonify({"error": "number_of_points is required."}), 400
    if not isinstance(number_of_points, (int, float)):
        return jsonify({"error": "number_of_points must be numeric."}), 400
    number_of_points = int(number_of_points)
    
    # Validate variation
    variation = body.get("variation")
    if variation is None:
        return jsonify({"error": "variation is required."}), 400
    if not isinstance(variation, str):
        return jsonify({"error": "variation must be a string."}), 400
    
    # Validate node_to_track
    node_to_track = body.get("node_to_track")
    if node_to_track is None:
        return jsonify({"error": "node_to_track is required."}), 400
    if not isinstance(node_to_track, (int, float)):
        return jsonify({"error": "node_to_track must be numeric."}), 400
    node_to_track = int(node_to_track)
    
    # Validate AC parameters
    try:
        validate_ac_parameters(start_frequency, stop_frequency, number_of_points, variation)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    
    # Validate node_to_track exists in circuit and is not ground
    circuit_nodes = circuit_payload.get("nodes", [])
    if node_to_track not in circuit_nodes:
        return jsonify({"error": f"node_to_track {node_to_track} must exist in circuit nodes."}), 400
    if node_to_track == 0:
        return jsonify({"error": "Node 0 (ground) cannot be tracked in AC analysis."}), 400
    
    # Validate circuit has at least one AC voltage source
    ac_voltage_sources = circuit_payload.get("ac_voltage_sources", [])
    if len(ac_voltage_sources) == 0:
        return jsonify({"error": "Circuit must have at least one AC voltage source for AC analysis."}), 400
    
    try:
        circuit = create_circuit(circuit_payload)
        
        analysis = ac_analysis(circuit, start_frequency, stop_frequency, number_of_points, variation)
        
        fig = plot_ac_sweep(analysis, node_to_track)
        
        plot_base64 = plot_to_base64(fig)
        
        return jsonify({
            "status": "ok",
            "plot_base64": plot_base64
        }), 200
    
    except Exception as e:
        logger.error(f"AC sweep error: {str(e)}", exc_info=True)
        return jsonify({"error": f"AC sweep simulation failed: {str(e)}"}), 500