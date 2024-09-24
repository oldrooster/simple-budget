import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from sqlalchemy import text
from database import init_db, db, Category, Subcategory, Rules, RuleActions, RuleConditions # Import from database.py
from data_processor import process_files, get_remaining_imports, delete_gifts_import, add_transaction, get_account_summary_view, logger# Import from file_processor.py

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

### Categories

@app.route('/categories')
def categories():
    if 'username' in session:
        categories = Category.query.all()
        return render_template('categories.html', categories=categories)
    return redirect(url_for('login'))

@app.route('/add_category', methods=['POST'])
def add_category():
    if 'username' in session:
        category_name = request.form['category_name']
        new_category = Category(name=category_name)
        db.session.add(new_category)
        db.session.commit()
        return redirect(url_for('categories'))
    return redirect(url_for('login'))

@app.route('/add_subcategory', methods=['POST'])
def add_subcategory():
    if 'username' in session:
        category_id = request.form['category_id']
        subcategory_name = request.form['subcategory_name']
        new_subcategory = Subcategory(name=subcategory_name, category_id=category_id)
        db.session.add(new_subcategory)
        db.session.commit()
        return redirect(url_for('categories'))
    return redirect(url_for('login'))

@app.route('/edit_category', methods=['POST'])
def edit_category():
    if 'username' in session:
        category_id = request.form['category_id']
        category_name = request.form['category_name']
        category = Category.query.get(category_id)
        category.name = category_name
        db.session.commit()
        return redirect(url_for('categories'))
    return redirect(url_for('login'))
@app.route('/edit_subcategory', methods=['POST'])
def edit_subcategory():
    if 'username' in session:
        subcategory_id = request.form['subcategory_id']
        subcategory_name = request.form['subcategory_name']
        subcategory = Subcategory.query.get(subcategory_id)
        subcategory.name = subcategory_name
        db.session.commit()
        return redirect(url_for('categories'))
    return redirect(url_for('login'))
@app.route('/delete_category/<int:category_id>')
def delete_category(category_id):
    if 'username' in session:
        category = Category.query.get(category_id)
        db.session.delete(category)
        db.session.commit()
        return redirect(url_for('categories'))
    return redirect(url_for('login'))

@app.route('/delete_subcategory/<int:subcategory_id>')
def delete_subcategory(subcategory_id):
    if 'username' in session:
        subcategory = Subcategory.query.get(subcategory_id)
        db.session.delete(subcategory)
        db.session.commit()
        return redirect(url_for('categories'))
    return redirect(url_for('login'))


### Rules

@app.route('/rules')
def rules():
    if 'username' in session:
        rules = Rules.query.all()
        categories = Category.query.all()
        subcategories = Subcategory.query.all()
        categories_dict = [{'id': c.id, 'name': c.name} for c in categories]
        subcategories_dict = [{'id': sc.id, 'name': sc.name, 'category_id': sc.category_id} for sc in subcategories]
        return render_template('rules.html', rules=rules, categories=categories_dict, subcategories=subcategories_dict)
    return redirect(url_for('login'))

@app.route('/api/rule/<int:rule_id>')
def get_rule(rule_id):
    if 'username' in session:
        rule = Rules.query.get(rule_id)
        if not rule:
            return jsonify({'error': 'Rule not found'}), 404

        rule_data = {
            'id': rule.id,
            'name': rule.name,
            'description': rule.description,
            'conditions': [{'field': c.field, 'operator': c.operator, 'value': c.value, 'and_condition': c.and_condition} for c in rule.conditions],
            'actions': [{'category_id': a.category_id, 'subcategory_id': a.subcategory_id} for a in rule.actions]
        }
        return jsonify(rule_data)
    return redirect(url_for('login'))

