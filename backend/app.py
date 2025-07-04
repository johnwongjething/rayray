import json
from flask import Flask, request, jsonify, send_from_directory, make_response, redirect
from flask_cors import CORS, cross_origin
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime, timedelta
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
import pytz
from werkzeug.middleware.proxy_fix import ProxyFix
from dateutil import parser
from flask_wtf import CSRFProtect
import logging
from extract_fields import extract_fields
from werkzeug.utils import secure_filename

load_dotenv()

app = Flask(__name__)
csrf = CSRFProtect(app)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(16))
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

# --- Security Enhancements ---
# Secure session cookies
app.config['SESSION_COOKIE_SECURE'] = True  # Only send cookies over HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevent JS access to cookies
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Prevent CSRF in most cases

# Set HTTP security headers
@app.after_request
def set_security_headers(response):
    response.headers['Content-Security-Policy'] = "default-src 'self' https://terryraylogicticsco.xyz https://www.terryraylogicticsco.xyz; script-src 'self'; object-src 'none'; frame-ancestors 'none';"
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=()'
    return response

# CORS configuration
allowed_origins = ['http://localhost:3000', 'https://terryraylogicticsco.xyz', 'https://www.terryraylogicticsco.xyz']
env_origins = os.getenv('ALLOWED_ORIGINS', '').split(',')
if env_origins and env_origins[0]:
    allowed_origins.extend([origin.strip() for origin in env_origins])
CORS(app, origins=allowed_origins, supports_credentials=True)

# Register blueprints
from payment_webhook import payment_webhook
from payment_link import payment_link
app.register_blueprint(payment_webhook, url_prefix='/api/webhook')
app.register_blueprint(payment_link)

# JWT configuration
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'change-this-in-production')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'pdf'}
jwt = JWTManager(app)

# Rate limiting
is_development = os.getenv('FLASK_ENV', 'development') == 'development'
limiter = Limiter(get_remote_address, app=app, default_limits=["200 per day", "50 per hour"] if not is_development else ["1000 per day", "100 per hour"])

# Custom error handler for rate limiting
@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({'error': 'Too many requests. Please wait before trying again.', 'retry_after': getattr(e, 'retry_after', 3600)}), 429

# HTTPS enforcement in production
if os.getenv('FLASK_ENV') == 'production':
    @app.before_request
    def enforce_https():
        if not request.is_secure and request.headers.get('X-Forwarded-Proto', 'http') != 'https':
            url = request.url.replace('http://', 'https://', 1)
            return redirect(url, code=301)

# Encryption
encryption_key = os.environ.get('ENCRYPTION_KEY')
if not encryption_key:
    encryption_key = Fernet.generate_key().decode()
    print(f"Generated encryption key: {encryption_key}. Add to .env as ENCRYPTION_KEY.")
fernet = Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)

# Security helper functions
def validate_password(password):
    return (len(password) >= 8 and any(c.isupper() for c in password) and
            any(c.islower() for c in password) and any(c.isdigit() for c in password) and
            any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)), "Password must meet complexity requirements"

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def sanitize_filename(filename):
    return secure_filename(filename)

def encrypt_sensitive_data(data):
    return fernet.encrypt(data.encode()).decode() if data and isinstance(data, str) else data

def decrypt_sensitive_data(encrypted_data):
    return fernet.decrypt(encrypted_data.encode()).decode() if encrypted_data and encrypted_data.startswith('gAAAAA') else encrypted_data

def get_hk_date_range(search_date_str):
    hk_tz = pytz.timezone('Asia/Hong_Kong')
    search_date = datetime.strptime(search_date_str, '%Y-%m-%d').replace(tzinfo=hk_tz)
    next_date = search_date + timedelta(days=1)
    return search_date, next_date

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('app')

# Ensure upload folder exists
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/', methods=['GET'])
@limiter.exempt
def root():
    return jsonify({
        'message': 'Terry Ray Logistics Shipping System API',
        'version': '1.0.0',
        'status': 'running',
        'endpoints': {'health': '/health', 'api_base': '/api', 'documentation': 'Check the API endpoints for more information'}
    }), 200

@app.route('/health', methods=['GET'])
@limiter.exempt
def health_check():
    try:
        conn = get_db_conn()
        conn.close()
        return jsonify({'status': 'healthy', 'database': 'connected', 'timestamp': datetime.now(pytz.timezone('Asia/Hong_Kong')).isoformat()}), 200
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({'status': 'unhealthy', 'error': str(e), 'timestamp': datetime.now(pytz.timezone('Asia/Hong_Kong')).isoformat()}), 503

@app.route('/api/register', methods=['POST'])
@limiter.limit("50 per hour" if is_development else "20 per hour")
@csrf.exempt
def register():
    data = request.get_json()
    required = ['username', 'password', 'role', 'customer_name', 'customer_email', 'customer_phone']
    if not all(k in data for k in required):
        return jsonify({'error': 'Missing fields'}), 400
    is_valid, message = validate_password(data['password'])
    if not is_valid:
        return jsonify({'error': message}), 400
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (username, password_hash, role, customer_name, customer_email, customer_phone) VALUES (%s, %s, %s, %s, %s, %s)",
            (data['username'], generate_password_hash(data['password']), data['role'], data['customer_name'],
             encrypt_sensitive_data(data['customer_email']), encrypt_sensitive_data(data['customer_phone']))
        )
        conn.commit()
        logger.info(f"New user registered: {data['username']}")
        cur.close()
        conn.close()
        return jsonify({'message': 'Registration submitted, waiting for approval.'})
    except Exception as e:
        logger.error(f"Registration failed: {str(e)}")
        return jsonify({'error': str(e)}), 400

