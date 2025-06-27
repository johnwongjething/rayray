# Revised extract_fields.py — fixes AWB parser + cleans BOL port logic

import re
import os
import io
from google.cloud import vision
from dotenv import load_dotenv
import logging
from datetime import datetime

load_dotenv()
print("DEBUG: GOOGLE_APPLICATION_CREDENTIALS =", os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))

logging.basicConfig(level=logging.INFO)
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
    def next_valid_line(idx):
        for i in range(idx + 1, min(idx + 5, len(lines))):
            line = lines[i].strip()
            if not line or re.match(r'^[0-9]+\.', line):
                continue
            return line
        return ""

    flight_or_vessel = ""
    product_description = ""

    for i, line in enumerate(lines):
        if re.search(r'(EXPORTING CARRIER|VESSEL NAME|VOYAGE NO|FLIGHT NO)', line, re.IGNORECASE):
            flight_or_vessel = next_valid_line(i)
            break

    for i, line in enumerate(lines):
        if re.search(r'(DESCRIPTION OF GOODS|DESCRIPTION OF COMMODITIES|PRODUCT NAME|NATURE AND QUANTITY)', line, re.IGNORECASE):
            desc_lines = []
            for j in range(i + 1, min(i + 6, len(lines))):
                desc = lines[j].strip()
                if not desc or desc.lower().startswith("freight") or "SHIPPER'S LOAD" in desc:
                    break
                desc_lines.append(desc)
            product_description = " ".join(desc_lines).strip()
            break

    return flight_or_vessel, product_description

def parse_bill_of_lading_fields(ocr_text, page_response):
    lines = [line.strip() for line in ocr_text.split('\n') if line.strip()]
    n = len(lines)

    def next_nonempty(idx):
        for i in range(idx + 1, n):
            if lines[i]:
                return lines[i]
        return ""

    shipper = ""
    for i, line in enumerate(lines):
        if re.match(r'2\.? *EXPORTER', line, re.IGNORECASE):
            next_line = next_nonempty(i)
            shipper = next_line.split(',')[0].split('(')[0].strip()
            break

    consignee = ""
    for i, line in enumerate(lines):
        if re.match(r'3\.? *CONSIGNED TO', line, re.IGNORECASE):
            name_parts = []
            for j in range(1, 4):
                if i + j < len(lines):
                    candidate = lines[i + j].strip()
                    if not candidate:
                        continue
                    if re.match(r'(C/O|ATTN|ADDRESS|TEL|FAX)', candidate, re.IGNORECASE):
                        break
                    name_parts.append(candidate)
                    if len(name_parts) >= 2:
                        break
            consignee = ' '.join(name_parts)
            break

    port_of_loading = ""
    for i, line in enumerate(lines):
        if "PORT OF LOADING" in line:
            port_of_loading = next_nonempty(i)
            break

    port_of_discharge = ""
    for i, line in enumerate(lines):
        if "PLACE OF DELIVERY BY ON-CARRIER" in line or "FOREIGN PORT OF UNLOADING" in line or "PORT OF DISCHARGE" in line:
            port_of_discharge = next_nonempty(i)
            break

    bl_number = ""
    for i, line in enumerate(lines):
        if "B/L NUMBER" in line or "DOCUMENT NUMBER" in line:
            for j in range(i + 1, min(i + 4, n)):
                match = re.search(r'\b[A-Z]{3,}[0-9]{6,}\b', lines[j])
                if match:
                    bl_number = match.group(0)
                    break
            if bl_number:
                break

    container_numbers = set()
    for line in lines:
        matches = re.findall(r'\b([A-Z]{4}\d{7})\b', line)
        for match in matches:
            container_numbers.add(match.strip())
    container_numbers = ', '.join(container_numbers)

    flight_or_vessel, product_description = parse_common_fields(lines)

    return {
        'shipper': shipper,
        'consignee': consignee,
        'port_of_loading': port_of_loading,
        'port_of_discharge': port_of_discharge,
        'bl_number': bl_number,
        'container_numbers': container_numbers,
        'flight_or_vessel': flight_or_vessel,
        'product_description': product_description,
        'raw_text': ocr_text
    }

def parse_air_waybill_fields(ocr_text, page_response):
    lines = [line.strip() for line in ocr_text.split('\n') if line.strip()]

    def extract_field_by_label(label_keywords):
        for i, line in enumerate(lines):
            for keyword in label_keywords:
                if keyword.lower() in line.lower():
                    return lines[i + 1].strip() if i + 1 < len(lines) else ""
        return ""

    shipper = extract_field_by_label(["Shipper", "Shipper's Name"])
    consignee = extract_field_by_label(["Consignee", "Consignee's Name"])
    origin = extract_field_by_label(["Origin", "Airport of Departure"])
    destination = extract_field_by_label(["Destination", "Airport of Destination"])
    awb_number = extract_field_by_label(["Air Waybill No", "AWB No", "Waybill No"])
    total_packages = extract_field_by_label(["No. of Packages", "Total Pieces"])

    flight_or_vessel, product_description = parse_common_fields(lines)

    return {
        'shipper': shipper,
        'consignee': consignee,
        'origin': origin,
        'destination': destination,
        'awb_number': awb_number,
        'total_packages': total_packages,
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

        print("flight_or_vessel:", fields.get("flight_or_vessel", ""))
        print("product_description:", fields.get("product_description", ""))

        return fields
    except Exception as e:
        logging.error(f"Vision API failed: {e}.")
        return {'error': str(e)}
