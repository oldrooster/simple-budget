import os
import logging
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy_utils import database_exists, create_database
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database configuration
POSTGRES_ROOT_USER = os.getenv('POSTGRES_ROOT_USER')
POSTGRES_ROOT_PASSWORD = os.getenv('POSTGRES_ROOT_PASSWORD')
POSTGRES_USER = os.getenv('POSTGRES_USER')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD')
POSTGRES_DB = os.getenv('POSTGRES_DB')
POSTGRES_HOST = os.getenv('POSTGRES_HOST')

DATABASE_URI = f'postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}/{POSTGRES_DB}'
ROOT_DATABASE_URI = f'postgresql://{POSTGRES_ROOT_USER}:{POSTGRES_ROOT_PASSWORD}@{POSTGRES_HOST}/postgres'

db = SQLAlchemy()

def init_db(app):
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)

    createDBorUser = False

    # Check postgres database exists and has correct permissions using non-root user
    engine = create_engine(DATABASE_URI)
    try:
        with engine.connect() as conn:
            # Check if the database exists
            if not database_exists(DATABASE_URI):
                logger.error(f"Database {POSTGRES_DB} does not exist.")
                createDBorUser = True
            # Check if the user has all privileges on the database
            privileges_query = text(f"""
                SELECT has_database_privilege('{POSTGRES_USER}', '{POSTGRES_DB}', 'CREATE') AS create_priv,
                   has_database_privilege('{POSTGRES_USER}', '{POSTGRES_DB}', 'CONNECT') AS connect_priv,
                   has_database_privilege('{POSTGRES_USER}', '{POSTGRES_DB}', 'TEMPORARY') AS temp_priv
            """)
            result = conn.execute(privileges_query).fetchone()
            
            if not all(result):
                logger.warning(f"User {POSTGRES_USER} does not have all privileges on database {POSTGRES_DB}.")
                createDBorUser = True

    except OperationalError as e:
        if 'FATAL:  database' in str(e) and 'does not exist' in str(e):
            logger.warning(f"Database {POSTGRES_DB} does not exist.")
            createDBorUser = True
        else:
            raise
    
    if createDBorUser:
        # Create the database and user if they don't exist
        engine = create_engine(ROOT_DATABASE_URI)
        with engine.connect() as conn:
            conn.execution_options(isolation_level="AUTOCOMMIT")
            user_exists_query = text(f"SELECT rolcanlogin FROM pg_roles WHERE rolname='{POSTGRES_USER}'")
            result = conn.execute(user_exists_query).fetchone()
            if not result:
                # Create the user if it does not exist
                create_user_query = text(f"CREATE ROLE {POSTGRES_USER} WITH LOGIN PASSWORD '{POSTGRES_PASSWORD}';")
                conn.execute(create_user_query)
                logger.info(f"User {POSTGRES_USER} created successfully.")
                logger.info(create_user_query)
            else:
                logger.info(f"User {POSTGRES_USER} already exists.")
            
            # Verify user creation
            result = conn.execute(user_exists_query).fetchone()
            if result:
                logger.info(f"User {POSTGRES_USER} verified in the database.")
                if result[0]:
                    logger.info(f"User {POSTGRES_USER} can login.")
                else:
                    create_login_query = text(f"ALTER ROLE {POSTGRES_USER} WITH LOGIN;")
                    conn.execute(create_login_query)
                    logger.info(f"User {POSTGRES_USER} can now login.")
            else:
                logger.info(f"User {POSTGRES_USER} not found.")
                
        # Create the database
        with engine.connect() as conn:
            conn.execution_options(isolation_level="AUTOCOMMIT")
            # Check if the database exists before creating it
            db_exists_query = text(f"SELECT 1 FROM pg_database WHERE datname='{POSTGRES_DB}'")
            result = conn.execute(db_exists_query).fetchone()
            if not result:
                conn.execute(text(f"CREATE DATABASE {POSTGRES_DB} OWNER {POSTGRES_USER}"))
                logger.info(f"Database {POSTGRES_DB} created successfully.")
            else:
                logger.info(f"Database {POSTGRES_DB} already exists.")
            # Check if the user has all privileges on the database
            privileges_query = text(f"""
                SELECT has_database_privilege('{POSTGRES_USER}', '{POSTGRES_DB}', 'CREATE') AS create_priv,
                has_database_privilege('{POSTGRES_USER}', '{POSTGRES_DB}', 'CONNECT') AS connect_priv,
                has_database_privilege('{POSTGRES_USER}', '{POSTGRES_DB}', 'TEMPORARY') AS temp_priv
            """)
            result = conn.execute(privileges_query).fetchone()
            
            if not all(result):
                # Grant all privileges if any are missing
                conn.execute(text(f"GRANT ALL PRIVILEGES ON DATABASE {POSTGRES_DB} TO {POSTGRES_USER}"))
                logger.info(f"Granted all privileges on database {POSTGRES_DB} to {POSTGRES_USER}.")
            else:
                logger.info(f"User {POSTGRES_USER} already has all privileges on database {POSTGRES_DB}.")

    # Create the database tables
    with app.app_context():
        if not database_exists(DATABASE_URI):
            create_database(DATABASE_URI)
        db.create_all()

    with engine.connect() as conn:
        conn.execution_options(isolation_level="AUTOCOMMIT")
        # Create the view for the account summary
        view_query = """
        CREATE OR REPLACE VIEW view_account_summary AS
        SELECT 
            a.id,
            a.account_name,
            a.account_number,
            a.opening_balance,
            round((a.opening_balance + COALESCE(SUM(t.amount), 0))::numeric,2) AS balance
        FROM 
            accounts a
        LEFT JOIN 
            transactions t ON a.account_number = t.account_number
        GROUP BY 
            a.id, a.account_name, a.account_number, a.opening_balance
        """
        conn.execute(text(view_query))

