import datetime
import os
import csv
import logging
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

POSTGRES_USER = os.getenv('POSTGRES_USER')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD')
POSTGRES_DB = os.getenv('POSTGRES_DB')
POSTGRES_HOST = os.getenv('POSTGRES_HOST')

DATABASE_URI = f'postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}/{POSTGRES_DB}'
engine = create_engine(DATABASE_URI, isolation_level="AUTOCOMMIT")

def process_file(file_path):
    logger.info(f"Processing uploadfile {file_path}.")

    with engine.connect() as conn:
        if file_path.endswith('.gifts'):
            with open(file_path, 'r') as file:
                fieldnames = [
                    'record_type', 'internal_reference', 'source_account_number', 'amount', 'unknown',
                    'transaction_reference', 'particulars', 'code', 'reference', 'payee', 'date', 'optional',
                    'transaction_type', 'misc_field', 'destination_account_number'
                ]
                reader = csv.DictReader(file, fieldnames=fieldnames)
                for row in reader:
                    # logger.info(f"Processing row: {row}")
                    insert_query = text("""
                        INSERT INTO gifts_import (
                            "record_type", "internal_reference", "source_account_number", "amount", "unknown",
                            "transaction_reference", "particulars", "code", "reference", "payee", "date", "optional",
                            "transaction_type", "misc_field", "destination_account_number", "consecutive_duplicates"
                        ) VALUES (
                            :record_type, :internal_reference, :source_account_number, :amount, :unknown,
                            :transaction_reference, :particulars, :code, :reference, :payee, :date, :optional,
                            :transaction_type, :misc_field, :destination_account_number, 0
                        )
                    """)
                    # Convert the row values to appropriate types
                    try:
                        row['record_type'] = int(row['record_type']) if row['record_type'] else 0
                        row['internal_reference'] = int(row['internal_reference']) if row['internal_reference'] else 0
                        row['unknown'] = int(row['unknown']) if row['unknown'] else 0
                        row['transaction_reference'] = int(row['transaction_reference']) if row['transaction_reference'] else 0
                        row['misc_field'] = int(row['misc_field']) if row['misc_field'] else 0
                        row['amount'] = float(row['amount']) if row['amount'] else None
                        row['date'] = datetime.datetime.strptime(row['date'], '%d/%m/%y') if row['date'] else None
                    except ValueError as e:
                        logger.error(f"Data type conversion error: {e}")
                        logger.info(f"Processing row: {row}")
                        continue
                    
                    conn.execute(insert_query, {
                        'record_type': row['record_type'],
                        'internal_reference': row['internal_reference'],
                        'source_account_number': row['source_account_number'],
                        'amount': row['amount'] if row['amount'] is not None else 0,
                        'unknown': row['unknown'],
                        'transaction_reference': row['transaction_reference'],
                        'particulars': row['particulars'],
                        'code': row['code'],
                        'reference': row['reference'],
                        'payee': row['payee'],
                        'date': row['date'],
                        'optional': row['optional'],
                        'transaction_type': row['transaction_type'],
                        'misc_field': row['misc_field'],
                        'destination_account_number': row['destination_account_number']
                    })

    # Delete the file after processing
    try:
        os.remove(file_path)
        logger.info(f"Deleted file {file_path}.")
    except OSError as e:
        logger.error(f"Error deleting file {file_path}: {e}")


def process_files(file_paths):
    for file_path in file_paths:
        process_file(file_path)
    process_accounts()
    process_payees()
    process_transactions()
  
