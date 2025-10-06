from flask import Flask
from routes.groq import groq_bp

app = Flask(__name__)
app.register_blueprint(groq_bp, url_prefix='/groq')


@app.route('/health')
def home():
    return "OK", 200

if __name__ == '__main__':
    app.run(debug=True)