from flask import Flask
from flask_cors import CORS
from routes.groq import groq_bp
from routes.rag import rag_bp

app = Flask(__name__)
CORS(app) 
app.register_blueprint(groq_bp, url_prefix='/groq')
app.register_blueprint(rag_bp, url_prefix='/rag')


@app.route('/health')
def home():
    return "OK", 200

if __name__ == '__main__':
    app.run(debug=True)