# If you see ModuleNotFoundError: No module named 'pytz', run: pip install pytz

import json
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS, cross_origin
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import date, datetime, timedelta
from invoice_utils import generate_invoice_pdf
from email_utils import send_invoice_email, send_unique_number_email, send_contact_email, send_simple_email
from dotenv import load_dotenv
import secrets
import psycopg2
from config import DatabaseConfig, get_db_conn, EmailConfig
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
import smtplib
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from cryptography.fernet import Fernet
import re
from extract_fields import extract_fields
import pytz
from werkzeug.middleware.proxy_fix import ProxyFix
from dateutil import parser

load_dotenv()

app = Flask(__name__)

# Add ProxyFix middleware to handle X-Forwarded-For headers
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

# CORS configuration for both development and production
allowed_origins = [
    'http://localhost:3000',  # Development
    'https://terryraylogicticsco.xyz',
    'https://www.terryraylogicticsco.xyz',
]

# Add environment variable for additional origins
env_origins = os.getenv('ALLOWED_ORIGINS', '').split(',')
if env_origins and env_origins[0]:
    allowed_origins.extend([origin.strip() for origin in env_origins])

CORS(app, origins=allowed_origins, supports_credentials=True)

@app.route('/api/ping')
def ping():
    return {"message": "pong"}, 200


app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'change-this-in-production')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'pdf'}
jwt = JWTManager(app)

# Initialize Rate Limiter with conditional limits based on environment
is_development = os.getenv('FLASK_ENV') == 'development' or os.getenv('FLASK_DEBUG') == 'True'

if is_development:
    # More lenient limits for development
    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=["1000 per day", "100 per hour"]
    )
else:
    # Stricter limits for production
    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=["200 per day", "50 per hour"]
    )

# Custom error handler for rate limiting
@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({
        'error': 'Too many requests. Please wait before trying again.',
        'retry_after': getattr(e, 'retry_after', 3600)  # Default to 1 hour
    }), 429

# Initialize Encryption
# Use a persistent key from environment variables, or generate one if not exists
encryption_key = os.getenv('ENCRYPTION_KEY')
if not encryption_key:
    # Generate a new key and save it (you should save this to your .env file)
    encryption_key = Fernet.generate_key()
    print(f"Generated new encryption key: {encryption_key.decode()}")
    print("Please add this to your .env file as ENCRYPTION_KEY=<key>")
else:
    # Convert string key to bytes if needed
    if isinstance(encryption_key, str):
        encryption_key = encryption_key.encode()

fernet = Fernet(encryption_key)

# Security Helper Functions
def validate_password(password):
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one number"
    if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        return False, "Password must contain at least one special character"
    return True, "Password is valid"

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def encrypt_sensitive_data(data):
    if not data:
        return data
    try:
        if isinstance(data, str):
            return fernet.encrypt(data.encode()).decode()
        return data
    except Exception as e:
        print(f"Encryption error for data: {data[:50]}... Error: {str(e)}")
        # If encryption fails, return the original data
        return data

def decrypt_sensitive_data(encrypted_data):
    if not encrypted_data:
        return encrypted_data
    try:
        # Check if the data looks like it's encrypted (starts with gAAAAA)
        if isinstance(encrypted_data, str) and encrypted_data.startswith('gAAAAA'):
            try:
                return fernet.decrypt(encrypted_data.encode()).decode()
            except Exception as decrypt_error:
                print(f"Decryption failed for data: {encrypted_data[:50]}... Error: {str(decrypt_error)}")
                # If decryption fails, it might be encrypted with a different key
                # Return the original data and log the issue
                return encrypted_data
        else:
            # Data is not encrypted, return as is
            return encrypted_data
    except Exception as e:
        print(f"Decryption error for data: {encrypted_data[:50]}... Error: {str(e)}")
        # If decryption fails, return the original data (assuming it's not encrypted)
        return encrypted_data

def log_sensitive_operation(user_id, operation, details):
    # Temporarily disabled until audit_logs table is created
    # conn = get_db_conn()
    # cur = conn.cursor()
    # try:
    #     cur.execute(
    #         'INSERT INTO audit_logs (user_id, operation, details, timestamp) VALUES (%s, %s, %s, NOW())',
    #         (user_id, operation, details)
    #     )
    #     conn.commit()
    # except Exception as e:
    #     print(f"Error logging operation: {str(e)}")
    # finally:
    #     cur.close()
    #     conn.close()
    pass

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Using get_db_conn from config.py

@app.route('/', methods=['GET'])
@limiter.exempt
def root():
    """Root endpoint with API information"""
    return jsonify({
        'message': 'Terry Ray Logistics Shipping System API',
        'version': '1.0.0',
        'status': 'running',
        'endpoints': {
            'health': '/health',
            'api_base': '/api',
            'documentation': 'Check the API endpoints for more information'
        }
    }), 200

@app.route('/health', methods=['GET'])
@limiter.exempt
def health_check():
    """Health check endpoint for monitoring"""
    try:
        # Test database connection
        conn = get_db_conn()
        if conn:
            conn.close()
            return jsonify({
                'status': 'healthy',
                'database': 'connected',
                'timestamp': datetime.now(pytz.timezone('Asia/Hong_Kong')).isoformat()
            }), 200
        else:
            return jsonify({
                'status': 'unhealthy',
                'database': 'disconnected',
                'timestamp': datetime.now(pytz.timezone('Asia/Hong_Kong')).isoformat()
            }), 503
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now(pytz.timezone('Asia/Hong_Kong')).isoformat()
        }), 503

