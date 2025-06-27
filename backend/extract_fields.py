import re
import os
import io
from google.cloud import vision
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()
print("DEBUG: GOOGLE_APPLICATION_CREDENTIALS =", os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))

# Set up logging
logging.basicConfig(level=logging.INFO)

# Google Vision client initialization
GOOGLE_CREDENTIALS = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
if not GOOGLE_CREDENTIALS or not os.path.exists(GOOGLE_CREDENTIALS):
    raise RuntimeError('Google Vision credentials not found. Please set GOOGLE_APPLICATION_CREDENTIALS in your .env file.')

client = vision.ImageAnnotatorClient()

def extract_text_from_file(file_path):
    return extract_text_from_pdf(file_path)

def extract_text_from_pdf(pdf_path):
    with io.open(pdf_path, 'rb') as pdf_file:
        content = pdf_file.read()
    mime_type = 'application/pdf'
    input_doc = vision.InputConfig(content=content, mime_type=mime_type)
    requests = [
        vision.AnnotateFileRequest(
            input_config=input_doc,
            features=[vision.Feature(type_=vision.Feature.Type.DOCUMENT_TEXT_DETECTION)]
        )
    ]
    response = client.batch_annotate_files(requests=requests)
    return response.responses[0]

def parse_common_fields(lines):
    def next_nonempty(idx):
        for i in range(idx+1, len(lines)):
            if lines[i].strip():
                return lines[i].strip()
        return ""

    flight_or_vessel = ""
    product_description = ""

    for i, line in enumerate(lines):
        if re.search(r'(FLIGHT NO|VESSEL NAME|VOYAGE NO|CARRIER)', line, re.IGNORECASE):
            flight_or_vessel = next_nonempty(i)
            break

    for i, line in enumerate(lines):
        if re.search(r'(DESCRIPTION OF GOODS|GOODS DESCRIPTION|PRODUCT NAME|NATURE AND QUANTITY)', line, re.IGNORECASE):
            for j in range(i+1, min(i+5, len(lines))):
                if lines[j].strip():
                    product_description = lines[j].strip()
                    break
            break

    return flight_or_vessel, product_description

def parse_air_waybill_fields(ocr_text, page_response):
    lines = [line.strip() for line in ocr_text.split('\n') if line.strip()]
    flight_or_vessel, product_description = parse_common_fields(lines)

    return {
        'shipper': '...',
        'consignee': '...',
        'origin': '...',
        'destination': '...',
        'awb_number': '...',
        'total_packages': '...',
        'flight_or_vessel': flight_or_vessel,
        'product_description': product_description,
        'raw_text': ocr_text
    }

def parse_bill_of_lading_fields(ocr_text, page_response):
    lines = [line.strip() for line in ocr_text.split('\n') if line.strip()]
    flight_or_vessel, product_description = parse_common_fields(lines)

    return {
        'shipper': '...',
        'consignee': '...',
        'port_of_loading': '...',
        'port_of_discharge': '...',
        'bl_number': '...',
        'container_numbers': '...',
        'flight_or_vessel': flight_or_vessel,
        'product_description': product_description,
        'raw_text': ocr_text
    }

def extract_fields(file_path):
    print('=== extract_fields function called ===')
    try:
        response = extract_text_from_file(file_path)
        image_response = response

        all_text = ""
        for page_response in image_response.responses:
            all_text += page_response.full_text_annotation.text + "\n"

        if 'AIR WAYBILL' in all_text.upper():
            fields = parse_air_waybill_fields(all_text, page_response)
            fields["document_type"] = "AWB"
        else:
            fields = parse_bill_of_lading_fields(all_text, page_response)
            fields["document_type"] = "BOL"

        print('=== PARSED FIELDS ===')
        for k, v in fields.items():
            print(f'{k}: {v}')
        print('=== END PARSED FIELDS ===')
        return fields
    except Exception as e:
        logging.error(f"Vision API failed: {e}. Fallback not available in this revision.")
        return {'error': str(e)}
