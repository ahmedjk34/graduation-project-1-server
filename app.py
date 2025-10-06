from flask import Flask
from flask_cors import CORS
from routes.groq import groq_bp

app = Flask(__name__)
CORS(app) 
app.register_blueprint(groq_bp, url_prefix='/groq')


@app.route('/health')
def home():
    return "OK", 200

if __name__ == '__main__':
    app.run(debug=True)