@app.route('/api/add_edit_rule', methods=['POST'])
def add_edit_rule():
    if 'username' in session:
        rule_id = request.form.get('rule_id')
        rule_name = request.form.get('rule_name')
        rule_description = request.form.get('rule_description')
        condition_fields = request.form.getlist('condition_field[]')
        condition_operators = request.form.getlist('condition_operator[]')
        condition_values = request.form.getlist('condition_value[]')
        condition_and_conditions = request.form.getlist('condition_and_condition[]')
        action_category_ids = request.form.getlist('action_category_id[]')
        action_subcategory_ids = request.form.getlist('action_subcategory_id[]')

        if not rule_name:
            flash('Rule name is required', 'error')
            return redirect(url_for('rules'))

        if rule_id:
            rule = Rules.query.get(rule_id)
            if not rule:
                flash('Rule not found', 'error')
                return redirect(url_for('rules'))
            rule.name = rule_name
            rule.description = rule_description
        else:
            rule = Rules(name=rule_name, description=rule_description)
            db.session.add(rule)

        # Clear existing conditions and actions
        RuleConditions.query.filter_by(rule_id=rule.id).delete()
        RuleActions.query.filter_by(rule_id=rule.id).delete()

        # Add new conditions
        #for field, operator, value, and_condition in zip(condition_fields, condition_operators, condition_values, condition_and_conditions):
        for field, operator, value, and_condition in zip(condition_fields, condition_operators, condition_values, condition_and_conditions):
            condition = RuleConditions(
                rule_id=rule.id,
                field=field,
                operator=operator,
                value=value,
                and_condition=True if and_condition.lower() == 'true' else False
            )
            
            db.session.add(condition)

        # Add new actions
        for category_id, subcategory_id in zip(action_category_ids, action_subcategory_ids):
            if subcategory_id == '':
                subcategory_id = None
            action = RuleActions(rule_id=rule.id, category_id=category_id, subcategory_id=subcategory_id)
            db.session.add(action)

        db.session.commit()
        flash('Rule saved successfully', 'success')
        return redirect(url_for('rules'))
    return redirect(url_for('login'))

@app.route('/delete_rule/<int:rule_id>')
def delete_rule(rule_id):
    if 'username' in session:
        rule = Rules.query.get(rule_id)
        if rule:
            db.session.delete(rule)
            db.session.commit()
            flash('Rule deleted successfully', 'success')
        else:
            flash('Rule not found', 'error')
        return redirect(url_for('rules'))
    return redirect(url_for('login'))

@app.route('/api/get_associated_transactions', methods=['POST'])
def get_associated_transactions():
    if 'username' in session:
        conditions = request.json.get('conditions', [])
        if not conditions:
            return jsonify({'error': 'No conditions provided'}), 400

        query = """
        SELECT t.*, a.account_name as account_name 
        FROM transactions t
        JOIN accounts a ON t.account_number = a.account_number
        WHERE 
        """
        query_conditions = []
        query_params = {}

        for i, condition in enumerate(conditions):
            field = condition.get('field')
            operator = condition.get('operator')
            value = condition.get('value')
            and_condition = condition.get('and_condition')

            if operator.lower() not in ['=', '!=', '<', '<=', '>', '>=', 'like']:
                return jsonify({'error': f'Invalid operator: {operator}'}), 400

            if operator == 'like':
                value = f"%{value}%"  # Add wildcards for LIKE operator

            param_key = f"value_{i}"
            if i == 0:
                query_conditions.append(f"t.{field} {operator} :{param_key}")
            else:
                conjunction = 'AND' if and_condition.lower() == 'true' else 'OR'
                query_conditions.append(f"{conjunction} t.{field} {operator} :{param_key}")

            query_params[param_key] = value

        query += ' '.join(query_conditions)
        # Log the full SQL query text with parameters
        logger.info(f"Query: {query}, Params: {query_params}")
        
        result = db.session.execute(text(query), query_params).fetchmany(100)
        transactions = [row._asdict() for row in result]

        return jsonify(transactions)
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

    