@app.route('/api/register', methods=['POST'])
@limiter.limit("50 per hour" if is_development else "20 per hour")  # More lenient in development
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    role = data.get('role')
    customer_name = data.get('customer_name')
    customer_email = data.get('customer_email')
    customer_phone = data.get('customer_phone')
    if not all([username, password, role, customer_name, customer_email, customer_phone]):
        return jsonify({'error': 'Missing fields'}), 400
    
    # Validate password
    is_valid, message = validate_password(password)
    if not is_valid:
        return jsonify({'error': message}), 400
    
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        # Encrypt sensitive data
        encrypted_email = encrypt_sensitive_data(customer_email)
        encrypted_phone = encrypt_sensitive_data(customer_phone)
        
        cur.execute(
            "INSERT INTO users (username, password_hash, role, customer_name, customer_email, customer_phone) VALUES (%s, %s, %s, %s, %s, %s)",
            (username, generate_password_hash(password), role, customer_name, encrypted_email, encrypted_phone)
        )
        conn.commit()
        log_sensitive_operation(None, 'register', f'New user registered: {username}')
        cur.close()
        conn.close()
        return jsonify({'message': 'Registration submitted, waiting for approval.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/login', methods=['POST'])
@limiter.limit("5 per minute")
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, password_hash, role, approved, customer_name, customer_email, customer_phone FROM users WHERE username=%s", (username,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    if not user:
        return jsonify({'error': 'User not found'}), 401
    user_id, password_hash, role, approved, customer_name, customer_email, customer_phone = user
    if not approved:
        return jsonify({'error': 'User not approved yet'}), 403
    if not check_password_hash(password_hash, password):
        return jsonify({'error': 'Incorrect password'}), 401
    access_token = create_access_token(identity=json.dumps({'id': user_id, 'role': role, 'username': username}))
    log_sensitive_operation(user_id, 'login', 'User logged in successfully')
    return jsonify({
        "access_token": access_token,
        "customer_name": customer_name,
        "customer_email": customer_email,
        "customer_phone": customer_phone,
        'role': role,
        'username': username
    }), 200

@app.route('/api/approve_user/<int:user_id>', methods=['POST'])
@jwt_required()
def approve_user(user_id):
    user = json.loads(get_jwt_identity())
    if user['role'] not in ['staff', 'admin']:
        return jsonify({'error': 'Unauthorized'}), 403
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET approved=TRUE WHERE id=%s", (user_id,))
    # Fetch user email and name
    cur.execute("SELECT customer_email, customer_name FROM users WHERE id=%s", (user_id,))
    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    if row:
        customer_email, customer_name = row
        # Decrypt email for sending
        decrypted_email = decrypt_sensitive_data(customer_email) if customer_email else ''
        if decrypted_email:
            # Send confirmation email
            subject = "Your registration has been approved"
            body = f"Dear {customer_name},\n\nYour registration has been approved. You can now log in and use our services.\n\nThank you!"
            send_simple_email(decrypted_email, subject, body)
    return jsonify({'message': 'User approved'})

@app.route('/api/unapproved_users', methods=['GET'])
@jwt_required()
def get_unapproved_users():
    user = json.loads(get_jwt_identity())
    if user['role'] not in ['staff', 'admin']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute('SELECT id, username, customer_name, customer_email, customer_phone, role FROM users WHERE approved = FALSE')
    users = []
    for row in cur.fetchall():
        # Decrypt email and phone
        decrypted_email = decrypt_sensitive_data(row[3]) if row[3] is not None else ''
        decrypted_phone = decrypt_sensitive_data(row[4]) if row[4] is not None else ''
        users.append({
            'id': row[0],
            'username': row[1],
            'customer_name': row[2],
            'customer_email': decrypted_email,
            'customer_phone': decrypted_phone,
            'role': row[5]
        })
    cur.close()
    conn.close()
    return jsonify(users)

@app.route('/api/stats/files_by_date')
@jwt_required()
def files_by_date():
    user = json.loads(get_jwt_identity())
    if user['role'] != 'staff':
        return jsonify({'error': 'Unauthorized'}), 403
    query_date = request.args.get('date')
    conn = get_db_conn()
    cur = conn.cursor()
    # Use timezone-aware date range
    start_date, end_date = get_hk_date_range(query_date)
    cur.execute("SELECT COUNT(*) FROM bill_of_lading WHERE created_at >= %s AND created_at < %s", (start_date, end_date))
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return jsonify({'files_created': count})

@app.route('/api/stats/completed_today')
@jwt_required()
def completed_today():
    user = json.loads(get_jwt_identity())
    if user['role'] != 'staff':
        return jsonify({'error': 'Unauthorized'}), 403
    # Use timezone-aware date
    hk_now = datetime.now(pytz.timezone('Asia/Hong_Kong'))
    today = hk_now.date().isoformat()
    conn = get_db_conn()
    cur = conn.cursor()
    # Use timezone-aware date range
    start_date, end_date = get_hk_date_range(today)
    cur.execute("SELECT COUNT(*) FROM bill_of_lading WHERE status='Completed' AND completed_at >= %s AND completed_at < %s", (start_date, end_date))
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return jsonify({'completed_today': count})

@app.route('/api/stats/payments_by_date')
@jwt_required()
def payments_by_date():
    user = json.loads(get_jwt_identity())
    if user['role'] != 'staff':
        return jsonify({'error': 'Unauthorized'}), 403
    query_date = request.args.get('date')
    conn = get_db_conn()
    cur = conn.cursor()
    # Use timezone-aware date range
    start_date, end_date = get_hk_date_range(query_date)
    cur.execute("SELECT SUM(service_fee) FROM bill_of_lading WHERE created_at >= %s AND created_at < %s", (start_date, end_date))
    total = cur.fetchone()[0] or 0
    cur.close()
    conn.close()
    return jsonify({'payments_received': float(total)})

@app.route('/api/stats/bills_by_date')
@jwt_required()
def bills_by_date():
    user = json.loads(get_jwt_identity())
    if user['role'] != 'staff':
        return jsonify({'error': 'Unauthorized'}), 403
    query_date = request.args.get('date')
    conn = get_db_conn()
    cur = conn.cursor()
    # Use timezone-aware date range
    start_date, end_date = get_hk_date_range(query_date)
    cur.execute("""
        SELECT 
            COUNT(*) as total_entries,
            COALESCE(SUM(ctn_fee), 0) as total_ctn_fee,
            COALESCE(SUM(service_fee), 0) as total_service_fee
        FROM bill_of_lading 
        WHERE created_at >= %s AND created_at < %s
    """, (start_date, end_date))
    summary = cur.fetchone()
    cur.execute("""
        SELECT 
            id, customer_name, customer_email, 
            ctn_fee, service_fee, 
            COALESCE(ctn_fee + service_fee, 0) as total,
            created_at
        FROM bill_of_lading 
        WHERE created_at >= %s AND created_at < %s
        ORDER BY created_at DESC
    """, (start_date, end_date))
    entries = [dict(zip([desc[0] for desc in cur.description], row)) for row in cur.fetchall()]
    cur.close()
    conn.close()
    return jsonify({
        'summary': {
            'total_entries': summary[0],
            'total_ctn_fee': float(summary[1]),
            'total_service_fee': float(summary[2])
        },
        'entries': entries
    })

@app.route('/api/upload', methods=['POST'])
@jwt_required()
def upload():
    user = json.loads(get_jwt_identity())
    username = user['username']

    try:
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        bill_pdfs = request.files.getlist('bill_pdf')
        invoice_pdf = request.files.get('invoice_pdf')
        packing_pdf = request.files.get('packing_pdf')

        if not name:
            return jsonify({'error': 'Name is required'}), 400
        if not email:
            return jsonify({'error': 'Email is required'}), 400
        if not phone:
            return jsonify({'error': 'Phone is required'}), 400
        if not bill_pdfs and not invoice_pdf and not packing_pdf:
            return jsonify({'error': 'At least one PDF file is required'}), 400

        def save_file_with_timestamp(file, label):
            if not file:
                return None
            now_str = datetime.now(pytz.timezone('Asia/Hong_Kong')).strftime('%Y-%m-%d_%H%M%S')
            filename = f"{now_str}_{label}_{file.filename}"
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(file_path)
            return filename

        uploaded_count = 0
        results = []

        customer_invoice = save_file_with_timestamp(invoice_pdf, 'invoice') if invoice_pdf else None
        customer_packing_list = save_file_with_timestamp(packing_pdf, 'packing') if packing_pdf else None

        if bill_pdfs:
            for bill_pdf in bill_pdfs:
                pdf_filename = save_file_with_timestamp(bill_pdf, 'bill')
                fields = {}

                if bill_pdf:
                    pdf_path = os.path.join(UPLOAD_FOLDER, pdf_filename)
                    fields = extract_fields(pdf_path)

                # 🔍 Debug print
                print("flight_or_vessel:", fields.get("flight_or_vessel", ""))
                print("product_description:", fields.get("product_description", ""))

                fields_json = json.dumps(fields)
                hk_now = datetime.now(pytz.timezone('Asia/Hong_Kong')).isoformat()

                conn = get_db_conn()
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO bill_of_lading (
                        customer_name, customer_email, customer_phone, pdf_filename, ocr_text,
                        shipper, consignee, port_of_loading, port_of_discharge, bl_number, container_numbers,
                        flight_or_vessel, product_description, status,
                        customer_username, created_at, customer_invoice, customer_packing_list
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    name, str(email), str(phone), pdf_filename, fields_json,
                    str(fields.get('shipper', '')),
                    str(fields.get('consignee', '')),
                    str(fields.get('port_of_loading', '')),
                    str(fields.get('port_of_discharge', '')),
                    str(fields.get('bl_number', '')),
                    str(fields.get('container_numbers', '')),
                    str(fields.get('flight_or_vessel', '')),
                    str(fields.get('product_description', '')),
                    "Pending",
                    username,
                    hk_now,
                    customer_invoice,
                    customer_packing_list
                ))
                conn.commit()
                cur.close()
                conn.close()
                uploaded_count += 1
        else:
            hk_now = datetime.now(pytz.timezone('Asia/Hong_Kong')).isoformat()
            conn = get_db_conn()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO bill_of_lading (
                    customer_name, customer_email, customer_phone, pdf_filename, ocr_text,
                    shipper, consignee, port_of_loading, port_of_discharge, bl_number, container_numbers, status,
                    customer_username, created_at, customer_invoice, customer_packing_list
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                name, str(email), str(phone), None, None,
                '', '', '', '', '', '',
                "Pending",
                username,
                hk_now,
                customer_invoice,
                customer_packing_list
            ))
            conn.commit()
            cur.close()
            conn.close()
            uploaded_count += 1

        try:
            if EmailConfig.SMTP_SERVER and EmailConfig.SMTP_USERNAME and EmailConfig.SMTP_PASSWORD:
                subject = "We have received your Bill of Lading"
                body = f"Dear {name},\n\nWe have received your documents. Our team will be in touch with you within 24 hours.\n\nThank you!"
                send_simple_email(email, subject, body)
        except Exception as e:
            print(f"Failed to send confirmation email: {str(e)}")

        return jsonify({'message': f'Upload successful! {uploaded_count} bill(s) uploaded.'})

    except Exception as e:
        print(f"Error processing upload: {str(e)}")
        return jsonify({'error': f'Error processing upload: {str(e)}'}), 400


