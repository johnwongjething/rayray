# Unified extract_fields.py with AWB & B/L support and final AWB trimming logic
import re
import os
import io
from google.cloud import vision
from dotenv import load_dotenv
import logging

load_dotenv()
logging.basicConfig(level=logging.INFO)

GOOGLE_CREDENTIALS = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
if not GOOGLE_CREDENTIALS or not os.path.exists(GOOGLE_CREDENTIALS):
    raise RuntimeError('Google Vision credentials not found.')

client = vision.ImageAnnotatorClient()

def extract_text_from_file(file_path):
    with open(file_path, 'rb') as f:
        content = f.read()
    mime_type = 'application/pdf'
    input_doc = vision.InputConfig(content=content, mime_type=mime_type)
    requests = [vision.AnnotateFileRequest(
        input_config=input_doc,
        features=[vision.Feature(type_=vision.Feature.Type.DOCUMENT_TEXT_DETECTION)]
    )]
    response = client.batch_annotate_files(requests=requests)
    return response.responses[0]

def get_center(bounding_box):
    vertices = bounding_box.vertices
    x = sum(v.x for v in vertices) / 4
    y = sum(v.y for v in vertices) / 4
    return (x, y)

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

    port_of_loading = " ".join(port_of_loading.split()[:3]).strip()
    port_of_discharge = " ".join(port_of_discharge.split()[:3]).strip()

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

    return {
        "document_type": "AWB",
        "bl_number": bl_number,
        "shipper": shipper,
        "consignee": consignee,
        "port_of_loading": port_of_loading,
        "port_of_discharge": port_of_discharge,
        "container_numbers": container_numbers,
        "raw_text": ocr_text
    }

def parse_bill_of_lading_fields(ocr_text, page_response):
    lines = [line.strip() for line in ocr_text.split('\n') if line.strip()]
    n = len(lines)
    def next_nonempty(idx):
        for i in range(idx+1, n):
            if lines[i]:
                return lines[i]
        return ""

    shipper = ""
    for i, line in enumerate(lines):
        if re.match(r'2\.? *EXPORTER', line, re.IGNORECASE):
            shipper = next_nonempty(i).split(',')[0].split('(')[0].strip()
            break

    consignee = ""
    for i, line in enumerate(lines):
        if re.match(r'3\.? *CONSIGNED TO', line, re.IGNORECASE):
            name_parts = []
            for j in range(1, 4):
                if i + j < len(lines):
                    candidate = lines[i + j].strip()
                    if re.match(r'(C/O|ATTN|ADDRESS|TEL|FAX)', candidate, re.IGNORECASE):
                        break
                    name_parts.append(candidate)
            consignee = ' '.join(name_parts)
            break

    port_of_loading = ""
    for i, line in enumerate(lines):
        if "PORT OF LOADING" in line.upper():
            port_of_loading = next_nonempty(i)
            break

    port_of_discharge = ""
    for i, line in enumerate(lines):
        if "FOREIGN PORT OF UNLOADING" in line.upper() or "PLACE OF DELIVERY" in line.upper():
            port_of_discharge = next_nonempty(i)
            break

    bl_number = ""
    for i, line in enumerate(lines):
        if "B/L NUMBER" in line or "DOCUMENT NUMBER" in line:
            for j in range(i+1, min(i+4, n)):
                match = re.search(r'\b[A-Z]{3,}[0-9]{6,}\b', lines[j])
                if match:
                    bl_number = match.group(0)
                    break
            if bl_number:
                break
    if not bl_number:
        bl_text = find_nearest_text_below("B/L NUMBER", page_response)
        match = re.search(r'\b[A-Z]{3,}[0-9]{6,}\b', bl_text)
        if match:
            bl_number = match.group(0)

    container_numbers = set()
    for line in lines:
        matches = re.findall(r'(?:CONTAINER\s*(?:NO\.?|#)|CONTR(?:AINER)?\s*#)\s*([A-Z0-9]+)', line, re.IGNORECASE)
        matches += re.findall(r'\b([A-Z]{4}\d{7})\b', line)
        for match in matches:
            container_numbers.add(match.strip())

    return {
        'document_type': 'B/L',
        'shipper': shipper,
        'consignee': consignee,
        'port_of_loading': port_of_loading,
        'port_of_discharge': port_of_discharge,
        'bl_number': bl_number,
        'container_numbers': ', '.join(container_numbers),
        'raw_text': ocr_text
    }

def extract_fields(file_path):
    try:
        response = extract_text_from_file(file_path)
        all_text = "\n".join([page.full_text_annotation.text for page in response.responses])
        last_page = response.responses[-1]

        if "AIR WAYBILL" in all_text.upper():
            fields = parse_air_waybill_fields(all_text, last_page)
        else:
            fields = parse_bill_of_lading_fields(all_text, last_page)

        return fields
    except Exception as e:
        logging.error(f"Vision API failed: {e}")
        return {'error': str(e)}