@app.route('/api/login', methods=['POST'])
@limiter.limit("5 per minute")
@csrf.exempt
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("SELECT id, password_hash, role, approved, customer_name, customer_email, customer_phone FROM users WHERE username=%s", (username,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        if not user or not check_password_hash(user[1], password) or not user[3]:
            logger.warning(f"Login failed for {username}")
            return jsonify({'error': 'Invalid credentials or unapproved user'}), 401
        access_token = create_access_token(identity=json.dumps({'id': user[0], 'role': user[2], 'username': username}))
        logger.info(f"Login successful for {username}")
        return jsonify({
            "access_token": access_token,
            "customer_name": user[4],
            "customer_email": decrypt_sensitive_data(user[5]),
            "customer_phone": decrypt_sensitive_data(user[6]),
            'role': user[2],
            'username': username
        }), 200
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/approve_user/<int:user_id>', methods=['POST'])
@jwt_required()
def approve_user(user_id):
    user = json.loads(get_jwt_identity())
    if user['role'] not in ['staff', 'admin']:
        return jsonify({'error': 'Unauthorized'}), 403
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("UPDATE users SET approved=TRUE WHERE id=%s", (user_id,))
        cur.execute("SELECT customer_email, customer_name FROM users WHERE id=%s", (user_id,))
        row = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        if row:
            decrypted_email = decrypt_sensitive_data(row[0]) if row[0] else ''
            if decrypted_email:
                send_simple_email(decrypted_email, "Registration Approved", f"Dear {row[1]}, your account is approved.")
        return jsonify({'message': 'User approved'})
    except Exception as e:
        logger.error(f"Approve user failed: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/unapproved_users', methods=['GET'])
@jwt_required()
def get_unapproved_users():
    user = json.loads(get_jwt_identity())
    if user['role'] not in ['staff', 'admin']:
        return jsonify({'error': 'Unauthorized'}), 403
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("SELECT id, username, customer_name, customer_email, customer_phone, role FROM users WHERE approved = FALSE")
        users = [{'id': row[0], 'username': row[1], 'customer_name': row[2], 'customer_email': decrypt_sensitive_data(row[3]),
                  'customer_phone': decrypt_sensitive_data(row[4]), 'role': row[5]} for row in cur.fetchall()]
        cur.close()
        conn.close()
        return jsonify(users)
    except Exception as e:
        logger.error(f"Get unapproved users failed: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats/files_by_date')
@jwt_required()
def files_by_date():
    user = json.loads(get_jwt_identity())
    if user['role'] != 'staff':
        return jsonify({'error': 'Unauthorized'}), 403
    query_date = request.args.get('date')
    start_date, end_date = get_hk_date_range(query_date)
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM bill_of_lading WHERE created_at >= %s AND created_at < %s", (start_date, end_date))
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return jsonify({'files_created': count})
    except Exception as e:
        logger.error(f"Files by date failed: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats/completed_today')
@jwt_required()
def completed_today():
    user = json.loads(get_jwt_identity())
    if user['role'] != 'staff':
        return jsonify({'error': 'Unauthorized'}), 403
    hk_now = datetime.now(pytz.timezone('Asia/Hong_Kong'))
    today = hk_now.date().isoformat()
    start_date, end_date = get_hk_date_range(today)
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM bill_of_lading WHERE status='Paid and CTN Valid' AND completed_at >= %s AND completed_at < %s", (start_date, end_date))
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return jsonify({'completed_today': count})
    except Exception as e:
        logger.error(f"Completed today failed: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats/payments_by_date')
@jwt_required()
def payments_by_date():
    user = json.loads(get_jwt_identity())
    if user['role'] != 'staff':
        return jsonify({'error': 'Unauthorized'}), 403
    query_date = request.args.get('date')
    start_date, end_date = get_hk_date_range(query_date)
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(SUM(service_fee), 0) FROM bill_of_lading WHERE created_at >= %s AND created_at < %s", (start_date, end_date))
        total = cur.fetchone()[0]
        cur.close()
        conn.close()
        return jsonify({'payments_received': float(total)})
    except Exception as e:
        logger.error(f"Payments by date failed: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats/bills_by_date')
@jwt_required()
def bills_by_date():
    user = json.loads(get_jwt_identity())
    if user['role'] != 'staff':
        return jsonify({'error': 'Unauthorized'}), 403
    query_date = request.args.get('date')
    start_date, end_date = get_hk_date_range(query_date)
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT COUNT(*) as total_entries, COALESCE(SUM(ctn_fee), 0) as total_ctn_fee, COALESCE(SUM(service_fee), 0) as total_service_fee
            FROM bill_of_lading WHERE created_at >= %s AND created_at < %s
        """, (start_date, end_date))
        summary = cur.fetchone()
        cur.execute("""
            SELECT id, customer_name, customer_email, ctn_fee, service_fee, COALESCE(ctn_fee + service_fee, 0) as total, created_at
            FROM bill_of_lading WHERE created_at >= %s AND created_at < %s ORDER BY created_at DESC
        """, (start_date, end_date))
        entries = [dict(zip([desc[0] for desc in cur.description], row)) for row in cur.fetchall()]
        cur.close()
        conn.close()
        return jsonify({
            'summary': {'total_entries': summary[0], 'total_ctn_fee': float(summary[1]), 'total_service_fee': float(summary[2])},
            'entries': entries
        })
    except Exception as e:
        logger.error(f"Bills by date failed: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/upload', methods=['POST'])
@jwt_required()
@csrf.exempt
def upload():
    user = json.loads(get_jwt_identity())
    try:
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        bill_pdfs = request.files.getlist('bill_pdf')
        invoice_pdf = request.files.get('invoice_pdf')
        packing_pdf = request.files.get('packing_pdf')
        if not all([name, email, phone]) or not any([bill_pdfs, invoice_pdf, packing_pdf]):
            return jsonify({'error': 'Missing required fields or files'}), 400
        def save_file(file, label):
            if file and allowed_file(file.filename):
                now_str = datetime.now(pytz.timezone('Asia/Hong_Kong')).strftime('%Y-%m-%d_%H%M%S')
                filename = f"{now_str}_{label}_{sanitize_filename(file.filename)}"
                file.save(os.path.join(UPLOAD_FOLDER, filename))
                return filename
            return None
        customer_invoice = save_file(invoice_pdf, 'invoice')
        customer_packing_list = save_file(packing_pdf, 'packing')
        uploaded_count = 0
        results = []
        hk_now = datetime.now(pytz.timezone('Asia/Hong_Kong')).isoformat()
        for bill_pdf in bill_pdfs:
            pdf_filename = save_file(bill_pdf, 'bill')
            fields = extract_fields(os.path.join(UPLOAD_FOLDER, pdf_filename)) if pdf_filename else {}
            conn = get_db_conn()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO bill_of_lading (customer_name, customer_email, customer_phone, pdf_filename, ocr_text, shipper, consignee,
                port_of_loading, port_of_discharge, bl_number, container_numbers, flight_or_vessel, product_description, status,
                customer_username, created_at, customer_invoice, customer_packing_list)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (name, encrypt_sensitive_data(email), encrypt_sensitive_data(phone), pdf_filename, json.dumps(fields),
                  fields.get('shipper', ''), fields.get('consignee', ''), fields.get('port_of_loading', ''),
                  fields.get('port_of_discharge', ''), fields.get('bl_number', ''), fields.get('container_numbers', ''),
                  fields.get('flight_or_vessel', ''), fields.get('product_description', ''), 'Pending', user['username'], hk_now,
                  customer_invoice, customer_packing_list))
            conn.commit()
            cur.close()
            conn.close()
            uploaded_count += 1
            if email:
                send_simple_email(email, "Bill Received", f"Dear {name}, we received your bill. Our team will contact you within 24 hours.")
        return jsonify({'message': f'Upload successful! {uploaded_count} bill(s) uploaded.'})
    except Exception as e:
        logger.error(f"Upload failed: {str(e)}")
        return jsonify({'error': str(e)}), 400

@app.route('/api/bills', methods=['GET'])
def get_bills():
    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('page_size', 50))
    offset = (page - 1) * page_size
    bl_number = request.args.get('bl_number')
    status = request.args.get('status')
    date = request.args.get('date')
    try:
        conn = get_db_conn()
        cur = conn.cursor()
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
        where_sql = ' WHERE ' + ' AND '.join(where_clauses) if where_clauses else ''
        cur.execute(f'SELECT COUNT(*) FROM bill_of_lading{where_sql}', tuple(params))
        total_count = cur.fetchone()[0]
        cur.execute(f'''
            SELECT id, customer_name, customer_email, customer_phone, pdf_filename, shipper, consignee, port_of_loading, port_of_discharge, bl_number,
            container_numbers, flight_or_vessel, product_description, service_fee, ctn_fee, payment_link, receipt_filename, status, invoice_filename,
            unique_number, created_at, receipt_uploaded_at, customer_username, customer_invoice, customer_packing_list
            FROM bill_of_lading{where_sql} ORDER BY id DESC LIMIT %s OFFSET %s
        ''', tuple(params) + (page_size, offset))
        bills = []
        for row in cur.fetchall():
            bill = dict(zip([desc[0] for desc in cur.description], row))
            bill['customer_email'] = decrypt_sensitive_data(bill['customer_email']) if bill['customer_email'] else ''
            bill['customer_phone'] = decrypt_sensitive_data(bill['customer_phone']) if bill['customer_phone'] else ''
            bills.append(bill)
        cur.close()
        conn.close()
        return jsonify({'bills': bills, 'total': total_count, 'page': page, 'page_size': page_size})
    except Exception as e:
        logger.error(f"Get bills failed: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    try:
        return send_from_directory(UPLOAD_FOLDER, filename)
    except Exception as e:
        logger.error(f"File serve failed: {str(e)}")
        return jsonify({'error': 'File not found'}), 404

@app.route('/api/bill/<int:bill_id>/upload_receipt', methods=['POST'])
def upload_receipt(bill_id):
    if 'receipt' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    receipt = request.files['receipt']
    if not allowed_file(receipt.filename):
        return jsonify({'error': 'Invalid file type'}), 400
    filename = f"receipt_{bill_id}_{sanitize_filename(receipt.filename)}"
    receipt.save(os.path.join(UPLOAD_FOLDER, filename))
    hk_now = datetime.now(pytz.timezone('Asia/Hong_Kong')).isoformat()
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("UPDATE bill_of_lading SET receipt_filename=%s, status=%s, receipt_uploaded_at=%s WHERE id=%s",
                   (filename, 'Awaiting Bank In', hk_now, bill_id))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'message': 'Receipt uploaded'})
    except Exception as e:
        logger.error(f"Receipt upload failed: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/bill/<int:bill_id>', methods=['GET', 'PUT', 'DELETE'])
@jwt_required()
def bill_detail(bill_id):
    user = json.loads(get_jwt_identity())
    if request.method == 'GET':
        try:
            conn = get_db_conn()
            cur = conn.cursor()
            cur.execute("SELECT * FROM bill_of_lading WHERE id=%s", (bill_id,))
            bill_row = cur.fetchone()
            if not bill_row:
                cur.close()
                conn.close()
                return jsonify({'error': 'Bill not found'}), 404
            bill = dict(zip([desc[0] for desc in cur.description], bill_row))
            bill['customer_email'] = decrypt_sensitive_data(bill['customer_email']) if bill['customer_email'] else ''
            bill['customer_phone'] = decrypt_sensitive_data(bill['customer_phone']) if bill['customer_phone'] else ''
            cur.close()
            conn.close()
            return jsonify(bill)
        except Exception as e:
            logger.error(f"Get bill failed: {str(e)}")
            return jsonify({'error': str(e)}), 500
    elif request.method == 'PUT':
        if user['role'] not in ['staff', 'admin']:
            return jsonify({'error': 'Unauthorized'}), 403
        data = request.get_json()
        try:
            conn = get_db_conn()
            cur = conn.cursor()
            cur.execute("SELECT * FROM bill_of_lading WHERE id=%s", (bill_id,))
            bill_row = cur.fetchone()
            if not bill_row:
                cur.close()
                conn.close()
                return jsonify({'error': 'Bill not found'}), 404
            updatable_fields = ['customer_name', 'customer_email', 'customer_phone', 'bl_number', 'shipper', 'consignee',
                              'port_of_loading', 'port_of_discharge', 'container_numbers', 'service_fee', 'ctn_fee',
                              'payment_link', 'unique_number', 'flight_or_vessel', 'product_description', 'payment_method',
                              'payment_status', 'reserve_status']
            update_fields = []
            update_values = []
            for field in updatable_fields:
                if field in data and data[field] is not None:
                    if field in ['customer_email', 'customer_phone']:
                        update_fields.append(f"{field}=%s")
                        update_values.append(encrypt_sensitive_data(data[field]))
                    else:
                        update_fields.append(f"{field}=%s")
                        update_values.append(data[field])
            if update_fields:
                update_values.append(bill_id)
                cur.execute(f"UPDATE bill_of_lading SET {', '.join(update_fields)} WHERE id=%s", tuple(update_values))
                conn.commit()
            cur.execute("SELECT * FROM bill_of_lading WHERE id=%s", (bill_id,))
            bill_row = cur.fetchone()
            bill = dict(zip([desc[0] for desc in cur.description], bill_row))
            bill['customer_email'] = decrypt_sensitive_data(bill['customer_email']) if bill['customer_email'] else ''
            bill['customer_phone'] = decrypt_sensitive_data(bill['customer_phone']) if bill['customer_phone'] else ''
            try:
                customer = {'name': bill['customer_name'], 'email': bill['customer_email'], 'phone': bill['customer_phone']}
                invoice_filename = generate_invoice_pdf(customer, bill, bill.get('service_fee'), bill.get('ctn_fee'), bill.get('payment_link'))
                bill['invoice_filename'] = invoice_filename
            except Exception as e:
                logger.error(f"Invoice generation failed: {str(e)}")
            cur.close()
            conn.close()
            return jsonify(bill)
        except Exception as e:
            logger.error(f"Update bill failed: {str(e)}")
            return jsonify({'error': str(e)}), 500
    elif request.method == 'DELETE':
        if user['role'] not in ['staff', 'admin']:
            return jsonify({'error': 'Unauthorized'}), 403
        try:
            conn = get_db_conn()
            cur = conn.cursor()
            cur.execute("DELETE FROM bill_of_lading WHERE id=%s", (bill_id,))
            conn.commit()
            cur.close()
            conn.close()
            return jsonify({'message': 'Bill deleted'})
        except Exception as e:
            logger.error(f"Delete bill failed: {str(e)}")
            return jsonify({'error': str(e)}), 500

@app.route('/api/bill/<int:bill_id>/settle_reserve', methods=['POST'])
@jwt_required()
def settle_reserve(bill_id):
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("SELECT id FROM bill_of_lading WHERE id = %s", (bill_id,))
        if not cur.fetchone():
            return jsonify({"error": "Bill not found"}), 404
        cur.execute("UPDATE bill_of_lading SET reserve_status = 'Reserve Settled' WHERE id = %s", (bill_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Reserve marked as settled"}), 200
    except Exception as e:
        logger.error(f"Settle reserve failed: {str(e)}")
        return jsonify({"error": "Failed to settle reserve"}), 500

@app.route('/api/bill/<int:bill_id>/complete', methods=['POST'])
def complete_bill(bill_id):
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        hk_now = datetime.now(pytz.timezone('Asia/Hong_Kong'))
        cur.execute("SELECT payment_method FROM bill_of_lading WHERE id=%s", (bill_id,))
        row = cur.fetchone()
        if row and row[0] and row[0].lower() == 'allinpay':
            cur.execute("UPDATE bill_of_lading SET status=%s, payment_status=%s, completed_at=%s WHERE id=%s",
                       ('Paid and CTN Valid', 'Paid 100%', hk_now, bill_id))
        else:
            cur.execute("UPDATE bill_of_lading SET status=%s, completed_at=%s WHERE id=%s",
                       ('Paid and CTN Valid', hk_now, bill_id))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'message': 'Bill marked as completed'})
    except Exception as e:
        logger.error(f"Complete bill failed: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/search_bills', methods=['POST'])
@jwt_required()
@csrf.exempt
def search_bills():
    data = request.get_json()
    params = {'customer_name': data.get('customer_name', ''),
              'customer_id': data.get('customer_id', ''),
              'created_at': data.get('created_at', ''),
              'bl_number': data.get('bl_number', ''),
              'unique_number': data.get('unique_number', ''),
              'username': data.get('username', '')}
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        query = "SELECT id, customer_name, customer_email, customer_phone, pdf_filename, shipper, consignee, port_of_loading, port_of_discharge, bl_number, container_numbers, service_fee, ctn_fee, payment_link, receipt_filename, status, invoice_filename, unique_number, created_at, receipt_uploaded_at, customer_username, customer_invoice, customer_packing_list FROM bill_of_lading WHERE 1=1"
        query_params = []
        if params['customer_name']:
            query += ' AND customer_name ILIKE %s'
            query_params.append(f'%{params["customer_name"]}%')
        if params['customer_id']:
            try:
                int(params['customer_id'])
                query += ' AND id = %s'
                query_params.append(params['customer_id'])
            except ValueError:
                query += ' AND customer_name ILIKE %s'
                query_params.append(f'%{params["customer_id"]}%')
        if params['created_at']:
            start_date, end_date = get_hk_date_range(params['created_at'])
            query += ' AND created_at >= %s AND created_at < %s'
            query_params.extend([start_date, end_date])
        if params['bl_number']:
            query += ' AND bl_number ILIKE %s'
            query_params.append(f'%{params["bl_number"]}%')
        if params['unique_number']:
            query += ' AND unique_number = %s'
            query_params.append(params['unique_number'])
        if params['username']:
            query += ' AND customer_username = %s'
            query_params.append(params['username'])
        query += ' ORDER BY id DESC'
        cur.execute(query, tuple(query_params))
        bills = []
        for row in cur.fetchall():
            bill = dict(zip([desc[0] for desc in cur.description], row))
            bill['customer_email'] = decrypt_sensitive_data(bill['customer_email']) if bill['customer_email'] else ''
            bill['customer_phone'] = decrypt_sensitive_data(bill['customer_phone']) if bill['customer_phone'] else ''
            bills.append(bill)
        cur.close()
        conn.close()
        return jsonify(bills)
    except Exception as e:
        logger.error(f"Search bills failed: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/bill/<int:bill_id>/unique_number', methods=['POST'])
def set_unique_number(bill_id):
    data = request.get_json()
    unique_number = data.get('unique_number')
    if not unique_number:
        return jsonify({'error': 'Missing unique number'}), 400
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("UPDATE bill_of_lading SET unique_number=%s WHERE id=%s", (unique_number, bill_id))
        conn.commit()
        cur.execute("SELECT customer_email, customer_name FROM bill_of_lading WHERE id=%s", (bill_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            send_unique_number_email(decrypt_sensitive_data(row[0]) if row[0] else '', row[1], unique_number)
        return jsonify({'message': 'Unique number saved and email sent'})
    except Exception as e:
        logger.error(f"Set unique number failed: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/send_unique_number_email', methods=['POST'])
def api_send_unique_number_email():
    try:
        data = request.get_json()
        if not data or not all(k in data for k in ['to_email', 'subject', 'body', 'bill_id']):
            return jsonify({'error': 'Missing required fields'}), 400
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("SELECT id FROM bill_of_lading WHERE id=%s", (data['bill_id'],))
        if not cur.fetchone():
            return jsonify({'error': 'Bill not found'}), 404
        send_unique_number_email(data['to_email'], data['subject'], data['body'])
        cur.close()
        conn.close()
        return jsonify({'message': 'Unique number email sent successfully'})
    except Exception as e:
        logger.error(f"Send unique number email failed: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/me', methods=['GET'])
@jwt_required()
def get_me():
    user = json.loads(get_jwt_identity())
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("SELECT customer_name, customer_email, customer_phone FROM users WHERE username=%s", (user['username'],))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            return jsonify({
                "customer_name": row[0],
                "customer_email": decrypt_sensitive_data(row[1]) if row[1] else '',
                "customer_phone": decrypt_sensitive_data(row[2]) if row[2] else ''
            })
        return jsonify({"error": "User not found"}), 404
    except Exception as e:
        logger.error(f"Get me failed: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/contact', methods=['POST'])
def contact():
    data = request.get_json()
    if not all(k in data for k in ['name', 'email', 'message']):
        return jsonify({'error': 'Missing fields'}), 400
    try:
        success = send_contact_email(data['name'], data['email'], data['message'])
        return jsonify({'message': 'Message sent successfully!'}) if success else jsonify({'error': 'Failed to send email'}), 500
    except Exception as e:
        logger.error(f"Contact failed: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats/summary')
@jwt_required()
def stats_summary():
    user = json.loads(get_jwt_identity())
    if user['role'] not in ['staff', 'admin']:
        return jsonify({'error': 'Unauthorized'}), 403
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM bill_of_lading")
        total_bills = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM bill_of_lading WHERE status = 'Paid and CTN Valid'")
        completed_bills = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM bill_of_lading WHERE status IN ('Pending', 'Invoice Sent', 'Awaiting Bank In')")
        pending_bills = cur.fetchone()[0]
        cur.execute("SELECT COALESCE(SUM(ctn_fee + service_fee), 0) FROM bill_of_lading")
        total_invoice_amount = float(cur.fetchone()[0])
        cur.execute("""
            SELECT COALESCE(SUM(CASE WHEN payment_method != 'Allinpay' AND status = 'Paid and CTN Valid' THEN ctn_fee + service_fee
                WHEN payment_method = 'Allinpay' AND status = 'Paid and CTN Valid' AND reserve_status = 'Reserve Settled' THEN ctn_fee + service_fee
                WHEN payment_method = 'Allinpay' AND status = 'Paid and CTN Valid' AND reserve_status = 'Unsettled' THEN (ctn_fee * 0.85) + (service_fee * 0.85)
                ELSE 0 END), 0)
            FROM bill_of_lading
        """)
        total_payment_received = float(cur.fetchone()[0])
        cur.execute("SELECT COALESCE(SUM(service_fee + ctn_fee), 0) FROM bill_of_lading WHERE status IN ('Awaiting Bank In', 'Invoice Sent')")
        awaiting_payment = float(cur.fetchone()[0])
        cur.execute("SELECT COALESCE(SUM(reserve_amount), 0) FROM bill_of_lading WHERE LOWER(TRIM(reserve_status)) = 'unsettled'")
        unsettled_reserve = float(cur.fetchone()[0])
        total_payment_outstanding = awaiting_payment + unsettled_reserve
        cur.close()
        conn.close()
        return jsonify({
            'total_bills': total_bills,
            'completed_bills': completed_bills,
            'pending_bills': pending_bills,
            'total_invoice_amount': round(total_invoice_amount, 2),
            'total_payment_received': round(total_payment_received, 2),
            'total_payment_outstanding': round(total_payment_outstanding, 2)
        })
    except Exception as e:
        logger.error(f"Stats summary failed: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats/outstanding_bills')
@jwt_required()
def outstanding_bills():
    user = json.loads(get_jwt_identity())
    if user['role'] not in ['staff', 'admin']:
        return jsonify({'error': 'Unauthorized'}), 403
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, customer_name, bl_number, ctn_fee, service_fee, reserve_amount, payment_method, reserve_status, invoice_filename
            FROM bill_of_lading
            WHERE status IN ('Awaiting Bank In', 'Invoice Sent') OR (payment_method = 'Allinpay' AND LOWER(TRIM(reserve_status)) = 'unsettled')
        """)
        bills = []
        for row in cur.fetchall():
            bill = dict(zip([desc[0] for desc in cur.description], row))
            ctn_fee = float(bill.get('ctn_fee') or 0)
            service_fee = float(bill.get('service_fee') or 0)
            payment_method = str(bill.get('payment_method') or '').strip().lower()
            reserve_status = str(bill.get('reserve_status') or '').strip().lower()
            outstanding_amount = round(ctn_fee + service_fee, 2) if payment_method != 'allinpay' or reserve_status != 'unsettled' else round(ctn_fee * 0.15 + service_fee * 0.15, 2)
            bill['outstanding_amount'] = outstanding_amount
            bills.append(bill)
        cur.close()
        conn.close()
        return jsonify(bills)
    except Exception as e:
        logger.error(f"Outstanding bills failed: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/request_password_reset', methods=['POST'])
def request_password_reset():
    data = request.get_json()
    email = data.get('email')
    if not email:
        return jsonify({'error': 'Email required'}), 400
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("SELECT id, customer_name, customer_email FROM users")
        user = next((row for row in cur.fetchall() if decrypt_sensitive_data(row[2]) == email), None)
        cur.close()
        conn.close()
        if not user:
            return jsonify({'message': 'If this email is registered, a reset link will be sent.'}), 200
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(pytz.timezone('Asia/Hong_Kong')) + timedelta(hours=1)
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("INSERT INTO password_reset_tokens (user_id, token, expires_at) VALUES (%s, %s, %s)", (user[0], token, expires_at))
        conn.commit()
        cur.close()
        conn.close()
        reset_link = f"https://www.terryraylogicticsco.xyz/reset-password/{token}"
        send_simple_email(email, "Password Reset Request", f"Dear {user[1]}, click here to reset: {reset_link}\nExpires in 1 hour.")
        return jsonify({'message': 'If this email is registered, a reset link will be sent.'})
    except Exception as e:
        logger.error(f"Password reset request failed: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/reset_password/<token>', methods=['POST'])
def reset_password(token):
    data = request.get_json()
    new_password = data.get('password')
    if not new_password:
        return jsonify({'error': 'Password required'}), 400
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("SELECT user_id, expires_at FROM password_reset_tokens WHERE token=%s", (token,))
        row = cur.fetchone()
        if not row or datetime.now(pytz.timezone('Asia/Hong_Kong')) > row[1]:
            if row:
                cur.execute("DELETE FROM password_reset_tokens WHERE token=%s", (token,))
                conn.commit()
            cur.close()
            conn.close()
            return jsonify({'error': 'Invalid or expired token'}), 400
        cur.execute("UPDATE users SET password_hash=%s WHERE id=%s", (generate_password_hash(new_password), row[0]))
        cur.execute("DELETE FROM password_reset_tokens WHERE token=%s", (token,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'message': 'Password has been reset successfully.'})
    except Exception as e:
        logger.error(f"Reset password failed: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/send_invoice_email', methods=['POST'])
@jwt_required()
def send_invoice_email_endpoint():
    try:
        data = request.get_json()
        if not all(k in data for k in ['to_email', 'subject', 'body', 'pdf_url', 'bill_id']):
            return jsonify({'error': 'Missing required fields'}), 400
        pdf_filename = os.path.basename(data['pdf_url'])
        pdf_path = os.path.join(os.path.dirname(__file__), 'uploads', pdf_filename)
        success = send_invoice_email(data['to_email'], data['subject'], data['body'], pdf_path)
        if success:
            conn = get_db_conn()
            cur = conn.cursor()
            cur.execute("UPDATE bill_of_lading SET status=%s WHERE id=%s", ("Invoice Sent", data['bill_id']))
            conn.commit()
            cur.close()
            conn.close()
            return jsonify({'message': 'Email sent successfully'})
        return jsonify({'error': 'Failed to send email'}), 500
    except Exception as e:
        logger.error(f"Send invoice email failed: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/account_bills', methods=['GET'])
def account_bills():
    completed_at = request.args.get('completed_at')
    bl_number = request.args.get('bl_number')
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        query = """
            SELECT id, customer_name, customer_email, customer_phone, pdf_filename, shipper, consignee, port_of_loading, port_of_discharge, bl_number,
            container_numbers, service_fee, ctn_fee, payment_link, receipt_filename, status, invoice_filename, unique_number, created_at, receipt_uploaded_at,
            completed_at, allinpay_85_received_at, customer_username, customer_invoice, customer_packing_list, payment_method, payment_status, reserve_status
            FROM bill_of_lading WHERE status = 'Paid and CTN Valid'
        """
        params = []
        if completed_at:
            start_date, end_date = get_hk_date_range(completed_at)
            query += " AND ((payment_method = 'Allinpay' AND allinpay_85_received_at >= %s AND allinpay_85_received_at < %s) OR (payment_method = 'Allinpay' AND completed_at >= %s AND completed_at < %s) OR (payment_method != 'Allinpay' AND completed_at >= %s AND completed_at < %s))"
            params.extend([start_date, end_date, start_date, end_date, start_date, end_date])
        if bl_number:
            query += " AND bl_number ILIKE %s"
            params.append(f'%{bl_number}%')
        query += " ORDER BY id DESC"
        cur.execute(query, tuple(params))
        bills = []
        totals = {'bank_ctn': 0, 'bank_service': 0, 'allinpay_85_ctn': 0, 'allinpay_85_service': 0, 'reserve_ctn': 0, 'reserve_service': 0}
        for row in cur.fetchall():
            bill = dict(zip([desc[0] for desc in cur.description], row))
            bill['customer_email'] = decrypt_sensitive_data(bill['customer_email']) if bill['customer_email'] else ''
            bill['customer_phone'] = decrypt_sensitive_data(bill['customer_phone']) if bill['customer_phone'] else ''
            ctn_fee = float(bill.get('ctn_fee') or 0)
            service_fee = float(bill.get('service_fee') or 0)
            bill['display_ctn_fee'] = ctn_fee
            bill['display_service_fee'] = service_fee
            if bill['payment_method'] == 'Allinpay':
                allinpay_85_dt = parser.parse(bill.get('allinpay_85_received_at')) if bill.get('allinpay_85_received_at') else None
                if allinpay_85_dt and completed_at and start_date <= allinpay_85_dt < end_date:
                    bill['display_ctn_fee'] = round(ctn_fee * 0.85, 2)
                    bill['display_service_fee'] = round(service_fee * 0.85, 2)
                    totals['allinpay_85_ctn'] += bill['display_ctn_fee']
                    totals['allinpay_85_service'] += bill['display_service_fee']
                elif bill['reserve_status'].lower() in ['settled', 'reserve settled'] and completed_at:
                    completed_dt = parser.parse(bill.get('completed_at')) if bill.get('completed_at') else None
                    if completed_dt and start_date <= completed_dt < end_date:
                        bill['display_ctn_fee'] = round(ctn_fee * 0.15, 2)
                        bill['display_service_fee'] = round(service_fee * 0.15, 2)
                        totals['reserve_ctn'] += bill['display_ctn_fee']
                        totals['reserve_service'] += bill['display_service_fee']
            elif completed_at:
                completed_dt = parser.parse(bill.get('completed_at')) if bill.get('completed_at') else None
                if completed_dt and start_date <= completed_dt < end_date:
                    totals['bank_ctn'] += ctn_fee
                    totals['bank_service'] += service_fee
            bills.append(bill)
        summary = {
            'totalEntries': len(bills),
            'totalCtnFee': round(sum(totals.values()), 2),
            'totalServiceFee': round(sum(totals.values()), 2),
            'bankTotal': round(totals['bank_ctn'] + totals['bank_service'], 2),
            'allinpay85Total': round(totals['allinpay_85_ctn'] + totals['allinpay_85_service'], 2),
            'reserveTotal': round(totals['reserve_ctn'] + totals['reserve_service'], 2)
        }
        cur.close()
        conn.close()
        return jsonify({'bills': bills, 'summary': summary})
    except Exception as e:
        logger.error(f"Account bills failed: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate_payment_link/<int:bill_id>', methods=['POST'])
def generate_payment_link(bill_id):
    try:
        payment_link = f"https://pay.example.com/link/{bill_id}"
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("UPDATE bill_of_lading SET payment_link = %s WHERE id = %s", (payment_link, bill_id))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"payment_link": payment_link})
    except Exception as e:
        logger.error(f"Generate payment link failed: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/bills/status/<status>', methods=['GET'])
def get_bills_by_status(status):
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, customer_name, customer_email, customer_phone, pdf_filename, shipper, consignee, port_of_loading, port_of_discharge, bl_number,
            container_numbers, flight_or_vessel, product_description, service_fee, ctn_fee, payment_link, receipt_filename, status, invoice_filename, unique_number, created_at, receipt_uploaded_at,
            customer_username, customer_invoice, completed_at, customer_packing_list
            FROM bill_of_lading WHERE status = %s ORDER BY id DESC
        """, (status,))
        bills = []
        for row in cur.fetchall():
            bill = dict(zip([desc[0] for desc in cur.description], row))
            bill['customer_email'] = decrypt_sensitive_data(bill['customer_email']) if bill['customer_email'] else ''
            bill['customer_phone'] = decrypt_sensitive_data(bill['customer_phone']) if bill['customer_phone'] else ''
            bills.append(bill)
        cur.close()
        conn.close()
        return jsonify(bills)
    except Exception as e:
        logger.error(f"Get bills by status failed: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/bills/awaiting_bank_in', methods=['GET'])
@jwt_required()
def get_awaiting_bank_in_bills():
    try:
        bl_number = request.args.get('bl_number', '').strip()
        conn = get_db_conn()
        cur = conn.cursor()
        query = """
            SELECT id, customer_name, customer_email, customer_phone, pdf_filename, shipper, consignee, port_of_loading, 
                   port_of_discharge, bl_number, container_numbers, service_fee, ctn_fee, payment_link, receipt_filename, 
                   status, invoice_filename, unique_number, created_at, receipt_uploaded_at, customer_username, 
                   customer_invoice, completed_at, customer_packing_list, payment_method, payment_status, reserve_status
            FROM bill_of_lading
            WHERE (status = 'Awaiting Bank In') OR (payment_method = 'Allinpay' AND payment_status = 'Paid 85%')
        """
        params = []
        if bl_number:
            query += " AND bl_number ILIKE %s"
            params.append(f'%{bl_number}%')
        query += " ORDER BY id DESC"
        cur.execute(query, tuple(params))
        bills = []
        for row in cur.fetchall():
            bill = dict(zip([desc[0] for desc in cur.description], row))
            bill['customer_email'] = decrypt_sensitive_data(bill['customer_email']) if bill['customer_email'] else ''
            bill['customer_phone'] = decrypt_sensitive_data(bill['customer_phone']) if bill['customer_phone'] else ''
            bills.append(bill)
        cur.close()
        conn.close()
        return jsonify({'bills': bills, 'total': len(bills)})
    except Exception as e:
        logger.error(f"Awaiting bank in failed: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/request_username', methods=['POST'])
def request_username():
    data = request.get_json()
    email = data.get('email')
    if not email:
        return jsonify({'error': 'Email is required'}), 400
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("SELECT username, customer_email FROM users")
        username = next((row[0] for row in cur.fetchall() if decrypt_sensitive_data(row[1]) == email), None)
        cur.close()
        conn.close()
        if not username:
            return jsonify({'error': 'No user found with this email'}), 404
        send_simple_email(email, "Your Username Recovery Request", f"Hi,\nYour username is: {username}\nIf you didn’t request this, ignore this email.\nThanks,\nSupport Team")
        return jsonify({'message': 'Username sent to your email'}), 200
    except Exception as e:
        logger.error(f"Request username failed: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/notify_new_user', methods=['POST'])
@csrf.exempt
def notify_new_user():
    data = request.get_json()
    if not all(k in data for k in ['username', 'email', 'role']):
        return jsonify({'error': 'Missing fields'}), 400
    try:
        send_simple_email('ray6330099@gmail.com', f"📬 New User Registration: {data['username']}",
                         f"Hi Admin,\nA new user has registered.\nUsername: {data['username']}\nEmail: {data['email']}\nRole: {data['role']}\nReview and approve if needed.\nBest regards,\nYour System")
        return jsonify({'message': 'Notification email sent'})
    except Exception as e:
        logger.error(f"Notify new user failed: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.errorhandler(404)
def not_found(e):
    logger.warning(f"404 error: {request.url}")
    return '<h1>404 - Page Not Found</h1><p>Sorry, the page you are looking for does not exist.</p>', 404

@app.errorhandler(500)
def internal_error(e):
    logger.error(f'500 error: {request.url} - {str(e)}')
    return '<h1>500 - Internal Server Error</h1><p>Sorry, something went wrong. Please try again later.</p>', 500

@app.route('/api/ping', methods=['GET'])
@limiter.exempt
def ping():
    return jsonify({'message': 'pong', 'timestamp': datetime.now(pytz.timezone('Asia/Hong_Kong')).isoformat()}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)