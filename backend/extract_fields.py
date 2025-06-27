# Revised extract_fields.py — AWB now restored to advanced logic, BOL port logic cleaned

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

def find_nearest_text_below(label_text, page_response):
    label_coords = []
    candidates = []

    for page in page_response.full_text_annotation.pages:
        for block in page.blocks:
            block_text = ""
            for paragraph in block.paragraphs:
                para_text = ""
                for word in paragraph.words:
                    word_text = ''.join([s.text for s in word.symbols])
                    para_text += word_text + " "
                block_text += para_text.strip() + "\n"

            if label_text.lower() in block_text.lower():
                label_coords.append(get_center(block.bounding_box))
            else:
                candidates.append((get_center(block.bounding_box), block_text.strip()))

    for label in label_coords:
        below_blocks = [
            (text, center) for center, text in candidates
            if center[1] > label[1] and abs(center[0] - label[0]) < 150
        ]
        if below_blocks:
            below_blocks.sort(key=lambda b: b[1][1])
            return below_blocks[0][0]
    return ""

def get_center(bounding_box):
    vertices = bounding_box.vertices
    x = sum(v.x for v in vertices) / 4
    y = sum(v.y for v in vertices) / 4
    return (x, y)

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

def parse_air_waybill_fields(ocr_text, page_response):
    lines = [line.strip() for line in ocr_text.split('\n') if line.strip()]
    print("=== DEBUG: OCR TEXT ===")
    print(ocr_text)

    def get_after_label(label_keywords):
        for i, line in enumerate(lines):
            for keyword in label_keywords:
                if keyword.lower() in line.lower():
                    return " ".join(lines[i+1:i+4])
        return ""

    def find_port_by_label(label, lines):
        for i, line in enumerate(lines):
            if label.lower() in line.lower():
                return " ".join(lines[i+1:i+4])
        return ""

    def find_first_company_line(start_keywords, stop_keywords):
        collecting = False
        for line in lines:
            if any(kw.lower() in line.lower() for kw in start_keywords):
                collecting = True
                continue
            if collecting:
                if any(stop.lower() in line.lower() for stop in stop_keywords):
                    break
                if re.search(r'[A-Z]{2,}', line):
                    return line.strip()
        return ""

    bl_number = ""
    awb_match = re.search(r'\b\d{3}-\d{7,8}\b', ocr_text)
    if awb_match:
        bl_number = awb_match.group(0)

    shipper = find_first_company_line(["Shipper's Name and Address"], ["Consignee"])
    consignee = find_first_company_line(["Consignee's Name and Address"], ["Issuing Carrier", "Agent"])

    port_of_loading = (
        find_nearest_text_below("Airport of Departure", page_response)
        or find_port_by_label("Airport of Departure", lines)
    )
    port_of_discharge = (
        find_nearest_text_below("Airport of Destination", page_response)
        or find_port_by_label("Airport of Destination", lines)
    )

    port_of_loading = re.split(r'[^A-Z/\- ]+', port_of_loading, flags=re.IGNORECASE)[0].strip()
    port_of_discharge = re.split(r'[^A-Z/\- ]+', port_of_discharge, flags=re.IGNORECASE)[0].strip()

    known_ports = ["NEW YORK CITY", "HEATHROW", "LHR", "JFK", "ATLANTA"]
    for port in known_ports:
        if port in ocr_text.upper():
            if not port_of_loading and "NEW YORK" in port:
                port_of_loading = port
            elif not port_of_discharge:
                port_of_discharge = port

    container_numbers = ""
    pkg_match = re.search(r'(\d{1,3})\s*(pieces|pkgs|packages|pcs)', ocr_text, re.IGNORECASE)
    if pkg_match:
        container_numbers = pkg_match.group(1)
    else:
        for line in reversed(lines):
            if re.search(r'(\d+)\s*(pcs|packages|pkgs)', line, re.IGNORECASE):
                match = re.search(r'(\d+)', line)
                if match:
                    container_numbers = match.group(1)
                    break

    flight_or_vessel, product_description = parse_common_fields(lines)

    return {
        "document_type": "AWB",
        "bl_number": bl_number,
        "shipper": shipper,
        "consignee": consignee,
        "port_of_loading": port_of_loading,
        "port_of_discharge": port_of_discharge,
        "container_numbers": container_numbers,
        "flight_or_vessel": flight_or_vessel,
        "product_description": product_description,
        "raw_text": ocr_text
    }