@app.route('/api/bills', methods=['GET'])
def get_bills():
    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('page_size', 50))
    offset = (page - 1) * page_size
    bl_number = request.args.get('bl_number')
    status = request.args.get('status')
    date = request.args.get('date')
    conn = get_db_conn()
    cur = conn.cursor()

    # Build WHERE clause
    where_clauses = []
    params = []
    if bl_number:
        where_clauses.append('bl_number ILIKE %s')
        params.append(f'%{bl_number}%')
    if status:
        where_clauses.append('status = %s')
        params.append(status)
    if date:
        start_date, end_date = get_hk_date_range(date)
        where_clauses.append('created_at >= %s AND created_at < %s')
        params.extend([start_date, end_date])
    where_sql = ' AND '.join(where_clauses)
    if where_sql:
        where_sql = 'WHERE ' + where_sql

    # Get total count for pagination
    count_query = f'SELECT COUNT(*) FROM bill_of_lading {where_sql}'
    cur.execute(count_query, tuple(params))
    total_count = cur.fetchone()[0]

    # Get paginated results
    query = f'''
        SELECT id, customer_name, customer_email, customer_phone, pdf_filename, shipper, consignee, port_of_loading, port_of_discharge, bl_number, container_numbers,
               flight_or_vessel, product_description,  -- <-- add here
               service_fee, ctn_fee, payment_link, receipt_filename, status, invoice_filename, unique_number, created_at, receipt_uploaded_at, customer_username, customer_invoice, customer_packing_list
        FROM bill_of_lading
        {where_sql}
        ORDER BY id DESC
        LIMIT %s OFFSET %s
    '''
    cur.execute(query, tuple(params) + (page_size, offset))
    rows = cur.fetchall()
    columns = [desc[0] for desc in cur.description]
    bills = []
    for row in rows:
        bill_dict = dict(zip(columns, row))
        # Decrypt email and phone
        if bill_dict.get('customer_email') is not None:
            bill_dict['customer_email'] = decrypt_sensitive_data(bill_dict['customer_email'])
        if bill_dict.get('customer_phone') is not None:
            bill_dict['customer_phone'] = decrypt_sensitive_data(bill_dict['customer_phone'])
        bills.append(bill_dict)

    cur.close()
    conn.close()

    return jsonify({
        'bills': bills,
        'total': total_count,
        'page': page,
        'page_size': page_size
    })

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/api/bill/<int:bill_id>/upload_receipt', methods=['POST'])
def upload_receipt(bill_id):
    if 'receipt' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    receipt = request.files['receipt']
    filename = f"receipt_{bill_id}_{receipt.filename}"
    receipt_path = os.path.join(UPLOAD_FOLDER, filename)
    receipt.save(receipt_path)

    hk_now = datetime.now(pytz.timezone('Asia/Hong_Kong')).isoformat()
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE bill_of_lading
        SET receipt_filename=%s, status=%s, receipt_uploaded_at=%s
        WHERE id=%s
    """, (filename, 'Awaiting Bank In', hk_now, bill_id))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({'message': 'Receipt uploaded'})

@app.route('/api/bills/<int:bill_id>', methods=['GET', 'PUT'])
def bill_detail(bill_id):
    if request.method == 'GET':
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM bill_of_lading WHERE id=%s", (bill_id,))
        bill_row = cur.fetchone()
        if not bill_row:
            cur.close()
            conn.close()
            return jsonify({'error': 'Bill not found'}), 404
        columns = [desc[0] for desc in cur.description]
        bill = dict(zip(columns, bill_row))
        # Decrypt sensitive fields
        if bill.get('customer_email') is not None:
            bill['customer_email'] = decrypt_sensitive_data(bill['customer_email'])
        if bill.get('customer_phone') is not None:
            bill['customer_phone'] = decrypt_sensitive_data(bill['customer_phone'])
        cur.close()
        conn.close()
        return jsonify(bill)
    elif request.method == 'PUT':
        data = request.get_json()
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM bill_of_lading WHERE id=%s", (bill_id,))
        bill_row = cur.fetchone()
        if not bill_row:
            cur.close()
            conn.close()
            return jsonify({'error': 'Bill not found'}), 404
        columns = [desc[0] for desc in cur.description]
        bill = dict(zip(columns, bill_row))
        # Allow updating all relevant fields, including new ones
        updatable_fields = [
            'customer_name', 'customer_email', 'customer_phone', 'bl_number',
            'shipper', 'consignee', 'port_of_loading', 'port_of_discharge',
            'container_numbers', 'service_fee', 'ctn_fee', 'payment_link', 'unique_number',
            'flight_or_vessel', 'product_description',
            'payment_method', 'payment_status', 'reserve_status'  # <-- new fields
        ]
        update_fields = []
        update_values = []
        for field in updatable_fields:
            if field in data and data[field] is not None:
                if field == 'customer_email':
                    update_fields.append(f"{field}=%s")
                    update_values.append(encrypt_sensitive_data(data[field]))
                elif field == 'customer_phone':
                    update_fields.append(f"{field}=%s")
                    update_values.append(encrypt_sensitive_data(data[field]))
                else:
                    update_fields.append(f"{field}=%s")
                    update_values.append(data[field])
        if update_fields:
            update_values.append(bill_id)
            update_query = f"""
                UPDATE bill_of_lading
                SET {', '.join(update_fields)}
                WHERE id=%s
            """
            cur.execute(update_query, tuple(update_values))
            conn.commit()
        # Fetch updated bill
        cur.execute("SELECT * FROM bill_of_lading WHERE id=%s", (bill_id,))
        bill_row = cur.fetchone()
        columns = [desc[0] for desc in cur.description]
        bill = dict(zip(columns, bill_row))
        # Decrypt sensitive fields
        if bill.get('customer_email') is not None:
            bill['customer_email'] = decrypt_sensitive_data(bill['customer_email'])
        if bill.get('customer_phone') is not None:
            bill['customer_phone'] = decrypt_sensitive_data(bill['customer_phone'])
        # Regenerate invoice PDF if relevant fields changed
        customer = {
            'name': bill['customer_name'],
            'email': bill['customer_email'],
            'phone': bill['customer_phone']
        }
        try:
            invoice_filename = generate_invoice_pdf(customer, bill, bill.get('service_fee'), bill.get('ctn_fee'), bill.get('payment_link'))
            bill['invoice_filename'] = invoice_filename
        except Exception as e:
            print(f"Error generating invoice PDF: {str(e)}")
        cur.close()
        conn.close()
        return jsonify(bill)
    
@app.route('/api/bill/<int:bill_id>/settle_reserve', methods=['POST'])
@jwt_required()
def settle_reserve(bill_id):
    conn = get_db_conn()
    cur = conn.cursor()
    try:
        # Check if bill exists
        cur.execute("SELECT id FROM bill_of_lading WHERE id = %s", (bill_id,))
        if not cur.fetchone():
            return jsonify({"error": "Bill not found"}), 404

        # Update reserve_status field to 'Reserve Settled'
        cur.execute("""
            UPDATE bill_of_lading
            SET reserve_status = 'Reserve Settled'
            WHERE id = %s
        """, (bill_id,))
        conn.commit()
        return jsonify({"message": "Reserve marked as settled"}), 200
    except Exception as e:
        print(f"Error settling reserve: {e}")
        return jsonify({"error": "Failed to settle reserve"}), 500
    finally:
        cur.close()
        conn.close()   

# @app.route('/api/bill/<int:bill_id>/service_fee', methods=['POST'])
# @cross_origin()
# @jwt_required()
# def update_service_fee(bill_id):
#     try:
    #     # Get user role from JWT
    #     user = get_jwt_identity()
    #     user = json.loads(user) if isinstance(user, str) else user
    #     print(f"User attempting update: {user}")
    #     if user.get('role') not in ['staff', 'admin']:
    #         return jsonify({'error': 'Unauthorized'}), 403

    #     data = request.get_json()
    #     print(f"Received update data: {data}")
    #     if not data:
    #         return jsonify({'error': 'No data provided'}), 400

    #     service_fee = data.get('service_fee')
    #     ctn_fee = data.get('ctn_fee')
    #     payment_link = data.get('payment_link')
    #     unique_number = data.get('unique_number')
        
    #     if not all([service_fee, ctn_fee, payment_link, unique_number]):
    #         return jsonify({'error': 'Missing required fields'}), 400

    #     try:
    #         # Convert fees to float
    #         service_fee = float(service_fee)
    #         ctn_fee = float(ctn_fee)
    #         print(f"Converted fees: service_fee={service_fee}, ctn_fee={ctn_fee}")
    #     except ValueError as e:
    #         print(f"ValueError converting fees: {str(e)}")
    #         return jsonify({'error': 'Invalid fee values'}), 400

    #     # Get database connection
    #     try:
    #         conn = get_db_conn()
    #         if not conn:
    #             print("Database connection failed")
    #             return jsonify({'error': 'Database connection failed'}), 500
    #         print("Database connection successful")
    #     except Exception as e:
    #         print(f"Error getting database connection: {str(e)}")
    #         return jsonify({'error': f'Database connection error: {str(e)}'}), 500

    #     try:
    #         cur = conn.cursor()
    #         print("Cursor created successfully")
    #     except Exception as e:
    #         print(f"Error creating cursor: {str(e)}")
    #         return jsonify({'error': f'Cursor creation error: {str(e)}'}), 500

    #     try:
    #         print(f"Checking if bill {bill_id} exists...")
    #         cur.execute("SELECT id FROM bill_of_lading WHERE id=%s", (bill_id,))
    #         bill_exists = cur.fetchone()
    #         print(f"Bill exists check result: {bill_exists}")
    #         if not bill_exists:
    #             return jsonify({'error': 'Bill not found'}), 404

    #         print("Building update query...")
    #         # Update fields
    #         update_fields = []
    #         update_values = []
    #         if service_fee is not None:
    #             update_fields.append('service_fee=%s')
    #             update_values.append(service_fee)
    #         if ctn_fee is not None:
    #             update_fields.append('ctn_fee=%s')
    #             update_values.append(ctn_fee)
    #         if payment_link is not None:
    #             update_fields.append('payment_link=%s')
    #             update_values.append(payment_link)
    #         if unique_number:
    #             update_fields.append('unique_number=%s')
    #             update_values.append(unique_number)
    #         update_values.append(bill_id)

    #         update_query = f"""
    #             UPDATE bill_of_lading
    #             SET {', '.join(update_fields)}
    #             WHERE id=%s
    #         """
    #         print(f"Update query: {update_query}")
    #         print(f"Update values: {update_values}")
            
    #         try:
    #             cur.execute(update_query, tuple(update_values))
    #             print("Update executed successfully")
    #             conn.commit()
    #             print("Transaction committed")
    #         except Exception as e:
    #             print(f"Error executing update: {str(e)}")
    #             conn.rollback()
    #             raise

    #         print("Fetching updated bill info...")
    #         cur.execute("SELECT * FROM bill_of_lading WHERE id=%s", (bill_id,))
    #         bill_row = cur.fetchone()
    #         print(f"Updated bill row: {bill_row}")
    #         if not bill_row:
    #             return jsonify({'error': 'Failed to update bill'}), 500

    #         columns = [desc[0] for desc in cur.description]
    #         bill = dict(zip(columns, bill_row))
    #         print(f"Updated bill data: {bill}")

    #         # Decrypt customer data
    #         customer = {
    #             'name': bill['customer_name'],
    #             'email': decrypt_sensitive_data(bill['customer_email']) if bill['customer_email'] is not None else '',
    #             'phone': decrypt_sensitive_data(bill['customer_phone']) if bill['customer_phone'] is not None else ''
    #         }
    #         print(f"Customer info: {customer}")

    #         print("Generating invoice PDF...")
    #         try:
    #             invoice_filename = generate_invoice_pdf(customer, bill, service_fee, ctn_fee, payment_link)
    #             invoice_path = os.path.join('uploads', invoice_filename)
    #             print(f"Invoice generated: {invoice_path}")

    #             # Check if file exists
    #             if not os.path.exists(invoice_path):
    #                 print(f"Error: Invoice file not found at {invoice_path}")
    #                 return jsonify({'error': 'Failed to generate invoice PDF'}), 500

    #             # Only send email if explicitly requested (not for staff/admin updates)
    #             # For now, we'll skip automatic email sending
    #             print("Invoice generated successfully, email sending disabled for staff/admin updates")
                
    #         except Exception as e:
    #             print(f"Error during invoice generation: {str(e)}")
    #             return jsonify({'error': f'Failed to generate invoice: {str(e)}'}), 500

    #         return jsonify({'message': 'Service fee, CTN fee, and payment link updated successfully'}), 200

    #     except Exception as db_error:
    #         conn.rollback()
    #         return jsonify({'error': f'Database error: {str(db_error)}'}), 500
    #     finally:
    #         cur.close()
    #         conn.close()

    # except Exception as e:
    #     print(f"Error in update_service_fee: {str(e)}")
    #     return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@app.route('/api/bill/<int:bill_id>/complete', methods=['POST'])
