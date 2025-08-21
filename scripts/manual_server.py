from datetime import datetime
from flask import Flask, request, jsonify

from tas_parl_monitor import run_monitor

app = Flask(__name__)

@app.post('/run')
def run():
    data = request.get_json(force=True)
    date_str = data.get('date')
    keyword = data.get('keyword')
    if not date_str or not keyword:
        return jsonify({'message': 'date and keyword required'}), 400
    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'message': 'invalid date format'}), 400
    run_monitor(target_date, [keyword])
    return jsonify({'message': 'run started'}), 200

if __name__ == '__main__':
    app.run(debug=True)
