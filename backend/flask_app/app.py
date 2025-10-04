# Backend-Startdatei für GeoMapPolygome
# Beispiel: Flask-Server für spätere GeoJSON-Uploads, API etc.
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
app = Flask(__name__)
CORS(app)

@app.route('/')
def index():
    return "Backend läuft!"

# Beispiel-Endpunkt für GeoJSON-Upload
@app.route('/upload', methods=['POST'])
def upload_geojson():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    geojson_data = file.read().decode('utf-8')
    # Hier könntest du die Datei speichern oder weiterverarbeiten
    return jsonify({'message': 'GeoJSON empfangen!', 'data': geojson_data})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
