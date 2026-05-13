from flask import Flask, jsonify, send_from_directory
import json, os

app = Flask(__name__)
ESTADO = os.path.expanduser("~/.don_estado.json")
WEB = os.path.join(os.path.dirname(__file__), 'web')

@app.route('/')
def index():
    return send_from_directory(WEB, 'don_pantalla.html')

@app.route('/setup')
def setup():
    return send_from_directory(WEB, 'don_setup.html')

@app.route('/estado')
def estado():
    try:
        with open(ESTADO) as f:
            return jsonify(json.load(f))
    except:
        return jsonify({"hablando": False, "bateria": 100})

@app.route('/guardar-config', methods=['POST'])
def guardar_config():
    from flask import request
    config = request.json
    with open(os.path.expanduser("~/.don_config.json"), 'w') as f:
        json.dump(config, f)
    return jsonify({"ok": True})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)