def complete_bill(bill_id):
    conn = get_db_conn()
    cur = conn.cursor()
    hk_now = datetime.now(pytz.timezone('Asia/Hong_Kong'))
    # Check payment_method for this bill
    cur.execute("SELECT payment_method FROM bill_of_lading WHERE id=%s", (bill_id,))
    row = cur.fetchone()
    if row and row[0] and row[0].lower() == 'allinpay':
        # For Allinpay, also update payment_status to 'Paid 100%'
        cur.execute("""
            UPDATE bill_of_lading
            SET status=%s, payment_status=%s, completed_at=%s
            WHERE id=%s
        """, ('Paid and CTN Valid', 'Paid 100%', hk_now, bill_id))
    else:
        # For others, just update status and completed_at
        cur.execute("""
            UPDATE bill_of_lading
            SET status=%s, completed_at=%s
            WHERE id=%s
        """, ('Paid and CTN Valid', hk_now, bill_id))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({'message': 'Bill marked as completed'})


# @app.route('/api/bill/<int:bill_id>/complete', methods=['POST'])
# def complete_bill(bill_id):
#     conn = get_db_conn()
#     cur = conn.cursor()
#     hk_now = datetime.now(pytz.timezone('Asia/Hong_Kong'))
#     cur.execute("""
#         UPDATE bill_of_lading
#         SET status=%s, completed_at=%s
#         WHERE id=%s
#     """, ('Paid and CTN Valid', hk_now, bill_id))
#     conn.commit()
#     cur.close()
#     conn.close()
#     return jsonify({'message': 'Bill marked as completed'})

@app.route('/api/search_bills', methods=['POST'])
@jwt_required()
def search_bills():
    data = request.get_json()
    customer_name = data.get('customer_name', '')
    customer_id = data.get('customer_id', '')
    created_at = data.get('created_at', '')
    bl_number = data.get('bl_number', '')
    unique_number = data.get('unique_number', '')  # Add support for CTN number search
    username = data.get('username', '')  # Add support for username search
    
    conn = get_db_conn()
    cur = conn.cursor()
    
    query = '''
        SELECT id, customer_name, customer_email, customer_phone, pdf_filename, shipper, consignee, port_of_loading, port_of_discharge, bl_number, container_numbers, service_fee, ctn_fee, payment_link, receipt_filename, status, invoice_filename, unique_number, created_at, receipt_uploaded_at, customer_username, customer_invoice, customer_packing_list
        FROM bill_of_lading
        WHERE 1=1
    '''
    params = []
    
    if customer_name:
        query += ' AND customer_name ILIKE %s'
        params.append(f'%{customer_name}%')
    
    if customer_id:
        # Validate that customer_id is a number
        try:
            int(customer_id)
            query += ' AND id = %s'
            params.append(customer_id)
        except ValueError:
            # If not a number, search by customer name instead
            query += ' AND customer_name ILIKE %s'
            params.append(f'%{customer_id}%')
    
    if created_at:
        # Use timezone-aware date range for created_at
        start_date, end_date = get_hk_date_range(created_at)
        query += ' AND created_at >= %s AND created_at < %s'
        params.extend([start_date, end_date])
    
    if bl_number:
        query += ' AND bl_number ILIKE %s'
        params.append(f'%{bl_number}%')
    
    if unique_number:
        query += ' AND unique_number = %s'
        params.append(unique_number)
    
    if username:
        query += ' AND customer_username = %s'
        params.append(username)
    
    query += ' ORDER BY id DESC'
    
    cur.execute(query, params)
    rows = cur.fetchall()
    columns = [desc[0] for desc in cur.description]
    
    bills = []
    for row in rows:
        bill_dict = dict(zip(columns, row))
        # Decrypt email and phone
        if bill_dict.get('customer_email') is not None:
            bill_dict['customer_email'] = decrypt_sensitive_data(bill_dict['customer_email'])
        if bill_dict.get('customer_phone') is not None:
            bill_dict['customer_phone'] = decrypt_sensitive_data(bill_dict['customer_phone'])
        bills.append(bill_dict)
    
    cur.close()
    conn.close()
    return jsonify(bills)

