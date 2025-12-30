from flask import Flask, request, session, jsonify, send_from_directory
import random, time

app = Flask(__name__, static_folder='static')
app.secret_key = 'your_secret_key_here'
allowed_time = 5

@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/generate', methods=['GET'])
def generate():
    n1 = random.randint(0, 99)
    n2 = random.randint(0, 99)
    n3 = random.randint(0, 99)
    n4 = random.randint(0, 99)
    s = n1 + n2 + n3 + n4
    session['total'] = s
    session['generated_at'] = time.time()
    return jsonify({'expression': f'{n1}+{n2}+{n3}+{n4}=?'})

@app.route('/verify', methods=['POST'])
def verify():
    d = request.get_json()
    u = d.get('user_input')
    c = session.get('total')
    generated_at = session.get('generated_at')
    if c is None or generated_at is None:
        return jsonify({'error': 'No puzzle generated or session expired'}), 400
    if time.time() - generated_at > allowed_time:
        return jsonify({'error': 'Puzzle expired, please generate a new one'}), 400
    if str(u) == str(c):
        try:
            with open('/root/flag.txt', 'r', encoding='utf-8') as f:
                flag = f.read().strip()
        except Exception:
            return jsonify({'error': 'Failed to read flag'}), 500
        return jsonify({'flag': flag})
    return jsonify({'error': 'Wrong answer'}), 400

@app.route('/<path:filename>')
def serve_static_file(filename):
    return send_from_directory('static', filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=True)
