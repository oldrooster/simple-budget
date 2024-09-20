import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from database import init_db, db  # Import from database.py
from data_processor import process_files, get_remaining_imports, delete_gifts_import, add_transaction, get_account_summary_view # Import from file_processor.py
load_dotenv() 

app = Flask(__name__, static_folder='static')
app.config['UPLOAD_FOLDER'] = 'import'
app.config['ALLOWED_EXTENSIONS'] = {'gifts'}
app.secret_key = os.getenv('SECRET_KEY', 'your_default_secret_key')  # Use the secret key from .env or a default value

# Initialize the database
init_db(app)

# Dummy users database
users = {
    'user': generate_password_hash('password')  # username: user, password: password
}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

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
        rows = get_account_summary_view()
        return render_template('accounts.html', rows=rows)
    return redirect(url_for('login'))

@app.route('/expenses')
def expenses():
    if 'username' in session:
        return render_template('expenses.html')
    return redirect(url_for('login'))

@app.route('/categories')
def categories():
    if 'username' in session:
        return render_template('categories.html')
    return redirect(url_for('login'))

@app.route('/rules')
def rules():
    if 'username' in session:
        return render_template('rules.html')
    return redirect(url_for('login'))

@app.route('/import')
def import_data():
    if 'username' in session:
        rows = get_remaining_imports()
        table_empty = len(rows) == 0
        return render_template('import.html', is_table_empty=table_empty, rows=rows)
    return redirect(url_for('login'))

@app.route('/api/expenses', methods=['POST'])
def add_expense():
    if 'username' in session:
        new_expense = request.json
        expenses.append(new_expense)
        return jsonify(new_expense), 201
    return jsonify({'error': 'Unauthorized'}), 403

@app.route('/api/import_data', methods=['POST'])
def upload_files():
    # Check if the post request has the file part
    if 'files' not in request.files:
        flash('No file part')
        return redirect(request.url)
    
    # Get the list of files from the request
    files = request.files.getlist('files')
    
    # Check if any files were selected
    if not files or all(file.filename == '' for file in files):
        flash('No selected files')
        return redirect(request.url)
    
    # Process each file in the list
    for file in files:
        # Check if the file is allowed based on its extension
        if file and allowed_file(file.filename):
            # Secure the filename and save the file to the upload folder
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            flash(f'File {filename} successfully uploaded')
        else:
            flash('Allowed file types are .gifts')
    
    # Get the list of files in the upload folder
    upload_folder = app.config['UPLOAD_FOLDER']
    uploaded_files = [os.path.join(upload_folder, f) for f in os.listdir(upload_folder) if os.path.isfile(os.path.join(upload_folder, f))]
    
    # Process the uploaded files
    process_files(uploaded_files)

    # Redirect to the index page after processing
    return redirect(url_for('import_data'))

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


@app.route('/api/add_duplicate_transaction', methods=['POST'])
def add_duplicate_transaction():
    selected_rows = request.form.getlist('selected_rows')
    add_transaction(selected_rows,)
    return redirect(url_for('import_data'))

@app.route('/api/delete_duplicate_transaction', methods=['POST'])
def delete_duplicate_transaction():
    selected_rows = request.form.getlist('selected_rows')
    delete_gifts_import(selected_rows,)
    return redirect(url_for('import_data'))

@app.route('/delete_all_duplicate_transactions', methods=['POST'])
def delete_all_duplicate_transactions():
    delete_gifts_import("*")
    return redirect(url_for('import_data'))

def currency_format(value):
    return "${:,.2f}".format(value)

app.jinja_env.filters['currency'] = currency_format

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
