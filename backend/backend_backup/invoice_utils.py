from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import os
from config import get_db_conn, EmailConfig
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

def generate_invoice_pdf(customer, bill, service_fee, ctn_fee=None, payment_link=None):
    invoice_filename = f"invoice_{bill['id']}.pdf"
    uploads_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), 'uploads'))
    if not os.path.exists(uploads_folder):
        os.makedirs(uploads_folder)
    invoice_path = os.path.join(uploads_folder, invoice_filename)

    c = canvas.Canvas(invoice_path, pagesize=A4)
    c.setFont("Helvetica", 12)
    y = 800
    c.drawString(50, y, "INVOICE")
    y -= 30
    c.drawString(50, y, f"Customer Name: {customer['name']}")
    y -= 20
    c.drawString(50, y, f"Email: {customer['email']}")
    y -= 20
    c.drawString(50, y, f"Phone: {customer['phone']}")
    y -= 30
    c.drawString(50, y, f"Bill of Lading No: {bill['bl_number']}")
    y -= 20
    c.drawString(50, y, f"Shipper: {bill['shipper']}")
    y -= 20
    c.drawString(50, y, f"Consignee: {bill['consignee']}")
    y -= 20
    c.drawString(50, y, f"Port of Loading: {bill['port_of_loading']}")
    y -= 20
    c.drawString(50, y, f"Port of Discharge: {bill['port_of_discharge']}")
    y -= 20
    c.drawString(50, y, f"Container Numbers: {bill['container_numbers']}")
    y -= 30
    c.drawString(50, y, f"CTN Fee (USD): {ctn_fee if ctn_fee is not None else ''}")
    y -= 20
    c.drawString(50, y, f"Service Fee (USD): {service_fee}")
    y -= 20
    total = (float(service_fee or 0) + float(ctn_fee or 0))
    c.drawString(50, y, f"Total Amount (USD): {total}")
    y -= 30
    if payment_link:
        c.drawString(50, y, f"Payment Link: {payment_link}")
        y -= 30
    c.drawString(50, y, "Thank you for your business!")
    c.save()

    # Save the filename to the database
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("UPDATE bill_of_lading SET invoice_filename=%s WHERE id=%s", (invoice_filename, bill['id']))
        conn.commit()
        cur.close()
        conn.close()
        return invoice_filename
    except Exception as e:
        print(f"Error saving invoice filename: {str(e)}")
        return None

def send_invoice_email(to_email, subject, body, pdf_path):
    try:
        print(f"Attempting to send email to: {to_email}")
        print(f"SMTP server: {EmailConfig.SMTP_SERVER}:{EmailConfig.SMTP_PORT}")
        print(f"From email: {EmailConfig.FROM_EMAIL}")
        
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = formataddr(('Logistics Company', EmailConfig.FROM_EMAIL))
        msg['To'] = to_email
        msg.set_content(body)

        # Attach PDF
        print(f"Attaching PDF from: {pdf_path}")
        with open(pdf_path, 'rb') as f:
            pdf_data = f.read()
            msg.add_attachment(pdf_data, maintype='application', subtype='pdf', filename='invoice.pdf')

        with smtplib.SMTP(EmailConfig.SMTP_SERVER, EmailConfig.SMTP_PORT) as server:
            print("Starting TLS...")
            server.starttls()
            print("Logging in...")
            server.login(EmailConfig.SMTP_USERNAME, EmailConfig.SMTP_PASSWORD)
            print("Sending message...")
            server.send_message(msg)
        print("Email sent successfully")
        return True
    except Exception as e:
        print(f"Failed to send invoice email: {str(e)}")
        print(f"Email config: {EmailConfig.SMTP_SERVER}, {EmailConfig.SMTP_PORT}, {EmailConfig.SMTP_USERNAME}, {EmailConfig.SMTP_PASSWORD}")
        return False