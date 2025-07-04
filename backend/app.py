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
env_origins = os.getenv('ALLOWED_ORIGINS', '').split(',')
if env_origins and env_origins[0]:
    allowed_origins.extend([origin.strip() for origin in env_origins])

CORS(app, origins=allowed_origins, supports_credentials=True)

# Initialize Rate Limiter with optimized settings for Render's 512MB RAM
is_development = os.getenv('FLASK_ENV') == 'development' or os.getenv('FLASK_DEBUG') == 'True'
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    storage_uri="memory://",  # In-memory storage for Render compatibility
    strategy="moving-window",
    default_limits=["1000 per day", "100 per hour"] if is_development else ["200 per day", "50 per hour"]
)

jwt = JWTManager(app)

from payment_webhook import payment_webhook
from payment_link import payment_link

app.register_blueprint(payment_webhook, url_prefix='/api/webhook')
app.register_blueprint(payment_link)

@app.route('/api/ping')
@limiter.limit("5 per minute")  # Added for testing rate limiting
def ping():
    return {"message": "pong"}, 200

app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'change-this-in-production')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'pdf'}

@app.route('/api/upload', methods=['POST'])
@limiter.limit("5 per hour")  # Limit file uploads
@jwt_required()  # Added to match token usage in UploadForm.js
def upload_file():
    try:
        if not any(key in request.files for key in ['bill_pdf', 'invoice_pdf', 'packing_pdf']):
            return jsonify({"error": "No file part"}), 400
        
        uploaded_files = {}
        for key in ['bill_pdf', 'invoice_pdf', 'packing_pdf']:
            if key in request.files:
                files = request.files.getlist(key)
                for file in files:
                    if file and file.filename.endswith('.pdf'):
                        filename = f"{key}_{secrets.token_hex(8)}_{file.filename}"
                        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                        uploaded_files[key] = uploaded_files.get(key, []) + [filename]
                    else:
                        return jsonify({"error": f"Invalid file type for {key}"}), 400
        
        return jsonify({"message": "Files uploaded", "filenames": uploaded_files}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
    where_sql = ' AND '.join(where_clauses) if where_clauses else ''

    count_query = f'SELECT COUNT(*) FROM bill_of_lading {where_sql}'
    cur.execute(count_query, tuple(params))
    total_count = cur.fetchone()[0]

    query = f'''
        SELECT id, customer_name, customer_email, customer_phone, pdf_filename, shipper, consignee, port_of_loading, port_of_discharge, bl_number, container_numbers,
               flight_or_vessel, product_description, service_fee, ctn_fee, payment_link, receipt_filename, status, invoice_filename, unique_number, created_at, receipt_uploaded_at, customer_username, customer_invoice, customer_packing_list
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
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/api/register', methods=['POST'])
@limiter.limit("50 per hour" if is_development else "20 per hour")
@cross_origin()
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
    
    is_valid, message = validate_password(password)
    if not is_valid:
        return jsonify({'error': message}), 400
    
    try:
        conn = get_db_conn()
        cur = conn.cursor()
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
@cross_origin()
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
    cur.execute("SELECT customer_email, customer_name FROM users WHERE id=%s", (user_id,))
    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    if row:
        customer_email, customer_name = row
        decrypted_email = decrypt_sensitive_data(customer_email) if customer_email else ''
        if decrypted_email:
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
    hk_now = datetime.now(pytz.timezone('Asia/Hong_Kong'))
    today = hk_now.date().isoformat()
    conn = get_db_conn()
    cur = conn.cursor()
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

@app.route('/api/bill/<int:bill_id>/upload_receipt', methods=['POST'])
def upload_receipt(bill_id):
    if 'receipt' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    receipt = request.files['receipt']
    filename = f"receipt_{bill_id}_{receipt.filename}"
    receipt_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
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
        updatable_fields = [
            'customer_name', 'customer_email', 'customer_phone', 'bl_number',
            'shipper', 'consignee', 'port_of_loading', 'port_of_discharge',
            'container_numbers', 'service_fee', 'ctn_fee', 'payment_link', 'unique_number',
            'flight_or_vessel', 'product_description',
            'payment_method', 'payment_status', 'reserve_status'
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
        cur.execute("SELECT * FROM bill_of_lading WHERE id=%s", (bill_id,))
        bill_row = cur.fetchone()
        columns = [desc[0] for desc in cur.description]
        bill = dict(zip(columns, bill_row))
        if bill.get('customer_email') is not None:
            bill['customer_email'] = decrypt_sensitive_data(bill['customer_email'])
        if bill.get('customer_phone') is not None:
            bill['customer_phone'] = decrypt_sensitive_data(bill['customer_phone'])
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
        cur.execute("SELECT id FROM bill_of_lading WHERE id = %s", (bill_id,))
        if not cur.fetchone():
            return jsonify({"error": "Bill not found"}), 404
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

@app.route('/api/bill/<int:bill_id>/complete', methods=['POST'])
def complete_bill(bill_id):
    conn = get_db_conn()
    cur = conn.cursor()
    hk_now = datetime.now(pytz.timezone('Asia/Hong_Kong'))
    cur.execute("SELECT payment_method FROM bill_of_lading WHERE id=%s", (bill_id,))
    row = cur.fetchone()
    if row and row[0] and row[0].lower() == 'allinpay':
        cur.execute("""
            UPDATE bill_of_lading
            SET status=%s, payment_status=%s, completed_at=%s
            WHERE id=%s
        """, ('Paid and CTN Valid', 'Paid 100%', hk_now, bill_id))
    else:
        cur.execute("""
            UPDATE bill_of_lading
            SET status=%s, completed_at=%s
            WHERE id=%s
        """, ('Paid and CTN Valid', hk_now, bill_id))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({'message': 'Bill marked as completed'})

@app.route('/api/search_bills', methods=['POST'])
@jwt_required()
def search_bills():
    data = request.get_json()
    customer_name = data.get('customer_name', '')
    customer_id = data.get('customer_id', '')
    created_at = data.get('created_at', '')
    bl_number = data.get('bl_number', '')
    unique_number = data.get('unique_number', '')
    username = data.get('username', '')
    
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
        try:
            int(customer_id)
            query += ' AND id = %s'
            params.append(customer_id)
        except ValueError:
            query += ' AND customer_name ILIKE %s'
            params.append(f'%{customer_id}%')
    
    if created_at:
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

    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE bill_of_lading
        SET unique_number=%s
        WHERE id=%s
    """, (unique_number, bill_id))
    conn.commit()

    cur.execute("SELECT customer_email, customer_name FROM bill_of_lading WHERE id=%s", (bill_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if row:
        customer_email, customer_name = row
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

        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("SELECT id FROM bill_of_lading WHERE id=%s", (bill_id,))
        if not cur.fetchone():
            return jsonify({'error': 'Bill not found'}), 404

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
    total_bills = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM bill_of_lading WHERE status = 'Paid and CTN Valid'")
    completed_bills = cur.fetchone()[0]

    cur.execute("""
    SELECT COUNT(*) 
    FROM bill_of_lading 
    WHERE status IN ('Pending', 'Invoice Sent', 'Awaiting Bank In')
""")
    pending_bills = cur.fetchone()[0]

    cur.execute("SELECT COALESCE(SUM(ctn_fee + service_fee), 0) FROM bill_of_lading")
    total_invoice_amount = float(cur.fetchone()[0] or 0)

    cur.execute("""
        SELECT COALESCE(SUM(
            CASE 
                WHEN payment_method != 'Allinpay' AND status = 'Paid and CTN Valid'
                    THEN ctn_fee + service_fee
                WHEN payment_method = 'Allinpay' AND status = 'Paid and CTN Valid' AND reserve_status = 'Reserve Settled'
                    THEN ctn_fee + service_fee
                WHEN payment_method = 'Allinpay' AND status = 'Paid and CTN Valid' AND reserve_status = 'Unsettled'
                    THEN (ctn_fee * 0.85) + (service_fee * 0.85)
                ELSE 0
            END
        ), 0)
        FROM bill_of_lading
    """)
    total_payment_received = float(cur.fetchone()[0] or 0)

    cur.execute("""
    SELECT COALESCE(SUM(service_fee + ctn_fee), 0)
    FROM bill_of_lading
    WHERE status IN ('Awaiting Bank In', 'Invoice Sent')
""")
    awaiting_payment = float(cur.fetchone()[0] or 0)

    cur.execute("SELECT COALESCE(SUM(reserve_amount), 0) FROM bill_of_lading WHERE LOWER(TRIM(reserve_status)) = 'unsettled'")
    unsettled_reserve = float(cur.fetchone()[0] or 0)

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

@app.route('/api/stats/outstanding_bills')
@jwt_required()
def outstanding_bills():
    user = json.loads(get_jwt_identity())
    if user['role'] not in ['staff', 'admin']:
        return jsonify({'error': 'Unauthorized'}), 403

    conn = get_db_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            id, customer_name, bl_number,
            ctn_fee, service_fee, reserve_amount,
            payment_method, reserve_status, invoice_filename
        FROM bill_of_lading
        WHERE status IN ('Awaiting Bank In', 'Invoice Sent')
           OR (payment_method = 'Allinpay' AND LOWER(TRIM(reserve_status)) = 'unsettled')
    """)
    rows = cur.fetchall()
    columns = [desc[0] for desc in cur.description]

    bills = []
    for row in rows:
        bill = dict(zip(columns, row))

        ctn_fee = float(bill.get('ctn_fee') or 0)
        service_fee = float(bill.get('service_fee') or 0)

        payment_method = str(bill.get('payment_method') or '').strip().lower()
        reserve_status = str(bill.get('reserve_status') or '').strip().lower()

        outstanding_amount = round(ctn_fee + service_fee, 2)

        if payment_method == 'allinpay' and reserve_status == 'unsettled':
            outstanding_amount = round(ctn_fee * 0.15 + service_fee * 0.15, 2)

        bill['outstanding_amount'] = outstanding_amount
        bills.append(bill)

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
        return jsonify({'message': 'If this email is registered, a reset link will be sent.'})

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

        if pdf_url.startswith('http://') or pdf_url.startswith('https://'):
            pdf_filename = os.path.basename(pdf_url)
        else:
            pdf_filename = pdf_url.lstrip('/')
        pdf_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads', pdf_filename)
        
        success = send_invoice_email(to_email, subject, body, pdf_path)
        
        if success:
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
    total_bank_ctn = 0
    total_bank_service = 0
    total_allinpay_85_ctn = 0
    total_allinpay_85_service = 0
    total_reserve_ctn = 0
    total_reserve_service = 0

    for row in rows:
        bill = dict(zip(columns, row))

        if bill.get('customer_email'):
            bill['customer_email'] = decrypt_sensitive_data(bill['customer_email'])
        if bill.get('customer_phone'):
            bill['customer_phone'] = decrypt_sensitive_data(bill['customer_phone'])

        ctn_fee = float(bill.get('ctn_fee') or 0)
        service_fee = float(bill.get('service_fee') or 0)

        bill['display_ctn_fee'] = ctn_fee
        bill['display_service_fee'] = service_fee

        if bill.get('payment_method') == 'Allinpay':
            allinpay_85_dt = bill.get('allinpay_85_received_at')
            if allinpay_85_dt:
                if isinstance(allinpay_85_dt, str):
                    allinpay_85_dt = parser.isoparse(allinpay_85_dt)
                if allinpay_85_dt and allinpay_85_dt.tzinfo is None:
                    allinpay_85_dt = allinpay_85_dt.replace(tzinfo=pytz.UTC)
                if completed_at and allinpay_85_dt and start_date <= allinpay_85_dt < end_date:
                    bill['display_ctn_fee'] = round(ctn_fee * 0.85, 2)
                    bill['display_service_fee'] = round(service_fee * 0.85, 2)
                    total_allinpay_85_ctn += bill['display_ctn_fee']
                    total_allinpay_85_service += bill['display_service_fee']
            reserve_status = (bill.get('reserve_status') or '').lower()
            completed_dt = bill.get('completed_at')
            if completed_dt:
                if isinstance(completed_dt, str):
                    completed_dt = parser.isoparse(completed_dt)
                if completed_dt and completed_dt.tzinfo is None:
                    completed_dt = completed_dt.replace(tzinfo=pytz.UTC)
            if reserve_status in ['settled', 'reserve settled'] and completed_at and completed_dt and start_date <= completed_dt < end_date:
                bill['display_ctn_fee'] = round(ctn_fee * 0.15, 2)
                bill['display_service_fee'] = round(service_fee * 0.15, 2)
                total_reserve_ctn += bill['display_ctn_fee']
                total_reserve_service += bill['display_service_fee']
        else:
            completed_dt = bill.get('completed_at')
            if completed_dt:
                if isinstance(completed_dt, str):
                    completed_dt = parser.isoparse(completed_dt)
                if completed_dt and completed_dt.tzinfo is None:
                    completed_dt = completed_dt.replace(tzinfo=pytz.UTC)
            if completed_at and completed_dt and start_date <= completed_dt < end_date:
                total_bank_ctn += ctn_fee
                total_bank_service += service_fee

        bills.append(bill)

    summary = {
        'totalEntries': len(bills),
        'totalCtnFee': round(total_bank_ctn + total_allinpay_85_ctn + total_reserve_ctn, 2),
        'totalServiceFee': round(total_bank_service + total_allinpay_85_service + total_reserve_service, 2),
        'bankTotal': round(total_bank_ctn + total_bank_service, 2),
        'allinpay85Total': round(total_allinpay_85_ctn + total_allinpay_85_service, 2),
        'reserveTotal': round(total_reserve_ctn + total_reserve_service, 2)
    }

    cur.close()
    conn.close()

    return jsonify({'bills': bills, 'summary': summary})

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

@app.route('/api/request_username', methods=['POST'])
def request_username():
    data = request.get_json()
    email = data.get('email')

    if not email:
        return jsonify({'error': 'Email is required'}), 400

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

@app.errorhandler(404)
def not_found(e):
    return '<h1>404 - Page Not Found</h1><p>Sorry, the page you are looking for does not exist.</p>', 404

@app.errorhandler(500)
def internal_error(e):
    app.logger.error(f'500 error: {request.url} - {e}')
    return '<h1>500 - Internal Server Error</h1><p>Sorry, something went wrong on our end. Please try again later.</p>', 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)

# Initialize Encryption
encryption_key = os.getenv('ENCRYPTION_KEY')
if not encryption_key:
    encryption_key = Fernet.generate_key()
    print(f"Generated new encryption key: {encryption_key.decode()}")
    print("Please add this to your .env file as ENCRYPTION_KEY=<key>")
else:
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
        return data

def decrypt_sensitive_data(encrypted_data):
    if not encrypted_data:
        return encrypted_data
    try:
        if isinstance(encrypted_data, str) and encrypted_data.startswith('gAAAAA'):
            return fernet.decrypt(encrypted_data.encode()).decode()
        return encrypted_data
    except Exception as e:
        print(f"Decryption error for data: {encrypted_data[:50]}... Error: {str(e)}")
        return encrypted_data

def log_sensitive_operation(user_id, operation, details):
    pass  # Temporarily disabled until audit_logs table is created

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/', methods=['GET'])
@limiter.exempt
def root():
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
    try:
        conn = get_db_conn()
        if conn:
            conn.close()
            return jsonify({
                'status': 'healthy',
                'database': 'connected',
                'timestamp': datetime.now(pytz.timezone('Asia/Hong_Kong')).isoformat()
            }), 200
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