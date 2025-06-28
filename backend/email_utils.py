import smtplib
from email.message import EmailMessage
from email.utils import formataddr
import os

from config import EmailConfig

print("Loaded email_utils.py")

# Send invoice email with PDF attachment using SMTP
def send_invoice_email(to_email, subject, body, pdf_path):
    try:
        # Check if SMTP configuration is available
        if not all([EmailConfig.SMTP_SERVER, EmailConfig.SMTP_USERNAME, EmailConfig.SMTP_PASSWORD]):
            print("SMTP configuration not available, skipping email sending")
            return True  # Return True to indicate success since we're skipping

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

# Send unique number email using SMTP (plain text)
def send_unique_number_email(to_email, subject, body):
    try:
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = formataddr(('Logistics Company', EmailConfig.FROM_EMAIL))
        msg['To'] = to_email
        msg.set_content(body)

        with smtplib.SMTP(EmailConfig.SMTP_SERVER, EmailConfig.SMTP_PORT) as server:
            server.starttls()
            server.login(EmailConfig.SMTP_USERNAME, EmailConfig.SMTP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"Failed to send unique number email: {str(e)}")
        return False

def send_contact_email(name, from_email, message):
    to_email = "johnwongjething@gmail.com"  # Your receiving email
    subject = "New Contact Form Submission"
    body = f"Name: {name}\nEmail: {from_email}\n\nMessage:\n{message}"

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = formataddr(('Website Contact', EmailConfig.FROM_EMAIL))
    msg['To'] = to_email
    msg['Reply-To'] = from_email
    msg.set_content(body)

    try:
        print(f"Attempting to send contact email to: {to_email}")
        with smtplib.SMTP(EmailConfig.SMTP_SERVER, EmailConfig.SMTP_PORT) as server:
            server.starttls()
            server.login(EmailConfig.SMTP_USERNAME, EmailConfig.SMTP_PASSWORD)
            server.send_message(msg)
        print("Contact email sent successfully.")
        return True
    except Exception as e:
        print(f"Failed to send contact email: {str(e)}")
        return False

# Send a simple plain text email to a customer (for registration approval, upload confirmation, etc.)
def send_simple_email(to_email, subject, body):
    try:
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = formataddr(('Logistics Company', EmailConfig.FROM_EMAIL))
        msg['To'] = to_email
        msg.set_content(body)
        
        with smtplib.SMTP(EmailConfig.SMTP_SERVER, EmailConfig.SMTP_PORT) as server:
            server.starttls()
            server.login(EmailConfig.SMTP_USERNAME, EmailConfig.SMTP_PASSWORD)
            server.send_message(msg)
        print("Simple email sent successfully.")
        return True
    except Exception as e:
        print("Failed to send simple email:", e)
        return False
