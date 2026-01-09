from flask import Blueprint, request, jsonify

import PySpice
import PySpice.Logging.Logging as Logging
import PySpice.Spice.Simulation
import sys

from pyspice.simulator import create_circuit, simulate_circuit

if sys.platform == "linux" or sys.platform == "linux2":
    PySpice.Spice.Simulation.CircuitSimulator.DEFAULT_SIMULATOR = 'ngspice-shared'
elif sys.platform == "win32":
    pass


circuit_bp = Blueprint("circuit", __name__)

logger = Logging.setup_logging()

@circuit_bp.route("/simulate", methods=["POST"])

def simulate():
    body = request.get_json()
    if not body:
        return jsonify({"error": "Request must be JSON."}), 400
    circuit = body.get("circuit")
    if not circuit:
        return jsonify({"error": "Circuit is required."}), 400
   
    circuit = create_circuit(circuit)

    simulation_results = simulate_circuit(circuit)

    return jsonify({"status": "ok"} , simulation_results), 200