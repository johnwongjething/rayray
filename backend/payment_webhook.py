from flask import Blueprint, request, jsonify
from email_utils import send_unique_number_email  # Replaced send_simple_email with send_unique_number_email
import logging
import hmac
import hashlib
import json
from datetime import datetime
import re
from config import EmailConfig, get_db_conn
import pytz

payment_webhook = Blueprint('payment_webhook', __name__)

# Configure logging
logger = logging.getLogger(__name__)

# Secret key for signature verification (set by your bank)
SECRET_KEY = "your_secret_key_here"  # Move to .env or config

def verify_signature(payload, signature):
    """Verify the HMAC signature of the webhook payload."""
    computed_signature = hmac.new(
        SECRET_KEY.encode('utf-8'),
        json.dumps(payload, sort_keys=True).encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(computed_signature, signature)

@payment_webhook.route('/payment', methods=['POST'])
def handle_payment_webhook():
    """Handle bank payment notification webhook."""
    try:
        # Get the raw payload and headers
        data = request.get_json()
        signature = request.headers.get('X-Signature')  # Adjust based on bank docs

        # Verify the signature (commented out for testing without secret key)
        # if signature and not verify_signature(data, signature):
        #     logger.warning("Invalid signature for transaction")
        #     return jsonify({"error": "Invalid signature"}), 400

        # Extract payment details
        transaction_id = data.get('transaction_id')
        amount = float(data.get('amount', 0))
        currency = data.get('currency', 'USD')
        status = data.get('status', '').lower()
        customer_email = data.get('customer_email')  # Assume in payload or fetch from DB
        payment_phase = data.get('payment_phase', '').lower()  # e.g., 'initial' or 'final'

        if not all([transaction_id, amount, currency, status, customer_email]):
            logger.error("Missing required fields in payload")
            return jsonify({"error": "Missing data"}), 400

        # Log the payment details
        logger.info(f"Received payment: ID={transaction_id}, Amount={amount} {currency}, Status={status}")

        # Validate transaction_id as potential B/L number
        if not re.match(r'^\w{3}\d{6,}$|^\d{9,}$', transaction_id):
            logger.warning(f"Transaction ID {transaction_id} does not resemble a B/L number")
            return jsonify({"error": "Invalid transaction ID format"}), 400

        # Fetch bill details from database
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT ctn_fee, service_fee, unique_number
            FROM bill_of_lading
            WHERE unique_number = %s
        """, (transaction_id,))
        bill = cur.fetchone()

        if not bill:
            logger.error(f"No bill found for unique_number {transaction_id}")
            cur.close()
            conn.close()
            return jsonify({"error": "Bill not found"}), 404

        ctn_fee, service_fee, unique_number = bill
        ctn_fee = float(ctn_fee or 0)
        service_fee = float(service_fee or 0)
        invoice_total = ctn_fee + service_fee

        # Determine payment phase
        received_85 = abs(amount - (invoice_total * 0.85)) < 0.01
        received_15 = abs(amount - (invoice_total * 0.15)) < 0.01
        is_initial = payment_phase == 'initial' or received_85
        is_final = payment_phase == 'final' or received_15

        # Update database
        hk_now = datetime.now(pytz.timezone('Asia/Hong_Kong'))
        update_query = """
            UPDATE bill_of_lading
            SET payment_method = %s,
                status = %s
        """
        params = ['Allinpay', 'Paid and CTN Valid']

        if is_initial:
            reserve_amount = invoice_total - (invoice_total * 0.85)
            update_query += ", reserve_status = %s, reserve_amount = %s, payment_status = %s, allinpay_85_received_at = %s"
            params.extend(['Unsettled', reserve_amount, 'Paid 85%', hk_now])
            # Send email only for 85% payment with CTN number
            subject = "Payment Confirmation - 85% Received"
            body = f"""
Dear Customer,

Thank you for your payment!

Transaction Details:
- Transaction ID: {transaction_id}
- Your CTN Number: {unique_number}  <!-- Highlighted as the most important -->
- Total Invoice Amount: {invoice_total} {currency}

If you have any questions, please contact support.

Best regards,
Terry Ray Logistics
"""
            send_unique_number_email(customer_email, subject, body)
            logger.info(f"Email sent to {customer_email} with 85% confirmation and CTN {unique_number}")
        elif is_final:
            update_query += ", reserve_status = %s, payment_status = %s, completed_at = %s"
            params.extend(['Reserve Settled', 'Paid 100%', hk_now])

        update_query += " WHERE unique_number = %s"
        params.append(transaction_id)

        cur.execute(update_query, tuple(params))
        logger.info(f"Updated bill for unique_number {transaction_id} with payment_status {params[5] if is_initial else params[4]}")
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"status": "success"}), 200

    except Exception as e:
        logger.error(f"Webhook processing failed: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

def process_payment(transaction_id, amount, currency, status):
    """Process the payment and link to B/L."""
    logger.info(f"Processing payment for B/L {transaction_id} with amount {amount} {currency}, status {status}")
    # Add your business logic here
    pass


# from flask import Blueprint, request, jsonify
# from email_utils import send_simple_email
# import logging
# import hmac
# import hashlib
# import json
# from datetime import datetime
# import re
# from config import EmailConfig, get_db_conn
# import pytz

# payment_webhook = Blueprint('payment_webhook', __name__)

# # Configure logging
# logger = logging.getLogger(__name__)

# # Secret key for signature verification (set by your bank)
# SECRET_KEY = "your_secret_key_here"  # Move to .env or config

# def verify_signature(payload, signature):
#     """Verify the HMAC signature of the webhook payload."""
#     computed_signature = hmac.new(
#         SECRET_KEY.encode('utf-8'),
#         json.dumps(payload, sort_keys=True).encode('utf-8'),
#         hashlib.sha256
#     ).hexdigest()
#     return hmac.compare_digest(computed_signature, signature)

# @payment_webhook.route('/payment', methods=['POST'])
# def handle_payment_webhook():
#     """Handle bank payment notification webhook."""
#     try:
#         # Get the raw payload and headers
#         data = request.get_json()
#         signature = request.headers.get('X-Signature')  # Adjust based on bank docs

#         # Verify the signature (commented out for testing without secret key)
#         # if signature and not verify_signature(data, signature):
#         #     logger.warning("Invalid signature for transaction")
#         #     return jsonify({"error": "Invalid signature"}), 400

#         # Extract payment details
#         transaction_id = data.get('transaction_id')
#         amount = float(data.get('amount', 0))
#         currency = data.get('currency', 'USD')
#         status = data.get('status', '').lower()
#         customer_email = data.get('customer_email')  # Assume in payload or fetch from DB
#         payment_phase = data.get('payment_phase', '').lower()  # e.g., 'initial' or 'final'

#         if not all([transaction_id, amount, currency, status, customer_email]):
#             logger.error("Missing required fields in payload")
#             return jsonify({"error": "Missing data"}), 400

#         # Log the payment details
#         logger.info(f"Received payment: ID={transaction_id}, Amount={amount} {currency}, Status={status}")

#         # Validate transaction_id as potential B/L number
#         if not re.match(r'^\w{3}\d{6,}$|^\d{9,}$', transaction_id):
#             logger.warning(f"Transaction ID {transaction_id} does not resemble a B/L number")
#             return jsonify({"error": "Invalid transaction ID format"}), 400

#         # Fetch bill details from database
#         conn = get_db_conn()
#         cur = conn.cursor()
#         cur.execute("""
#             SELECT ctn_fee, service_fee, unique_number
#             FROM bill_of_lading
#             WHERE unique_number = %s
#         """, (transaction_id,))
#         bill = cur.fetchone()

#         if not bill:
#             logger.error(f"No bill found for unique_number {transaction_id}")
#             cur.close()
#             conn.close()
#             return jsonify({"error": "Bill not found"}), 404

#         ctn_fee, service_fee, unique_number = bill
#         ctn_fee = float(ctn_fee or 0)
#         service_fee = float(service_fee or 0)
#         invoice_total = ctn_fee + service_fee

#         # Determine payment phase
#         received_85 = abs(amount - (invoice_total * 0.85)) < 0.01
#         received_15 = abs(amount - (invoice_total * 0.15)) < 0.01
#         is_initial = payment_phase == 'initial' or received_85
#         is_final = payment_phase == 'final' or received_15

#         # Update database
#         hk_now = datetime.now(pytz.timezone('Asia/Hong_Kong'))
#         update_query = """
#             UPDATE bill_of_lading
#             SET payment_method = %s,
#                 status = %s
#         """
#         params = ['Allinpay', 'Paid and CTN Valid']

#         if is_initial:
#             reserve_amount = invoice_total - (invoice_total * 0.85)
#             update_query += ", reserve_status = %s, reserve_amount = %s, payment_status = %s, allinpay_85_received_at = %s"
#             params.extend(['Unsettled', reserve_amount, 'Paid 85%', hk_now])
#         elif is_final:
#             update_query += ", reserve_status = %s, payment_status = %s, completed_at = %s"
#             params.extend(['Reserve Settled', 'Paid 100%', hk_now])

#         update_query += " WHERE unique_number = %s"
#         params.append(transaction_id)

#         cur.execute(update_query, tuple(params))
#         logger.info(f"Updated bill for unique_number {transaction_id} with payment_status {params[5] if is_initial else params[4]}")
#         conn.commit()
#         cur.close()
#         conn.close()

#         # Send email with CTN number
#         if unique_number and customer_email:
#             subject = f"Payment Confirmation - Transaction {transaction_id}"
#             body = f"""
# Dear Customer,

# Thank you for your payment!

# Transaction Details:
# - Transaction ID: {transaction_id}
# - Amount: {amount} {currency}
# - CTN Number: {unique_number}
# - Date: {hk_now.strftime('%Y-%m-%d %H:%M:%S AEST')}

# If you have any questions, please contact support.

# Best regards,
# Terry Ray Logistics
# """
#             send_simple_email(customer_email, subject, body)
#             logger.info(f"Email sent to {customer_email} with CTN {unique_number}")

#         return jsonify({"status": "success"}), 200

#     except Exception as e:
#         logger.error(f"Webhook processing failed: {str(e)}")
#         return jsonify({"error": "Internal server error"}), 500

# def process_payment(transaction_id, amount, currency, status):
#     """Process the payment and link to B/L."""
#     logger.info(f"Processing payment for B/L {transaction_id} with amount {amount} {currency}, status {status}")
#     # Add your business logic here
#     pass