from flask import Blueprint, request, jsonify
from config import get_db_conn
import logging
from datetime import datetime
import pytz

# Create a Blueprint for the payment link endpoint
payment_link = Blueprint('payment_link', __name__)

# Configure logging
logger = logging.getLogger(__name__)

@payment_link.route('/api/generate_payment_link/<int:bill_id>', methods=['POST'])
def generate_payment_link(bill_id):
    """
    Generate a dummy payment link for a specific bill and store it in the database.
    Accepts optional parameters in the request body to customize the link.
    """
    try:
        # Get data from the request body and print for debugging
        data = request.get_json()
        print(f"Generating payment link for bill_id {bill_id} with data: {data}")  # Debug print statement
        amount = float(data.get('amount', 0.0))  # Default to 0.0 if not provided
        currency = data.get('currency', 'USD')  # Default to USD
        customer_email = data.get('customer_email')  # Optional, can be overridden
        description = data.get('description', 'Reserve Payment')  # Default description
        success_url = data.get('success_url', 'https://yourdomain.com/success')  # Default success URL
        cancel_url = data.get('cancel_url', 'https://yourdomain.com/cancel')  # Default cancel URL
        ctn_fee = float(data.get('ctn_fee', 0.0))  # Capture from input field
        service_fee = float(data.get('service_fee', 0.0))  # Capture from input field

        # Log the request
        logger.info(f"Generating payment link for bill_id {bill_id} with amount {amount} {currency}")

        # Connect to the database
        conn = get_db_conn()
        cur = conn.cursor()

        # Fetch bill details (only customer_email and unique_number for now)
        cur.execute("""
            SELECT customer_email, unique_number
            FROM bill_of_lading
            WHERE id = %s
        """, (bill_id,))
        bill = cur.fetchone()

        if not bill:
            cur.close()
            conn.close()
            return jsonify({"error": "Bill not found"}), 404

        stored_email, unique_number = bill
        customer_email = customer_email or stored_email

        # Calculate reserve amount based on input fees
        reserve_amount = amount if amount > 0 else (ctn_fee + service_fee) * 0.15

        # Generate a dummy payment link
        hk_now = datetime.now(pytz.timezone('Asia/Hong_Kong'))
        dummy_link = (
            f"https://pay.dummy.com/link/{bill_id}"
            f"?amount={reserve_amount:.2f}"
            f"¤cy={currency}"
            f"&email={customer_email}"
            f"&ctn={unique_number or 'None'}"
            f"&description={description.replace(' ', '%20')}"
            f"&success={success_url}"
            f"&cancel={cancel_url}"
            f"×tamp={hk_now.strftime('%Y%m%d%H%M%S')}"
        )

        # Update the database with the dummy payment link
        cur.execute("UPDATE bill_of_lading SET payment_link = %s WHERE id = %s", (dummy_link, bill_id))
        conn.commit()
        cur.close()
        conn.close()

        # Return the generated payment link
        return jsonify({"payment_link": dummy_link})

    except Exception as e:
        logger.error(f"Failed to generate payment link for bill_id {bill_id}: {str(e)}")
        return jsonify({"error": str(e)}), 500

# from flask import Blueprint, request, jsonify
# from config import get_db_conn
# import logging
# from datetime import datetime
# import pytz

# # Create a Blueprint for the payment link endpoint
# payment_link = Blueprint('payment_link', __name__)

# # Configure logging
# logger = logging.getLogger(__name__)

# @payment_link.route('/api/generate_payment_link/<int:bill_id>', methods=['POST'])
# def generate_payment_link(bill_id):
#     """
#     Generate a dummy payment link for a specific bill and store it in the database.
#     Accepts optional parameters in the request body to customize the link.
#     """
#     try:
#         # Get data from the request body and print for debugging
#         data = request.get_json()
#         print(f"Generating payment link for bill_id {bill_id} with data: {data}")  # Debug print statement
#         amount = float(data.get('amount', 0.0))  # Default to 0.0 if not provided
#         currency = data.get('currency', 'USD')  # Default to USD
#         customer_email = data.get('customer_email')  # Optional, can be overridden
#         description = data.get('description', 'Reserve Payment')  # Default description
#         success_url = data.get('success_url', 'https://yourdomain.com/success')  # Default success URL
#         cancel_url = data.get('cancel_url', 'https://yourdomain.com/cancel')  # Default cancel URL

#         # Log the request
#         logger.info(f"Generating payment link for bill_id {bill_id} with amount {amount} {currency}")

#         # Connect to the database
#         conn = get_db_conn()
#         cur = conn.cursor()

#         # Fetch bill details to calculate reserve amount if amount not provided
#         cur.execute("""
#             SELECT ctn_fee, service_fee, unique_number, customer_email
#             FROM bill_of_lading
#             WHERE id = %s
#         """, (bill_id,))
#         bill = cur.fetchone()

#         if not bill:
#             cur.close()
#             conn.close()
#             return jsonify({"error": "Bill not found"}), 404

#         ctn_fee, service_fee, unique_number, stored_email = bill
#         ctn_fee = float(ctn_fee or 0)
#         service_fee = float(service_fee or 0)
#         reserve_amount = amount if amount > 0 else (ctn_fee + service_fee) * 0.15  # Use 15% if no amount specified

#         # Use stored email if not provided in request
#         customer_email = customer_email or stored_email

#         # Generate a dummy payment link
#         hk_now = datetime.now(pytz.timezone('Asia/Hong_Kong'))
#         dummy_link = (
#             f"https://pay.dummy.com/link/{bill_id}"
#             f"?amount={reserve_amount:.2f}"
#             f"¤cy={currency}"
#             f"&email={customer_email}"
#             f"&ctn={unique_number}"
#             f"&description={description.replace(' ', '%20')}"
#             f"&success={success_url}"
#             f"&cancel={cancel_url}"
#             f"×tamp={hk_now.strftime('%Y%m%d%H%M%S')}"
#         )

#         # Update the database with the dummy payment link
#         cur.execute("UPDATE bill_of_lading SET payment_link = %s WHERE id = %s", (dummy_link, bill_id))
#         conn.commit()
#         cur.close()
#         conn.close()

#         # Return the generated payment link
#         return jsonify({"payment_link": dummy_link})

#     except Exception as e:
#         logger.error(f"Failed to generate payment link for bill_id {bill_id}: {str(e)}")
#         return jsonify({"error": str(e)}), 500
