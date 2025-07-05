import psycopg2
from config import get_db_conn

def insert_bill_of_lading(
    customer_name, customer_email, customer_phone, pdf_filename, ocr_text,
    shipper, consignee, port_of_loading, port_of_discharge, bl_number, container_numbers
):
    conn = get_db_conn()
    if not conn:
        raise Exception("Failed to connect to database")
    
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO bill_of_lading (
            customer_name, customer_email, customer_phone, pdf_filename, ocr_text,
            shipper, consignee, port_of_loading, port_of_discharge, bl_number, container_numbers
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            customer_name, customer_email, customer_phone, pdf_filename, ocr_text,
            shipper, consignee, port_of_loading, port_of_discharge, bl_number, container_numbers
        )
    )
    conn.commit()
    cur.close()
    conn.close()