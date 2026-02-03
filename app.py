from flask import Flask, render_template, jsonify, request
import numpy as np

app = Flask(__name__)

# ====== APP STATE (simple version) ======
domains = None
scores = None


# ====== HELPERS ======
def sigmoid(x):
    return 1 / (1 + np.exp(-0.1 * x))


def get_graph_data():
    return {
        "theta": domains,
        "r": [100 * sigmoid(s) for s in scores]
    }


# ====== ROUTES ======
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/status")
def status():
    """Tell frontend whether domains are already initialized"""
    return jsonify({"initialized": domains is not None})


@app.route("/init", methods=["POST"])
def init():
    global domains, scores

    data = request.get_json()
    domains = data["domains"]
    scores = [0.0] * len(domains)

    return jsonify(get_graph_data())


@app.route("/get-data")
def get_data():
    if domains is None:
        return jsonify({"error": "Not initialized"}), 400
    return jsonify(get_graph_data())


@app.route("/update-score", methods=["POST"])
def update_score():
    global scores

    data = request.get_json()
    index = data["index"]
    change = data["change"]

    scores[index] += change

    return jsonify(get_graph_data())


if __name__ == "__main__":
    app.run(debug=True)
