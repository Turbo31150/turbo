import os
import json
import logging
from flask import Flask, render_template, request, jsonify
from flask_sockets import Sockets
import pvporcupine

app = Flask(__name__, static_folder='static', template_folder='static')
sockets = Sockets(app)
logging.basicConfig(level=logging.INFO)

# Simulation du backend Porcupine si WASM n'est pas utilisé directement
PORCUPINE_KEY = os.environ.get("PORCUPINE_ACCESS_KEY", "dummy_key")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health')
def health():
    return jsonify({"status": "ok", "service": "voice-wake-porcupine"})

@sockets.route('/audio')
def audio_socket(ws):
    logging.info("WebSocket audio connecté")
    try:
        # Initialisation Porcupine Python (optionnel si fait en WebAssembly côté JS)
        # porcupine = pvporcupine.create(access_key=PORCUPINE_KEY, keywords=['jarvis'])
        while not ws.closed:
            message = ws.receive()
            if message:
                # Logique de traitement de l'audio raw ou des événements du JS
                if isinstance(message, str):
                    data = json.loads(message)
                    if data.get('event') == 'wake_word_detected':
                        logging.info("WAKE WORD DETECTED: Jarvis!")
                        ws.send(json.dumps({"status": "acknowledged", "action": "trigger_mcp"}))
    except Exception as e:
        logging.error(f"Erreur WebSocket : {e}")
    finally:
        logging.info("WebSocket déconnecté")

if __name__ == '__main__':
    from gevent import pywsgi
    from geventwebsocket.handler import WebSocketHandler
    server = pywsgi.WSGIServer(('127.0.0.1', 8002), app, handler_class=WebSocketHandler)
    print("Voice Wake Server running on port 8002")
    server.serve_forever()