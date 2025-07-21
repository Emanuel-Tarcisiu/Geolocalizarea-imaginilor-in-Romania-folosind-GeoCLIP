from flask import Flask, request, jsonify
from flask_cors import CORS
from model_loader import load_model, predict_image

app = Flask(__name__)
CORS(app)
WEIGHTS_PATH = "_geoclip/model/weights"
MODEL = load_model(WEIGHTS_PATH)

@app.route('/predict', methods=['POST'])
def predict():
    if 'image' not in request.files:
        return jsonify({'error': 'No image provided'}), 400

    img = request.files['image']
    predictions = predict_image(MODEL, img)
    return jsonify({'predictions': predictions})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
