from flask import Flask, render_template, jsonify, request
import numpy as np
import pandas as pd

app = Flask(__name__)

def sigmoid(x):
    return 1 / (1 + np.exp(-0.1 * x))

def get_graph_data():
    """Convert current scores to the format Plotly needs"""
    df = pd.DataFrame(dict(
        r=100 * sigmoid(basic_score),
        theta=[' sport ', ' intellect ', ' spirit ', ' will-power ', ' detox ']
    ))
    return df.to_dict('list')  # Convert to dict for JSON



# Global variable to store your scores (starts at 0 for all domains)
basic_score = np.array([0, 0, 0, 0, 0])

@app.route('/')
def index():
    """Main page - renders the HTML template"""
    return render_template('index.html')



@app.route('/get-data')
def get_data():
    """API endpoint that returns current graph data as JSON"""
    return jsonify(get_graph_data())



@app.route('/update-score', methods=['POST'])
def update_score():
    """API endpoint to update a score when button is clicked"""
    global basic_score
    
    # Get data from the button click
    data = request.get_json()
    domain_index = data['index']  # Which domain (0-4)
    change = data['change']        # +1 or -1
    
    # Update the score
    basic_score[domain_index] += change
    
    # Return updated graph data
    return jsonify(get_graph_data())

if __name__ == '__main__':
    app.run(debug=True)