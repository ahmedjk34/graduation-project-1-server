# This focuses on doing a DC Sweep simulation
import numpy as np
import matplotlib.pyplot as plt
import sys



import PySpice
import PySpice.Logging.Logging as Logging
from PySpice.Spice.Netlist import Circuit
from PySpice.Unit import *

logger = Logging.setup_logging()


# used the bundled ngspice shared library instead of system ngspice [compatibility issue, I have ngspice 36 and tried to downgrade but was really a pain sooo]
if sys.platform == "linux" or sys.platform == "linux2":
    PySpice.Spice.Simulation.CircuitSimulator.DEFAULT_SIMULATOR = 'ngspice-shared'
elif sys.platform == "win32":
    pass

# Let's setup a basic circuit [let's use the one on github]

circuit = Circuit('Tutorial 4.1')

# # Define the 1N4148PH (Signal Diode)
circuit.model('MyDiode', 'D', IS=4.352@u_nA, RS=0.6458@u_Ohm, BV=110@u_V, IBV=0.0001@u_V, N=1.906)

# # add components to the circuit
circuit.V('test', 1, circuit.gnd, 10@u_V)
circuit.Diode(1, 1, 2, model='MyDiode')
circuit.R(1, 2, circuit.gnd, 1@u_kOhm)  # @u_kΩ is a unit of kOhms

# print(circuit)

# Then we create the simulator
simulator = circuit.simulator(temperature=25, nominal_temperature=25)


# Here is the main difference, instead of doing .operating_point(), we do .dc()
# We put the Vinput = slice(start, stop, step) [yes it has to be Vinput, tried other names and did not work]
# FUTURE ME: DAMN WAIT, IT HAS TO BE THE SAME NAME AS THE ONE IN THE CIRCUIT.V(). 
analysis = simulator.dc(Vtest=slice(0, 10, 0.1))

# print(analysis["1"], np.array(analysis["1"]))

# Result
# 1 [ 0.   0.1  0.2  0.3  0.4  0.5  0.6  0.7  0.8  0.9  1.   1.1  1.2  1.3
#   1.4  1.5  1.6  1.7  1.8  1.9  2.   2.1  2.2  2.3  2.4  2.5  2.6  2.7
#   2.8  2.9  3.   3.1  3.2  3.3  3.4  3.5  3.6  3.7  3.8  3.9  4.   4.1
#   4.2  4.3  4.4  4.5  4.6  4.7  4.8  4.9  5.   5.1  5.2  5.3  5.4  5.5
#   5.6  5.7  5.8  5.9  6.   6.1  6.2  6.3  6.4  6.5  6.6  6.7  6.8  6.9
#   7.   7.1  7.2  7.3  7.4  7.5  7.6  7.7  7.8  7.9  8.   8.1  8.2  8.3
#   8.4  8.5  8.6  8.7  8.8  8.9  9.   9.1  9.2  9.3  9.4  9.5  9.6  9.7
#   9.8  9.9 10. ]


# We can obviously get the changes on the other voltages as the sweep is happening
# print(analysis["2"], np.array(analysis["2"]))


plt.figure(figsize=(10, 5))
plt.plot(analysis["1"], analysis["2"])
plt.xlabel("Input Voltage (node 1)")
plt.ylabel("Output Voltage (node 2)")
plt.show()



# Result
# 2 [-2.99742379e-22  2.91668294e-05  2.52780872e-04  1.91042282e-03
#   1.20063605e-02  4.61070566e-02  1.05524881e-01  1.79450407e-01
#   2.61065123e-01  3.46898841e-01  4.35767597e-01  5.26507592e-01
#   6.18574938e-01  7.11657948e-01  8.05533788e-01  9.00042562e-01
#   9.95067553e-01  1.09052111e+00  1.18633585e+00  1.28245890e+00
#   1.37884810e+00  1.47546926e+00  1.57229433e+00  1.66930003e+00
#   1.76646677e+00  1.86377801e+00  1.96121957e+00  2.05877927e+00
#   2.15644653e+00  2.25421215e+00  2.35206802e+00  2.45000701e+00
#   2.54802278e+00  2.64610971e+00  2.74426275e+00  2.84247738e+00
#   2.94074950e+00  3.03907544e+00  3.13745185e+00  3.23587567e+00
#   3.33434414e+00  3.43285470e+00  3.53140503e+00  3.62999298e+00
#   3.72861658e+00  3.82727399e+00  3.92596353e+00  4.02468363e+00
#   4.12343284e+00  4.22220980e+00  4.32101326e+00  4.41984203e+00
#   4.51869501e+00  4.61757117e+00  4.71646954e+00  4.81538922e+00
#   4.91432936e+00  5.01328914e+00  5.11226781e+00  5.21126466e+00
#   5.31027901e+00  5.40931023e+00  5.50835771e+00  5.60742087e+00
#   5.70649919e+00  5.80559213e+00  5.90469922e+00  6.00381998e+00
#   6.10295398e+00  6.20210079e+00  6.30126002e+00  6.40043127e+00
#   6.49961418e+00  6.59880841e+00  6.69801362e+00  6.79722948e+00
#   6.89645570e+00  6.99569199e+00  7.09493805e+00  7.19419363e+00
#   7.29345846e+00  7.39273229e+00  7.49201490e+00  7.59130604e+00
#   7.69060551e+00  7.78991308e+00  7.88922856e+00  7.98855175e+00
#   8.08788245e+00  8.18722050e+00  8.28656571e+00  8.38591791e+00
#   8.48527694e+00  8.58464264e+00  8.68401487e+00  8.78339347e+00
#   8.88277830e+00  8.98216922e+00  9.08156610e+00  9.18096882e+00
#   9.28037724e+00]


## EXTRA FROM GOOGLE. WILL BE USEFUL
## i tried looking up returning plots, and google search ai [which no one asked for] actually gave me a decent response
## We can use that to return a plot to the front-end directly. and just display it there

# import io
# import base64
# from flask import Flask, send_file
# from matplotlib.figure import Figure
# import numpy as np

# app = Flask(__name__)

# def create_plot():
#     # Generate the figure **without using pyplot**.
#     fig = Figure()
#     ax = fig.subplots()
#     xs = np.arange(0, 10, 0.1)
#     ys = np.sin(xs)
#     ax.plot(xs, ys)
#     ax.set_xlabel('X-axis Label')
#     ax.set_ylabel('Y-axis Label')
#     ax.set_title('Dynamic Plot')
#     return fig

# @app.route("/plot.png")
# def plot_png():
#     """Returns the plot as a PNG image file."""
#     fig = create_plot()
#     buf = io.BytesIO()
#     # Save the figure to the buffer
#     fig.savefig(buf, format="png")
#     # Rewind the buffer to the beginning
#     buf.seek(0)
#     # Return the image data
#     return send_file(buf, mimetype='image/png')

# @app.route("/plot_base64")
# def plot_base64():
#     """Returns the plot as a Base64 encoded string (useful for JSON/HTML embedding)."""
#     fig = create_plot()
#     buf = io.BytesIO()
#     fig.savefig(buf, format="png")
#     # Encode to base64
#     data = base64.b64encode(buf.getbuffer()).decode("ascii")
#     # Return as part of a JSON response or an HTML img tag
#     return f"<img src='data:image/png;base64,{data}'/>"

# if __name__ == "__main__":
#     app.run(debug=True)
