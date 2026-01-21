from flask import Blueprint, request, jsonify

import PySpice
import PySpice.Logging.Logging as Logging
import PySpice.Spice.Simulation
import sys

from pyspice.simulator import create_circuit, map_resistors_and_currents_to_nodes, simulate_circuit
from pyspice.util import build_simulation_response

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