def process_accounts():
    logger.info(f"process accounts")
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO accounts ("account_number", "account_name", opening_balance)
            SELECT DISTINCT "source_account_number", payee, amount
            FROM gifts_import
            WHERE "record_type"=5 AND "source_account_number" NOT IN (
                SELECT "account_number" FROM accounts
            )
        """))
def process_payees():
    logger.info(f"process payees")
    with engine.connect() as conn:
        conn.execute(text("""
            WITH ranked_payees AS (
            SELECT 
                "destination_account_number", 
                payee,
                ROW_NUMBER() OVER (PARTITION BY "destination_account_number" ORDER BY date DESC) AS rn
            FROM gifts_import
            WHERE "record_type" = 3
            )
            INSERT INTO payees ("account_number", "account_name")
            SELECT 
            "destination_account_number", 
            payee
            FROM ranked_payees
            WHERE rn = 1
            AND "destination_account_number" NOT IN (
            SELECT "account_number" FROM payees
            )
        """))

        conn.execute(text("""
            DELETE FROM gifts_import WHERE "record_type" != 3
        """))

def process_transactions(): 
    logger.info(f"process transactions")
    with engine.connect() as conn:    
        ### Get all rows from gifts_import where record_type = 3
        result = conn.execute(text("""
            SELECT * FROM gifts_import WHERE "record_type" = 3
        """))
        rows = result.fetchall()
        headers = result.keys()
        process_count = 0
        batch_count = 200
        batch = 0
        consecutive_duplicates = 0
        for row in [dict(zip(headers, row)) for row in rows]:
            # Ensure row does not already exist in transactions table match on source_account_number, amount, date, payee, particulars, code, reference, transaction_type, destination_account_number
            if process_count == batch_count:
                logger.info(f"Processed {process_count} transactions")
                process_count = 0  + (batch * batch_count)
                batch += 1
            process_count += 1
            existing_transaction = conn.execute(text("""
                SELECT 1 FROM transactions
                WHERE "account_number" = :source_account_number
                AND "amount" = :amount
                AND "date" = :date
                AND "payee" = :payee
                AND "particulars" = :particulars
                AND "code" = :code
                AND "reference" = :reference
                AND "transaction_type" = :transaction_type
                AND "destination_account_number" = :destination_account_number
            """), {
                'source_account_number': row['source_account_number'],
                'amount': row['amount'],
                'date': row['date'],
                'payee': row['payee'],
                'particulars': row['particulars'],
                'code': row['code'],
                'reference': row['reference'],
                'transaction_type': row['transaction_type'],
                'destination_account_number': row['destination_account_number']
            }).fetchone()

            # If not, insert row into transactions table and delete from gifts_import
            if not existing_transaction:
                conn.execute(text("""
                    INSERT INTO transactions (
                        "account_number", "amount", "date", "payee", "particulars", "code", "reference", "transaction_type", "destination_account_number"
                    ) VALUES (
                        :source_account_number, :amount, :date, :payee, :particulars, :code, :reference, :transaction_type, :destination_account_number
                    )
                """), {
                    'source_account_number': row['source_account_number'],
                    'amount': row['amount'],
                    'date': row['date'],
                    'payee': row['payee'],
                    'particulars': row['particulars'],
                    'code': row['code'],
                    'reference': row['reference'],
                    'transaction_type': row['transaction_type'],
                    'destination_account_number': row['destination_account_number']
                })

                conn.execute(text("""
                    DELETE FROM gifts_import WHERE id = :id
                """), {'id': row['id']})
                consecutive_duplicates = 0
            else:
                logger.info(f"Transaction already exists or potential duplicate: {row}")
                consecutive_duplicates += 1
                #update consecutive_duplicates field for row and set to consecutive_dupliocates value in gifts_table
                conn.execute(text("""
                    UPDATE gifts_import SET consecutive_duplicates = :consecutive_duplicates WHERE id = :id
                """), {'consecutive_duplicates': consecutive_duplicates, 'id': row['id']})


def get_remaining_imports(): 
    logger.info(f"get remaining imports")
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT 
            gi.id, 
            a.account_name,
            gi.date, 
            gi.amount, 
            gi.payee, 
            gi.particulars, 
            gi.code, 
            gi.reference,
            gi.consecutive_duplicates
            FROM gifts_import gi
            LEFT JOIN accounts a ON gi.source_account_number = a.account_number
        """))
        return result.fetchall()

def get_account_summary_view():
    with engine.connect() as conn:
        result = conn.execute(text("""
        SELECT * FROM view_account_summary
        """))
        return result.fetchall()

def add_transaction(ids):
    logger.info(f"add transaction")
    with engine.connect() as conn:
        ids = [int(id) for id in ids]
        result = conn.execute(text("""
            SELECT * FROM gifts_import WHERE id = ANY(:ids)
        """), {'ids': ids})
        rows = result.fetchall()
        headers = result.keys()
        for row in [dict(zip(headers, row)) for row in rows]:
            conn.execute(text("""
                INSERT INTO transactions (
                    "account_number", "amount", "date", "payee", "particulars", "code", "reference", "transaction_type", "destination_account_number"
                ) VALUES (
                    :source_account_number, :amount, :date, :payee, :particulars, :code, :reference, :transaction_type, :destination_account_number
                )
            """), {
                'source_account_number': row['source_account_number'],
                'amount': row['amount'],
                'date': row['date'],
                'payee': row['payee'],
                'particulars': row['particulars'],
                'code': row['code'],
                'reference': row['reference'],
                'transaction_type': row['transaction_type'],
                'destination_account_number': row['destination_account_number']
            })

            conn.execute(text("""
                DELETE FROM gifts_import WHERE id = :id
            """), {'id': row['id']})

def delete_gifts_import(ids):
    logger.info(f"delete gifts import")
    with engine.connect() as conn:
        if ids == "*":
            conn.execute(text("""
                DELETE FROM gifts_import
            """))
        else:
            ids = [int(id) for id in ids]
            conn.execute(text("""
                DELETE FROM gifts_import WHERE id = ANY(:ids)
            """), {'ids': ids})