# Define your models here
class Transactions(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    account_number = db.Column(db.String(32), nullable=False) 
    date = db.Column(db.Date, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    particulars = db.Column(db.String(32), nullable=True)         # Column 7
    code = db.Column(db.String(32), nullable=True)                # Column 8
    reference = db.Column(db.String(32), nullable=True)           # Column 9
    payee = db.Column(db.String(32), nullable=True)                 # Column 10
    transaction_type = db.Column(db.String(10), nullable=True)     
    destination_account_number = db.Column(db.String(32), nullable=True) 
#    category = db.Column(db.String(100), nullable=True)  
#    sub_category = db.Column(db.String(100), nullable=True)  

class Accounts(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    account_number = db.Column(db.String(32), nullable=False, unique=True)
    account_name = db.Column(db.String(32), nullable=False)
    opening_balance = db.Column(db.Float, nullable=False, default=0.0)

class Payees(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    account_number = db.Column(db.String(32), nullable=False, unique=True)
    account_name = db.Column(db.String(32), nullable=False)

class GiftsImport(db.Model):
    id = db.Column(db.Integer, primary_key=True)                    
    record_type = db.Column(db.Integer, nullable=False)              # Column 1
    internal_reference = db.Column(db.Integer, nullable=False)       # Column 2
    source_account_number = db.Column(db.String(32), nullable=False)       # Column 3
    amount = db.Column(db.Float, nullable=False)                    # Column 4
    unknown = db.Column(db.Integer, nullable=True)               # Column 5
    transaction_reference = db.Column(db.Integer, nullable=True)    # Column 6
    particulars = db.Column(db.String(32), nullable=True)         # Column 7
    code = db.Column(db.String(32), nullable=True)                # Column 8
    reference = db.Column(db.String(32), nullable=True)           # Column 9
    payee = db.Column(db.String(32), nullable=True)                 # Column 10
    date = db.Column(db.Date, nullable=True)                       # Column 11
    optional = db.Column(db.String(20), nullable=True)            # Column 12
    transaction_type = db.Column(db.String(10), nullable=True)     # Column 13
    misc_field = db.Column(db.Integer, nullable=True)                # Column 14
    destination_account_number = db.Column(db.String(32), nullable=True) # Column 15
    consecutive_duplicates = db.Column(db.Integer, nullable=False, default=0) # No. of consecutive duplicates

class Categories(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(32), nullable=False, unique=True)
    subcategory = db.Column(db.String(32), nullable=False)

class TransactionsCategories(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)

# Rules table for setting up rules that have one or many rule conditions and one or mant rule actions
class Rules(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), nullable=False)
    description = db.Column(db.String(32), nullable=True)

# Rule Actions table for what category and sub category to apply  when one or more rules are matched includes associate Rules ID
class RuleActions(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rule_id = db.Column(db.Integer, db.ForeignKey('rules.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)

# Rule Condtions for given rule. includes specific field from transaction table to match on
class RuleConditions(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rule_id = db.Column(db.Integer, db.ForeignKey('rules.id'), nullable=False)
    field = db.Column(db.String(32), nullable=False)
    operator = db.Column(db.String(32), nullable=False)
    value = db.Column(db.String(32), nullable=False)

# class PayeesCategories(db.Model):
#     id = db.Column(db.Integer, primary_key=True)
#     payee_id = db.Column(db.Integer, db.ForeignKey('payees.id'), nullable=False)
#     category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)

# class TransactionsPayees(db.Model):
#     id = db.Column(db.Integer, primary_key=True)
#     transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id'), nullable=False)
#     payee_id = db.Column(db.Integer, db.ForeignKey('payees.id'), nullable=False)

# class TransactionsAccounts(db.Model):
#     id = db.Column(db.Integer, primary_key=True)
#     transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id'), nullable=False)
#     account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)