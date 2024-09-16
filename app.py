from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, static_folder='static')
app.secret_key = 'your_secret_key'  # Change this to a random secret key for session security

# Example data
expenses = [
    {"id": 1, "date": "2024-01-01", "description": "Groceries", "amount": 50.00},
    {"id": 2, "date": "2024-01-02", "description": "Rent", "amount": 1200.00}
]

# Dummy users database
users = {
    'user': generate_password_hash('password')  # username: user, password: password
}

@app.route('/')
def index():
    if 'username' in session:
        return render_template('index.html')
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user_password_hash = users.get(username)

        if user_password_hash and check_password_hash(user_password_hash, password):
            session['username'] = username
            return redirect(url_for('index'))
        else:
            return "Invalid username or password", 403

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/accounts')
def accounts():
    if 'username' in session:
        return render_template('accounts.html')
    return redirect(url_for('login'))

@app.route('/expenses')
def expenses():
    if 'username' in session:
        return render_template('expenses.html')
    return redirect(url_for('login'))

@app.route('/import')
def import_data():
    if 'username' in session:
        return render_template('import.html')
    return redirect(url_for('login'))

@app.route('/api/expenses', methods=['GET'])
def get_expenses():
    if 'username' in session:
        return jsonify(expenses)
    return jsonify({'error': 'Unauthorized'}), 403

@app.route('/api/expenses', methods=['POST'])
def add_expense():
    if 'username' in session:
        new_expense = request.json
        expenses.append(new_expense)
        return jsonify(new_expense), 201
    return jsonify({'error': 'Unauthorized'}), 403

@app.route('/api/expenses/<int:expense_id>', methods=['PUT'])
def update_expense(expense_id):
    if 'username' in session:
        updated_expense = request.json
        for expense in expenses:
            if expense['id'] == expense_id:
                expense.update(updated_expense)
                return jsonify(expense)
        return jsonify({'error': 'Expense not found'}), 404
    return jsonify({'error': 'Unauthorized'}), 403

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