@app.route('/api/bill/<int:bill_id>/unique_number', methods=['POST'])
def set_unique_number(bill_id):
    data = request.get_json()
    unique_number = data.get('unique_number')
    if not unique_number:
        return jsonify({'error': 'Missing unique number'}), 400

    # Update DB
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE bill_of_lading
        SET unique_number=%s
        WHERE id=%s
    """, (unique_number, bill_id))
    conn.commit()

    # Fetch customer email
    cur.execute("SELECT customer_email, customer_name FROM bill_of_lading WHERE id=%s", (bill_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if row:
        customer_email, customer_name = row
        # Send email
        send_unique_number_email(customer_email, customer_name, unique_number)

    return jsonify({'message': 'Unique number saved and email sent'})

@app.route('/api/send_unique_number_email', methods=['POST'])
def api_send_unique_number_email():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        to_email = data.get('to_email')
        subject = data.get('subject')
        body = data.get('body')
        bill_id = data.get('bill_id')

        if not all([to_email, subject, body, bill_id]):
            return jsonify({'error': 'Missing required fields'}), 400

        # Validate bill_id exists
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("SELECT id FROM bill_of_lading WHERE id=%s", (bill_id,))
        if not cur.fetchone():
            return jsonify({'error': 'Bill not found'}), 404

        # Send email
        send_unique_number_email(to_email, subject, body)

        return jsonify({'message': 'Unique number email sent successfully'}), 200

    except Exception as e:
        print(f"Error in send_unique_number_email: {str(e)}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@app.route('/api/me', methods=['GET'])
@jwt_required()
def get_me():
    user = json.loads(get_jwt_identity())
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("SELECT customer_name, customer_email, customer_phone FROM users WHERE username=%s", (user['username'],))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row:
        # Decrypt email and phone
        decrypted_email = decrypt_sensitive_data(row[1]) if row[1] is not None else ''
        decrypted_phone = decrypt_sensitive_data(row[2]) if row[2] is not None else ''
        return jsonify({
            "customer_name": row[0],
            "customer_email": decrypted_email,
            "customer_phone": decrypted_phone
        })
    else:
        return jsonify({"error": "User not found"}), 404

@app.route('/api/bill/<int:bill_id>', methods=['DELETE'])
@jwt_required()
def delete_bill(bill_id):
    user = json.loads(get_jwt_identity())
    if user['role'] not in ['staff', 'admin']:
        return jsonify({'error': 'Unauthorized'}), 403
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM bill_of_lading WHERE id=%s", (bill_id,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({'message': 'Bill deleted'})

@app.route('/api/contact', methods=['POST'])
def contact():
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    message = data.get('message')
    if not all([name, email, message]):
        return jsonify({'error': 'Missing fields'}), 400
    try:
        success = send_contact_email(name, email, message)
        if success:
            return jsonify({'message': 'Message sent successfully!'})
        else:
            return jsonify({'error': 'Failed to send email'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats/summary')
@jwt_required()
def stats_summary():
    user = json.loads(get_jwt_identity())
    if user['role'] not in ['staff', 'admin']:
        return jsonify({'error': 'Unauthorized'}), 403
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM bill_of_lading")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM bill_of_lading WHERE status='Completed'")
    completed = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM bill_of_lading WHERE status!='Completed'")
    pending = cur.fetchone()[0]
    cur.execute("SELECT COALESCE(SUM(service_fee),0) FROM bill_of_lading")
    total_invoice_amount = float(cur.fetchone()[0] or 0)
    cur.execute("SELECT COALESCE(SUM(service_fee),0) FROM bill_of_lading WHERE status='Completed'")
    total_payment_received = float(cur.fetchone()[0] or 0)
    cur.execute("SELECT COALESCE(SUM(service_fee),0) FROM bill_of_lading WHERE status!='Completed'")
    total_payment_outstanding = float(cur.fetchone()[0] or 0)
    cur.close()
    conn.close()
    return jsonify({
        'total_bills': total,
        'completed_bills': completed,
        'pending_bills': pending,
        'total_invoice_amount': total_invoice_amount,
        'total_payment_received': total_payment_received,
        'total_payment_outstanding': total_payment_outstanding
    })

@app.route('/api/stats/outstanding_bills')
@jwt_required()
def outstanding_bills():
    user = json.loads(get_jwt_identity())
    if user['role'] not in ['staff', 'admin']:
        return jsonify({'error': 'Unauthorized'}), 403
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, customer_name, bl_number, service_fee, invoice_filename FROM bill_of_lading WHERE status!='Completed'")
    rows = cur.fetchall()
    columns = [desc[0] for desc in cur.description]
    bills = [dict(zip(columns, row)) for row in rows]
    cur.close()
    conn.close()
    return jsonify(bills)

@app.route('/api/request_password_reset', methods=['POST'])
def request_password_reset():
    data = request.get_json()
    email = data.get('email')
    if not email:
        return jsonify({'error': 'Email required'}), 400

    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, customer_name, customer_email FROM users")
    users = cur.fetchall()
    user = None
    for row in users:
        user_id, customer_name, encrypted_email = row
        try:
            decrypted_email = decrypt_sensitive_data(encrypted_email)
            if decrypted_email == email:
                user = (user_id, customer_name)
                break
        except Exception as e:
            continue
    if not user:
        cur.close()
        conn.close()
        return jsonify({'message': 'If this email is registered, a reset link will be sent.'})  # Don't reveal user existence

    user_id, customer_name = user
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(pytz.timezone('Asia/Hong_Kong')) + timedelta(hours=1)
    cur.execute("INSERT INTO password_reset_tokens (user_id, token, expires_at) VALUES (%s, %s, %s)", (user_id, token, expires_at))
    conn.commit()
    cur.close()
    conn.close()

    reset_link = f"https://www.terryraylogicticsco.xyz/reset-password/{token}"
    subject = "Password Reset Request"
    body = f"Dear {customer_name},\n\nClick the link below to reset your password:\n{reset_link}\n\nThis link will expire in 1 hour."
    send_simple_email(email, subject, body)
    return jsonify({'message': 'If this email is registered, a reset link will be sent.'})

@app.route('/api/reset_password/<token>', methods=['POST'])
def reset_password(token):
    data = request.get_json()
    new_password = data.get('password')
    if not new_password:
        return jsonify({'error': 'Password required'}), 400

    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("SELECT user_id, expires_at FROM password_reset_tokens WHERE token=%s", (token,))
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        return jsonify({'error': 'Invalid or expired token'}), 400

    user_id, expires_at = row
    if datetime.now(pytz.timezone('Asia/Hong_Kong')) > expires_at:
        cur.execute("DELETE FROM password_reset_tokens WHERE token=%s", (token,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'error': 'Token expired'}), 400

    password_hash = generate_password_hash(new_password)
    cur.execute("UPDATE users SET password_hash=%s WHERE id=%s", (password_hash, user_id))
    cur.execute("DELETE FROM password_reset_tokens WHERE token=%s", (token,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({'message': 'Password has been reset successfully.'})

@app.route('/api/send_invoice_email', methods=['POST'])
@jwt_required()
def send_invoice_email_endpoint():
    try:
        data = request.get_json()
        to_email = data.get('to_email')
        subject = data.get('subject')
        body = data.get('body')
        pdf_url = data.get('pdf_url')
        bill_id = data.get('bill_id')

        if not all([to_email, subject, body, pdf_url, bill_id]):
            return jsonify({'error': 'Missing required fields'}), 400

        # Fix: Extract just the filename if pdf_url is a full URL
        import os
        if pdf_url.startswith('http://') or pdf_url.startswith('https://'):
            pdf_filename = os.path.basename(pdf_url)
        else:
            pdf_filename = pdf_url.lstrip('/')
        pdf_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads', pdf_filename)
        
        # Send the email
        success = send_invoice_email(to_email, subject, body, pdf_path)
        
        if success:
            # Update bill status to "Invoice Sent"
            conn = get_db_conn()
            cur = conn.cursor()
            cur.execute("UPDATE bill_of_lading SET status=%s WHERE id=%s", ("Invoice Sent", bill_id))
            conn.commit()
            cur.close()
            conn.close()
            return jsonify({'message': 'Email sent successfully'})
        else:
            return jsonify({'error': 'Failed to send email'}), 500
            
    except Exception as e:
        print(f"Error sending invoice email: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Helper function for timezone-aware date queries
def get_hk_date_range(search_date_str):
    """
    Convert a date string (YYYY-MM-DD) to Hong Kong timezone range for database queries.
    Returns (start_datetime, end_datetime) in Hong Kong timezone.
    """
    hk_tz = pytz.timezone('Asia/Hong_Kong')
    search_date = datetime.strptime(search_date_str, '%Y-%m-%d')
    search_date = hk_tz.localize(search_date)
    next_date = search_date + timedelta(days=1)
    return search_date, next_date

@app.route('/api/account_bills', methods=['GET'])
def account_bills():
    completed_at = request.args.get('completed_at')
    bl_number = request.args.get('bl_number')

    conn = get_db_conn()
    cur = conn.cursor()

    # Build base query
    select_clause = '''
        SELECT id, customer_name, customer_email, customer_phone, pdf_filename,
               shipper, consignee, port_of_loading, port_of_discharge, bl_number,
               container_numbers, service_fee, ctn_fee, payment_link, receipt_filename,
               status, invoice_filename, unique_number, created_at, receipt_uploaded_at,
               completed_at, allinpay_85_received_at,
               customer_username, customer_invoice, customer_packing_list,
               payment_method, payment_status, reserve_status
        FROM bill_of_lading
        WHERE status = 'Paid and CTN Valid'
    '''

    where_clauses = []
    params = []

    if completed_at:
        start_date, end_date = get_hk_date_range(completed_at)
        print("DEBUG: start_date", start_date, "end_date", end_date)
        where_clauses.append(
            "((payment_method = 'Allinpay' AND allinpay_85_received_at >= %s AND allinpay_85_received_at < %s) "
            "OR (payment_method = 'Allinpay' AND completed_at >= %s AND completed_at < %s) "
            "OR (payment_method != 'Allinpay' AND completed_at >= %s AND completed_at < %s))"
        )
        params.extend([start_date, end_date, start_date, end_date, start_date, end_date])
    if bl_number:
        where_clauses.append("bl_number ILIKE %s")
        params.append(f'%{bl_number}%')

    if where_clauses:
        select_clause += " AND " + " AND ".join(where_clauses)

    select_clause += " ORDER BY id DESC"

    cur.execute(select_clause, tuple(params))
    rows = cur.fetchall()
    columns = [desc[0] for desc in cur.description]

    bills = []
    valid_bills = []
    total_bank_ctn = 0
    total_bank_service = 0
    total_allinpay_85_ctn = 0
    total_allinpay_85_service = 0
    total_reserve_ctn = 0
    total_reserve_service = 0

    for row in rows:
        bill = dict(zip(columns, row))

        # Decrypt sensitive fields
        if bill.get('customer_email'):
            bill['customer_email'] = decrypt_sensitive_data(bill['customer_email'])
        if bill.get('customer_phone'):
            bill['customer_phone'] = decrypt_sensitive_data(bill['customer_phone'])

        try:
            ctn_fee = float(bill.get('ctn_fee') or 0)
            service_fee = float(bill.get('service_fee') or 0)
        except (TypeError, ValueError):
            ctn_fee = 0
            service_fee = 0

        # Default: show original values
        bill['display_ctn_fee'] = ctn_fee
        bill['display_service_fee'] = service_fee

        # Debug print for each bill
        print("DEBUG: bill id", bill.get('id'), "payment_method", bill.get('payment_method'),
              "allinpay_85_received_at", bill.get('allinpay_85_received_at'),
              "completed_at", bill.get('completed_at'),
              "reserve_status", bill.get('reserve_status'))

        if bill.get('payment_method') == 'Allinpay':
            # 85% part
            allinpay_85_dt = bill.get('allinpay_85_received_at')
            is_85 = False
            if allinpay_85_dt:
                if isinstance(allinpay_85_dt, str):
                    try:
                        allinpay_85_dt = parser.isoparse(allinpay_85_dt)
                    except Exception:
                        allinpay_85_dt = None
                if allinpay_85_dt and allinpay_85_dt.tzinfo is None:
                    allinpay_85_dt = allinpay_85_dt.replace(tzinfo=pytz.UTC)
                if completed_at and allinpay_85_dt and start_date <= allinpay_85_dt < end_date:
                    total_allinpay_85_ctn += round(ctn_fee * 0.85, 2)
                    total_allinpay_85_service += round(service_fee * 0.85, 2)
                    bill['display_ctn_fee'] = round(ctn_fee * 0.85, 2)
                    bill['display_service_fee'] = round(service_fee * 0.85, 2)
                    is_85 = True
                    bills.append(bill)
                    valid_bills.append(bill)
                    continue  # Don't double count as reserve

            # 15% part (reserve): only if reserve is settled and completed_at is in range
            reserve_status = (bill.get('reserve_status') or '').lower()
            completed_dt = bill.get('completed_at')
            if completed_dt:
                if isinstance(completed_dt, str):
                    try:
                        completed_dt = parser.isoparse(completed_dt)
                    except Exception:
                        completed_dt = None
                if completed_dt and completed_dt.tzinfo is None:
                    completed_dt = completed_dt.replace(tzinfo=pytz.UTC)
            if reserve_status in ['settled', 'reserve settled'] and completed_at and completed_dt and start_date <= completed_dt < end_date and not is_85:
                total_reserve_ctn += round(ctn_fee * 0.15, 2)
                total_reserve_service += round(service_fee * 0.15, 2)
                bill['display_ctn_fee'] = round(ctn_fee * 0.15, 2)
                bill['display_service_fee'] = round(service_fee * 0.15, 2)
                bills.append(bill)
                valid_bills.append(bill)
                continue
        else:
            # Bank Transfer: only if completed_at is in range
            completed_dt = bill.get('completed_at')
            if completed_dt:
                if isinstance(completed_dt, str):
                    try:
                        completed_dt = parser.isoparse(completed_dt)
                    except Exception:
                        completed_dt = None
                if completed_dt and completed_dt.tzinfo is None:
                    completed_dt = completed_dt.replace(tzinfo=pytz.UTC)
            if completed_at and completed_dt and start_date <= completed_dt < end_date:
                total_bank_ctn += ctn_fee
                total_bank_service += service_fee
                bills.append(bill)
                valid_bills.append(bill)
                continue

    summary = {
        'totalEntries': len(valid_bills),
        'totalCtnFee': round(total_bank_ctn + total_allinpay_85_ctn + total_reserve_ctn, 2),
        'totalServiceFee': round(total_bank_service + total_allinpay_85_service + total_reserve_service, 2),
        'bankTotal': round(total_bank_ctn + total_bank_service, 2),
        'allinpay85Total': round(total_allinpay_85_ctn + total_allinpay_85_service, 2),
        'reserveTotal': round(total_reserve_ctn + total_reserve_service, 2)
    }

    cur.close()
    conn.close()

    return jsonify({'bills': bills, 'summary': summary})

# @app.route('/api/account_bills', methods=['GET'])
# def account_bills():
#     completed_at = request.args.get('completed_at')
#     bl_number = request.args.get('bl_number')

#     conn = get_db_conn()
#     cur = conn.cursor()

#     # Build base query
#     select_clause = '''
#         SELECT id, customer_name, customer_email, customer_phone, pdf_filename,
#                shipper, consignee, port_of_loading, port_of_discharge, bl_number,
#                container_numbers, service_fee, ctn_fee, payment_link, receipt_filename,
#                status, invoice_filename, unique_number, created_at, receipt_uploaded_at,
#                completed_at, allinpay_85_received_at,
#                customer_username, customer_invoice, customer_packing_list,
#                payment_method, payment_status, reserve_status
#         FROM bill_of_lading
#         WHERE status = 'Paid and CTN Valid'
#     '''

#     where_clauses = []
#     params = []

#     if completed_at:
#         start_date, end_date = get_hk_date_range(completed_at)
#         print("DEBUG: start_date", start_date, "end_date", end_date)
#         where_clauses.append(
#             "((payment_method = 'Allinpay' AND allinpay_85_received_at >= %s AND allinpay_85_received_at < %s) "
#             "OR (payment_method = 'Allinpay' AND completed_at >= %s AND completed_at < %s) "
#             "OR (payment_method != 'Allinpay' AND completed_at >= %s AND completed_at < %s))"
#         )
#         params.extend([start_date, end_date, start_date, end_date, start_date, end_date])
#     if bl_number:
#         where_clauses.append("bl_number ILIKE %s")
#         params.append(f'%{bl_number}%')

#     if where_clauses:
#         select_clause += " AND " + " AND ".join(where_clauses)

#     select_clause += " ORDER BY id DESC"

#     cur.execute(select_clause, tuple(params))
#     rows = cur.fetchall()
#     columns = [desc[0] for desc in cur.description]

#     bills = []
#     valid_bills = []
#     total_bank_ctn = 0
#     total_bank_service = 0
#     total_allinpay_85_ctn = 0
#     total_allinpay_85_service = 0
#     total_reserve_ctn = 0
#     total_reserve_service = 0

#     for row in rows:
#         bill = dict(zip(columns, row))

#         # Decrypt sensitive fields
#         if bill.get('customer_email'):
#             bill['customer_email'] = decrypt_sensitive_data(bill['customer_email'])
#         if bill.get('customer_phone'):
#             bill['customer_phone'] = decrypt_sensitive_data(bill['customer_phone'])

#         bills.append(bill)

#         try:
#             ctn_fee = float(bill.get('ctn_fee') or 0)
#             service_fee = float(bill.get('service_fee') or 0)
#         except (TypeError, ValueError):
#             continue

#         valid_bills.append(bill)

#         # Debug print for each bill
#         print("DEBUG: bill id", bill.get('id'), "payment_method", bill.get('payment_method'),
#               "allinpay_85_received_at", bill.get('allinpay_85_received_at'),
#               "completed_at", bill.get('completed_at'),
#               "reserve_status", bill.get('reserve_status'))

#         if bill.get('payment_method') == 'Allinpay':
#             # 85% part
#             allinpay_85_dt = bill.get('allinpay_85_received_at')
#             if allinpay_85_dt:
#                 if isinstance(allinpay_85_dt, str):
#                     try:
#                         allinpay_85_dt = parser.isoparse(allinpay_85_dt)
#                     except Exception:
#                         allinpay_85_dt = None
#                 if allinpay_85_dt and allinpay_85_dt.tzinfo is None:
#                     # Assume UTC if no tzinfo
#                     allinpay_85_dt = allinpay_85_dt.replace(tzinfo=pytz.UTC)
#                 if completed_at and allinpay_85_dt and start_date <= allinpay_85_dt < end_date:
#                     total_allinpay_85_ctn += round(ctn_fee * 0.85, 2)
#                     total_allinpay_85_service += round(service_fee * 0.85, 2)
#                     continue  # Don't double count as reserve

#             # 15% part (reserve): only if reserve is settled and completed_at is in range
#             reserve_status = (bill.get('reserve_status') or '').lower()
#             completed_dt = bill.get('completed_at')
#             if completed_dt:
#                 if isinstance(completed_dt, str):
#                     try:
#                         completed_dt = parser.isoparse(completed_dt)
#                     except Exception:
#                         completed_dt = None
#                 if completed_dt and completed_dt.tzinfo is None:
#                     completed_dt = completed_dt.replace(tzinfo=pytz.UTC)
#             if reserve_status in ['settled', 'reserve settled'] and completed_at and completed_dt and start_date <= completed_dt < end_date:
#                 total_reserve_ctn += round(ctn_fee * 0.15, 2)
#                 total_reserve_service += round(service_fee * 0.15, 2)
#         else:
#             # Bank Transfer: only if completed_at is in range
#             completed_dt = bill.get('completed_at')
#             if completed_dt:
#                 if isinstance(completed_dt, str):
#                     try:
#                         completed_dt = parser.isoparse(completed_dt)
#                     except Exception:
#                         completed_dt = None
#                 if completed_dt and completed_dt.tzinfo is None:
#                     completed_dt = completed_dt.replace(tzinfo=pytz.UTC)
#             if completed_at and completed_dt and start_date <= completed_dt < end_date:
#                 total_bank_ctn += ctn_fee
#                 total_bank_service += service_fee

#     summary = {
#         'totalEntries': len(valid_bills),
#         'totalCtnFee': round(total_bank_ctn + total_allinpay_85_ctn + total_reserve_ctn, 2),
#         'totalServiceFee': round(total_bank_service + total_allinpay_85_service + total_reserve_service, 2),
#         'bankTotal': round(total_bank_ctn + total_bank_service, 2),
#         'allinpay85Total': round(total_allinpay_85_ctn + total_allinpay_85_service, 2),
#         'reserveTotal': round(total_reserve_ctn + total_reserve_service, 2)
#     }

#     cur.close()
#     conn.close()

#     return jsonify({'bills': bills, 'summary': summary})

# @app.route('/api/account_bills', methods=['GET'])
# def account_bills():
#     completed_at = request.args.get('completed_at')
#     bl_number = request.args.get('bl_number')

#     conn = get_db_conn()
#     cur = conn.cursor()

#     base_query = '''
#         SELECT id, customer_name, customer_email, customer_phone, pdf_filename,
#                shipper, consignee, port_of_loading, port_of_discharge, bl_number,
#                container_numbers, service_fee, ctn_fee, payment_link, receipt_filename,
#                status, invoice_filename, unique_number, created_at, receipt_uploaded_at,
#                completed_at, customer_username, customer_invoice, customer_packing_list,
#                payment_method, payment_status, reserve_status
#         FROM bill_of_lading
#         WHERE status = 'Paid and CTN Valid'
#     '''

#     where_clauses = []
#     params = []

#     if completed_at:
#         start_date, end_date = get_hk_date_range(completed_at)
#         where_clauses.append("completed_at >= %s AND completed_at < %s")
#         params.extend([start_date, end_date])
#     if bl_number:
#         where_clauses.append("bl_number ILIKE %s")
#         params.append(f'%{bl_number}%')

#     if where_clauses:
#         base_query += " AND " + " AND ".join(where_clauses)

#     base_query += " ORDER BY id DESC"
#     cur.execute(base_query, tuple(params))
#     rows = cur.fetchall()
#     columns = [desc[0] for desc in cur.description]

#     bills = []
#     valid_bills = []
#     total_bank_ctn = 0
#     total_bank_service = 0
#     total_allinpay_85_ctn = 0
#     total_allinpay_85_service = 0
#     total_reserve_ctn = 0
#     total_reserve_service = 0

#     for row in rows:
#         bill = dict(zip(columns, row))

#         # Decrypt sensitive fields
#         if bill.get('customer_email'):
#             bill['customer_email'] = decrypt_sensitive_data(bill['customer_email'])
#         if bill.get('customer_phone'):
#             bill['customer_phone'] = decrypt_sensitive_data(bill['customer_phone'])

#         bills.append(bill)

#         # Convert fee strings to float, skip if invalid
#         try:
#             ctn_fee = float(bill.get('ctn_fee'))
#             service_fee = float(bill.get('service_fee'))
#         except (TypeError, ValueError):
#             continue  # skip this bill for summary

#         valid_bills.append(bill)

#         if bill.get('payment_method') == 'Allinpay':
#             # Always add 85% to allinpay85
#             total_allinpay_85_ctn += round(ctn_fee * 0.85, 2)
#             total_allinpay_85_service += round(service_fee * 0.85, 2)
#             # Only add 15% to reserve if settled
#             reserve_status = (bill.get('reserve_status') or '').lower()
#             if reserve_status in ['settled', 'reserve settled']:
#                 total_reserve_ctn += round(ctn_fee * 0.15, 2)
#                 total_reserve_service += round(service_fee * 0.15, 2)
#         else:
#             total_bank_ctn += ctn_fee
#             total_bank_service += service_fee

#     summary = {
#     'totalEntries': len(valid_bills),
#     'totalCtnFee': round(total_bank_ctn + total_allinpay_85_ctn + total_reserve_ctn, 2),
#     'totalServiceFee': round(total_bank_service + total_allinpay_85_service + total_reserve_service, 2),
#     'bankTotal': round(total_bank_ctn + total_bank_service, 2),
#     'allinpay85Total': round(total_allinpay_85_ctn + total_allinpay_85_service, 2),
#     'reserveTotal': round(total_reserve_ctn + total_reserve_service, 2)
# }

 
#     cur.close()
#     conn.close()
#     return jsonify({'bills': bills, 'summary': summary})



# @app.route('/api/account_bills', methods=['GET'])
# def account_bills():
#     completed_at = request.args.get('completed_at')
#     bl_number = request.args.get('bl_number')

#     conn = get_db_conn()
#     cur = conn.cursor()

#     base_query = '''
#         SELECT id, customer_name, customer_email, customer_phone, pdf_filename,
#                shipper, consignee, port_of_loading, port_of_discharge, bl_number,
#                container_numbers, service_fee, ctn_fee, payment_link, receipt_filename,
#                status, invoice_filename, unique_number, created_at, receipt_uploaded_at,
#                completed_at, customer_username, customer_invoice, customer_packing_list,
#                payment_method, payment_status, reserve_status
#         FROM bill_of_lading
#         WHERE status = 'Paid and CTN Valid'
#     '''

#     where_clauses = []
#     params = []

#     if completed_at:
#         start_date, end_date = get_hk_date_range(completed_at)
#         where_clauses.append("completed_at >= %s AND completed_at < %s")
#         params.extend([start_date, end_date])
#     if bl_number:
#         where_clauses.append("bl_number ILIKE %s")
#         params.append(f'%{bl_number}%')

#     if where_clauses:
#         base_query += " AND " + " AND ".join(where_clauses)

#     base_query += " ORDER BY id DESC"
#     cur.execute(base_query, tuple(params))
#     rows = cur.fetchall()
#     columns = [desc[0] for desc in cur.description]

#     bills = []
#     valid_bills = []
#     total_bank_ctn = 0
#     total_bank_service = 0
#     total_allinpay_85_ctn = 0
#     total_allinpay_85_service = 0
#     total_reserve_ctn = 0
#     total_reserve_service = 0

#     for row in rows:
#         bill = dict(zip(columns, row))

#         # Decrypt sensitive fields
#         if bill.get('customer_email'):
#             bill['customer_email'] = decrypt_sensitive_data(bill['customer_email'])
#         if bill.get('customer_phone'):
#             bill['customer_phone'] = decrypt_sensitive_data(bill['customer_phone'])

#         bills.append(bill)

#         # Convert fee strings to float, skip if invalid
#         try:
#             ctn_fee = float(bill.get('ctn_fee'))
#             service_fee = float(bill.get('service_fee'))
#         except (TypeError, ValueError):
#             continue  # skip this bill for summary

#         valid_bills.append(bill)

#         # Logic based on payment method
#         if bill.get('payment_method') == 'Allinpay':
#             if bill.get('reserve_status') == 'Settled':
#                 # Reserve (15%)
#                 total_reserve_ctn += round(ctn_fee * 0.15, 2)
#                 total_reserve_service += round(service_fee * 0.15, 2)
#             else:
#                 # 85% part
#                 total_allinpay_85_ctn += round(ctn_fee * 0.85, 2)
#                 total_allinpay_85_service += round(service_fee * 0.85, 2)
#         else:
#             # Assume Bank Transfer
#             total_bank_ctn += ctn_fee
#             total_bank_service += service_fee

#     summary = {
#         'totalEntries': len(valid_bills),
#         'totalCtnFee': round(sum(float(b.get('ctn_fee')) for b in valid_bills), 2),
#         'totalServiceFee': round(sum(float(b.get('service_fee')) for b in valid_bills), 2),
#         'bankTotal': round(total_bank_ctn + total_bank_service, 2),
#         'allinpay85Total': round(total_allinpay_85_ctn + total_allinpay_85_service, 2),
#         'reserveTotal': round(total_reserve_ctn + total_reserve_service, 2)
#     }

#     cur.close()
#     conn.close()
#     return jsonify({'bills': bills, 'summary': summary})

@app.route('/api/generate_payment_link/<int:bill_id>', methods=['POST'])
def generate_payment_link(bill_id):
    try:
        # Simulate link (replace with real Allinpay/Stripe call later)
        payment_link = f"https://pay.example.com/link/{bill_id}"

        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("UPDATE bill_of_lading SET payment_link = %s WHERE id = %s", (payment_link, bill_id))
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"payment_link": payment_link})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/bills/status/<status>', methods=['GET'])
def get_bills_by_status(status):
    conn = get_db_conn()
    cur = conn.cursor()
    
    cur.execute('''
        SELECT id, customer_name, customer_email, customer_phone, pdf_filename, shipper, consignee, port_of_loading, port_of_discharge, bl_number, container_numbers, service_fee, ctn_fee, payment_link, receipt_filename, status, invoice_filename, unique_number, created_at, receipt_uploaded_at, customer_username, customer_invoice, completed_at, customer_packing_list
        FROM bill_of_lading
        WHERE status = %s
        ORDER BY id DESC
    ''', (status,))
    
    rows = cur.fetchall()
    columns = [desc[0] for desc in cur.description]
    bills = []
    for row in rows:
        bill_dict = dict(zip(columns, row))
        # Decrypt email and phone
        if bill_dict.get('customer_email') is not None:
            bill_dict['customer_email'] = decrypt_sensitive_data(bill_dict['customer_email'])
        if bill_dict.get('customer_phone') is not None:
            bill_dict['customer_phone'] = decrypt_sensitive_data(bill_dict['customer_phone'])
        bills.append(bill_dict)

    cur.close()
    conn.close()  
    return jsonify(bills)

@app.route('/api/bills/awaiting_bank_in', methods=['GET'])
@jwt_required()
def get_awaiting_bank_in_bills():
    try:
        bl_number = request.args.get('bl_number', '').strip()
        conn = get_db_conn()
        cur = conn.cursor()

        where_clauses = []
        params = []

        # Remove reserve_status filter!
        # Only filter by status/payment_method and optional bl_number
        if bl_number:
            where_clauses.append(
                "((status = 'Awaiting Bank In' AND bl_number ILIKE %s) OR "
                "(payment_method = 'Allinpay' AND payment_status = 'Paid 85%' AND bl_number ILIKE %s))"
            )
            params.extend([f"%{bl_number}%", f"%{bl_number}%"])
        else:
            where_clauses.append(
                "((status = 'Awaiting Bank In') OR "
                "(payment_method = 'Allinpay' AND payment_status = 'Paid 85%'))"
            )

        where_sql = " AND ".join(where_clauses)
        query = (
            "SELECT * FROM bill_of_lading "
            "WHERE " + where_sql + " "
            "ORDER BY id DESC"
        )

        if params:
            cur.execute(query, tuple(params))
        else:
            cur.execute(query)
        rows = cur.fetchall()
        columns = [desc[0] for desc in cur.description]
        bills = []
        for row in rows:
            bill_dict = dict(zip(columns, row))
            # Decrypt email and phone if needed
            if bill_dict.get('customer_email') is not None:
                bill_dict['customer_email'] = decrypt_sensitive_data(bill_dict['customer_email'])
            if bill_dict.get('customer_phone') is not None:
                bill_dict['customer_phone'] = decrypt_sensitive_data(bill_dict['customer_phone'])
            bills.append(bill_dict)

        return jsonify({'bills': bills, 'total': len(bills)})
    except Exception as e:
        print("❌ ERROR in awaiting_bank_in:", str(e))
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Internal server error'}), 500
    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass


# @app.route('/api/bills/awaiting_bank_in', methods=['GET'])
# @jwt_required()
# def get_awaiting_bank_in_bills():
#     try:
#         bl_number = request.args.get('bl_number')
#         if bl_number is not None:
#             bl_number = bl_number.strip()
#         else:
#             bl_number = ''

#         conn = get_db_conn()
#         cur = conn.cursor()

#         where_clauses = []
#         params = []

#         reserve_filter = "(reserve_status IS NULL OR reserve_status != 'Reserve Settled')"
#         where_clauses.append(reserve_filter)

#         # Only add search if bl_number is not empty
#         if bl_number:
#             where_clauses.append(
#                 "((status = 'Awaiting Bank In' AND bl_number ILIKE %s) OR (payment_method = 'Allinpay' AND payment_status = 'Paid 85%' AND bl_number ILIKE %s))"
#             )
#             params.extend([f"%{bl_number}%", f"%{bl_number}%"])
#         else:
#             where_clauses.append(
#                 "((status = 'Awaiting Bank In') OR (payment_method = 'Allinpay' AND payment_status = 'Paid 85%'))"
#             )

#         where_sql = " AND ".join(where_clauses)

#         query = f'''
#             SELECT * FROM bill_of_lading
#             WHERE {where_sql}
#             ORDER BY id DESC
#         '''
#         print("QUERY:", query)
#         print("PARAMS:", params)
#         if params:
#             cur.execute(query, tuple(params))
#         else:
#             cur.execute(query)
#         rows = cur.fetchall()
#         columns = [desc[0] for desc in cur.description]
#         bills = []
#         for row in rows:
#             bill_dict = dict(zip(columns, row))
#             bills.append(bill_dict)

#         return jsonify({'bills': bills, 'total': len(bills)})
#     except Exception as e:
#         print("❌ ERROR in awaiting_bank_in:", str(e))
#         import traceback
#         traceback.print_exc()
#         return jsonify({'error': 'Internal server error'}), 500
#     finally:
#         try:
#             cur.close()
#             conn.close()
#         except:
#             pass




@app.route('/api/request_username', methods=['POST'])
def request_username():
    data = request.get_json()
    email = data.get('email')

    if not email:
        return jsonify({'error': 'Email is required'}), 400

    conn = get_db_conn()
    cur = conn.cursor()

    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("SELECT username, customer_email FROM users")
    users = cur.fetchall()
    cur.close()
    conn.close()

    username = None
    for row in users:
        db_username, encrypted_email = row
        try:
            decrypted_email = decrypt_sensitive_data(encrypted_email)
            decrypted_email = decrypt_sensitive_data(encrypted_email)
            if decrypted_email == email:
                username = db_username
                break
        except Exception:
            continue

    if not username:
        return jsonify({'error': 'No user found with this email'}), 404

    subject = "Your Username Recovery Request"
    body = f"Hi,\n\nYour username is: {username}\n\nIf you did not request this, please ignore this email.\n\nThanks,\nSupport Team"

    try:
        send_simple_email(email, subject, body)
        return jsonify({'message': 'Username sent to your email'}), 200
    except Exception as e:
        return jsonify({'error': f'Email failed: {str(e)}'}), 500

def notify_new_user():
    data = request.get_json()
    customer_username = data.get('username')  # from frontend it's still called 'username'
    email = data.get('email')
    role = data.get('role')

    # Replace with your actual admin email
    admin_email = 'ray6330099@gmail.com'
    subject = f"📬 New User Registration: {customer_username}"
    body = f"""Hi Admin,

A new user has just registered on the system.

Username: {customer_username}
Email: {email}
Role: {role}

You can log in to review and approve the user if necessary.

Best regards,
Your System
"""
    try:
        send_simple_email(admin_email, subject, body)
        return jsonify({'message': 'Notification email sent'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.errorhandler(404)
def not_found(e):
    return '<h1>404 - Page Not Found</h1><p>Sorry, the page you are looking for does not exist.</p>', 404

@app.errorhandler(500)
def internal_error(e):
    app.logger.error(f'500 error: {request.url} - {e}')
    return '<h1>500 - Internal Server Error</h1><p>Sorry, something went wrong on our end. Please try again later.</p>', 500

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)