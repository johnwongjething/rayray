
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
    raise RuntimeError('Google Vision credentials not found. Please set GOOGLE_APPLICATION_CREDENTIALS in your .env file.')

client = vision.ImageAnnotatorClient()

def extract_text_from_file(file_path):
    with io.open(file_path, 'rb') as f:
        content = f.read()
    input_config = vision.InputConfig(content=content, mime_type='application/pdf')
    request = vision.AnnotateFileRequest(
        input_config=input_config,
        features=[vision.Feature(type_=vision.Feature.Type.DOCUMENT_TEXT_DETECTION)]
    )
    response = client.batch_annotate_files(requests=[request])
    return response.responses[0]

def get_center(bounding_box):
    vertices = bounding_box.vertices
    x = sum(v.x for v in vertices) / 4
    y = sum(v.y for v in vertices) / 4
    return (x, y)

def find_value_near_keyword(ocr_lines, keywords, direction='right', max_distance=400):
    for kw in keywords:
        for label in ocr_lines:
            if kw.lower() in label['text'].lower():
                lx, ly = label['x'], label['y']
                candidates = []
                for item in ocr_lines:
                    dx = item['x'] - lx
                    dy = abs(item['y'] - ly)
                    if direction == 'right' and 0 < dx < max_distance and dy < 30:
                        candidates.append((dx, item['text']))
                    elif direction == 'below' and 0 < item['y'] - ly < max_distance and abs(item['x'] - lx) < 150:
                        candidates.append((item['y'] - ly, item['text']))
                if candidates:
                    candidates.sort()
                    return candidates[0][1]
    return ""

FIELD_KEYWORDS = {
    'shipper': [
        'Shipper', 'Exporter', "Shipper's Name and Address", 'Exported By', 'Consignor', '2. EXPORTER'
    ],
    'consignee': [
        'Consignee', "Consignee's Name and Address", 'Consigned To', 'Notify Party', '3. CONSIGNED TO'
    ],
    'port_of_loading': [
        'Port of Loading', 'Port of Export', 'Place of Receipt', 'Port of Shipment'
    ],
    'port_of_discharge': [
        'Port of Discharge', 'Foreign Port of Unloading', 'Place of Delivery', 'Port of Destination'
    ],
    'vessel': [
        'Exporting Carrier', 'Carrier Name', 'Vessel Name', 'Vessel / Flight', 'Export Carrier'
    ],
    'product_description': [
        'Description of Goods', 'Commodities', 'Nature of Goods', 'Goods Description'
    ],
}



def get_ocr_lines(page_response):
    lines = []
    for page in page_response.full_text_annotation.pages:
        for block in page.blocks:
            for paragraph in block.paragraphs:
                text = ''
                for word in paragraph.words:
                    text += ''.join([s.text for s in word.symbols]) + ' '
                text = text.strip()
                if text:
                    center = get_center(paragraph.bounding_box)
                    lines.append({'text': text, 'x': center[0], 'y': center[1]})
    return lines

def parse_bill_of_lading_fields(ocr_text, page_response):
    lines = get_ocr_lines(page_response)

    bl_number = ""
    bl_match = re.search(r'\b[A-Z]{3,}\d{6,}\b', ocr_text)
    if bl_match:
        bl_number = bl_match.group(0)

    container_numbers = set(re.findall(r'\b([A-Z]{4}\d{7})\b', ocr_text))
    product_description = find_value_near_keyword(lines, FIELD_KEYWORDS['product_description'], direction='below')
    shipper = find_value_near_keyword(lines, FIELD_KEYWORDS['shipper'], direction='below')
    consignee = find_value_near_keyword(lines, FIELD_KEYWORDS['consignee'], direction='below')
    port_of_loading = find_value_near_keyword(lines, FIELD_KEYWORDS['port_of_loading'], direction='right')
    port_of_discharge = find_value_near_keyword(lines, FIELD_KEYWORDS['port_of_discharge'], direction='right')
    flight_or_vessel = find_value_near_keyword(lines, FIELD_KEYWORDS['vessel'], direction='right')

    return {
        'document_type': 'BOL',
        'shipper': shipper,
        'consignee': consignee,
        'port_of_loading': port_of_loading,
        'port_of_discharge': port_of_discharge,
        'bl_number': bl_number,
        'container_numbers': ', '.join(container_numbers),
        'flight_or_vessel': flight_or_vessel,
        'product_description': product_description,
        'raw_text': ocr_text
    }

def parse_air_waybill_fields(ocr_text, page_response):
    lines = [line.strip() for line in ocr_text.split('\n') if line.strip()]

    def find_label_value(label_keywords):
        for i, line in enumerate(lines):
            for keyword in label_keywords:
                if keyword.lower() in line.lower():
                    for j in range(i + 1, i + 4):
                        if j < len(lines):
                            value = lines[j].strip()
                            if value:
                                return re.split(r'[^A-Z\-/ ]+', value)[0].strip()
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

    awb_number = re.search(r'\b\d{3}-\d{7,8}\b', ocr_text)
    awb_number = awb_number.group(0) if awb_number else ""

    shipper = find_first_company_line(["Shipper's Name and Address"], ["Consignee"])
    consignee = find_first_company_line(["Consignee's Name and Address"], ["Issuing Carrier", "Agent"])
    port_of_loading = find_label_value(["Airport of Departure"])
    port_of_discharge = find_label_value(["Airport of Destination"])
    flight_or_vessel = find_label_value(["Requested Flight/Date", "Exporting Carrier"])

    container_numbers = ""
    pkg_match = re.search(r'(\d{1,3})\s*(pieces|pkgs|packages|pcs)', ocr_text, re.IGNORECASE)
    if pkg_match:
        container_numbers = pkg_match.group(1)

    product_description = ""
    for i, line in enumerate(lines):
        if "Nature and Quantity" in line or "Description of Goods" in line:
            for j in range(i + 1, min(i + 5, len(lines))):
                val = lines[j].strip()
                if val and not val.lower().startswith("freight"):
                    product_description = val
                    break
            break

    return {
        'document_type': 'AWB',
        'bl_number': awb_number,
        'shipper': shipper,
        'consignee': consignee,
        'port_of_loading': port_of_loading,
        'port_of_discharge': port_of_discharge,
        'container_numbers': container_numbers,
        'flight_or_vessel': flight_or_vessel,
        'product_description': product_description,
        'raw_text': ocr_text
    }

def extract_fields(file_path):
    print('=== extract_fields function called ===')
    try:
        response = extract_text_from_file(file_path)
        page_response = response.responses[0]
        all_text = page_response.full_text_annotation.text

        if 'AIR WAYBILL' in all_text.upper():
            fields = parse_air_waybill_fields(all_text, page_response)
        else:
            fields = parse_bill_of_lading_fields(all_text, page_response)

        print("flight_or_vessel:", fields.get("flight_or_vessel", ""))
        print("product_description:", fields.get("product_description", ""))

        return fields
    except Exception as e:
        logging.error(f"Vision API failed: {e}")
        return {'error': str(e)}


# # Final extract_fields.py with accurate AWB ports + product description cleanup

# import re
# import os
# import io
# from google.cloud import vision
# from dotenv import load_dotenv
# import logging
# from datetime import datetime

# load_dotenv()
# print("DEBUG: GOOGLE_APPLICATION_CREDENTIALS =", os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))

# logging.basicConfig(level=logging.INFO)
# GOOGLE_CREDENTIALS = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
# if not GOOGLE_CREDENTIALS or not os.path.exists(GOOGLE_CREDENTIALS):
#     raise RuntimeError('Google Vision credentials not found. Please set GOOGLE_APPLICATION_CREDENTIALS in your .env file.')

# client = vision.ImageAnnotatorClient()

# def extract_text_from_file(file_path):
#     return extract_text_from_pdf(file_path)

# def extract_text_from_pdf(pdf_path):
#     with io.open(pdf_path, 'rb') as pdf_file:
#         content = pdf_file.read()
#     mime_type = 'application/pdf'
#     input_doc = vision.InputConfig(content=content, mime_type=mime_type)
#     requests = [
#         vision.AnnotateFileRequest(
#             input_config=input_doc,
#             features=[vision.Feature(type_=vision.Feature.Type.DOCUMENT_TEXT_DETECTION)]
#         )
#     ]
#     response = client.batch_annotate_files(requests=requests)
#     return response.responses[0]

# def get_center(bounding_box):
#     vertices = bounding_box.vertices
#     x = sum(v.x for v in vertices) / 4
#     y = sum(v.y for v in vertices) / 4
#     return (x, y)

# def find_nearest_text_below(label_text, page_response):
#     label_coords = []
#     candidates = []

#     for page in page_response.full_text_annotation.pages:
#         for block in page.blocks:
#             block_text = ""
#             for paragraph in block.paragraphs:
#                 para_text = ""
#                 for word in paragraph.words:
#                     word_text = ''.join([s.text for s in word.symbols])
#                     para_text += word_text + " "
#                 block_text += para_text.strip() + "\n"

#             if label_text.lower() in block_text.lower():
#                 label_coords.append(get_center(block.bounding_box))
#             else:
#                 candidates.append((get_center(block.bounding_box), block_text.strip()))

#     for label in label_coords:
#         below_blocks = [
#             (text, center) for center, text in candidates
#             if center[1] > label[1] and abs(center[0] - label[0]) < 150
#         ]
#         if below_blocks:
#             below_blocks.sort(key=lambda b: b[1][1])
#             return below_blocks[0][0]
#     return ""

# def parse_bill_of_lading_fields(ocr_text, page_response):
#     lines = [line.strip() for line in ocr_text.split('\n') if line.strip()]
#     n = len(lines)

#     def next_nonempty(idx):
#         for i in range(idx + 1, n):
#             if lines[i]:
#                 return lines[i]
#         return ""

#     shipper = ""
#     for i, line in enumerate(lines):
#         if re.match(r'2\.? *EXPORTER', line, re.IGNORECASE):
#             next_line = next_nonempty(i)
#             shipper = next_line.split(',')[0].split('(')[0].strip()
#             break

#     consignee = ""
#     for i, line in enumerate(lines):
#         if re.match(r'3\.? *CONSIGNED TO', line, re.IGNORECASE):
#             name_parts = []
#             for j in range(1, 4):
#                 if i + j < len(lines):
#                     candidate = lines[i + j].strip()
#                     if not candidate:
#                         continue
#                     if re.match(r'(C/O|ATTN|ADDRESS|TEL|FAX)', candidate, re.IGNORECASE):
#                         break
#                     name_parts.append(candidate)
#                     if len(name_parts) >= 2:
#                         break
#             consignee = ' '.join(name_parts)
#             break

#     port_of_loading = ""
#     for i, line in enumerate(lines):
#         if "PORT OF LOADING" in line:
#             port_of_loading = next_nonempty(i)
#             break

#     port_of_discharge = ""
#     for i, line in enumerate(lines):
#         if "PLACE OF DELIVERY BY ON-CARRIER" in line or "FOREIGN PORT OF UNLOADING" in line or "PORT OF DISCHARGE" in line:
#             port_of_discharge = next_nonempty(i)
#             break

#     bl_number = ""
#     for i, line in enumerate(lines):
#         if "B/L NUMBER" in line or "DOCUMENT NUMBER" in line:
#             for j in range(i + 1, min(i + 4, n)):
#                 match = re.search(r'\b[A-Z]{3,}[0-9]{6,}\b', lines[j])
#                 if match:
#                     bl_number = match.group(0)
#                     break
#             if bl_number:
#                 break

#     container_numbers = set()
#     for line in lines:
#         matches = re.findall(r'\b([A-Z]{4}\d{7})\b', line)
#         for match in matches:
#             container_numbers.add(match.strip())
#     container_numbers = ', '.join(container_numbers)

#     flight_or_vessel = ""
#     for i, line in enumerate(lines):
#         if "EXPORTING CARRIER" in line or "VESSEL NAME" in line:
#             flight_or_vessel = next_nonempty(i)
#             break

#     product_description = ""
#     for i, line in enumerate(lines):
#         if re.search(r'(DESCRIPTION OF GOODS|DESCRIPTION OF COMMODITIES)', line, re.IGNORECASE):
#             desc_lines = []
#             for j in range(i + 1, min(i + 6, len(lines))):
#                 candidate = lines[j].strip()
#                 if not candidate or candidate.lower().startswith("freight"):
#                     break
#                 desc_lines.append(candidate)
#             product_description = " ".join(desc_lines).strip()
#             break

#     return {
#         'shipper': shipper,
#         'consignee': consignee,
#         'port_of_loading': port_of_loading,
#         'port_of_discharge': port_of_discharge,
#         'bl_number': bl_number,
#         'container_numbers': container_numbers,
#         'flight_or_vessel': flight_or_vessel,
#         'product_description': product_description,
#         'raw_text': ocr_text
#     }

# def parse_air_waybill_fields(ocr_text, page_response):
#     lines = [line.strip() for line in ocr_text.split('\n') if line.strip()]

#     def find_label_value(label_keywords):
#         for i, line in enumerate(lines):
#             for keyword in label_keywords:
#                 if keyword.lower() in line.lower():
#                     for j in range(i + 1, i + 4):
#                         if j < len(lines):
#                             value = lines[j].strip()
#                             if value:
#                                 return re.split(r'[^A-Z\-/ ]+', value)[0].strip()
#         return ""

#     def find_first_company_line(start_keywords, stop_keywords):
#         collecting = False
#         for line in lines:
#             if any(kw.lower() in line.lower() for kw in start_keywords):
#                 collecting = True
#                 continue
#             if collecting:
#                 if any(stop.lower() in line.lower() for stop in stop_keywords):
#                     break
#                 if re.search(r'[A-Z]{2,}', line):
#                     return line.strip()
#         return ""

#     awb_number = ""
#     awb_match = re.search(r'\b\d{3}-\d{7,8}\b', ocr_text)
#     if awb_match:
#         awb_number = awb_match.group(0)

#     shipper = find_first_company_line(["Shipper's Name and Address"], ["Consignee"])
#     consignee = find_first_company_line(["Consignee's Name and Address"], ["Issuing Carrier", "Agent"])

#     port_of_loading = find_label_value(["Airport of Departure"])
#     port_of_discharge = find_label_value(["Airport of Destination"])

#     container_numbers = ""
#     pkg_match = re.search(r'(\d{1,3})\s*(pieces|pkgs|packages|pcs)', ocr_text, re.IGNORECASE)
#     if pkg_match:
#         container_numbers = pkg_match.group(1)

#     flight_or_vessel = find_label_value(["Requested Flight/Date", "Exporting Carrier"])

#     product_description = ""
#     for i, line in enumerate(lines):
#         if "Nature and Quantity" in line or "Description of Goods" in line:
#             for j in range(i + 1, min(i + 5, len(lines))):
#                 val = lines[j].strip()
#                 if val and not val.lower().startswith("freight"):
#                     product_description = val
#                     break
#             break

#     return {
#         'document_type': 'AWB',
#         'bl_number': awb_number,
#         'shipper': shipper,
#         'consignee': consignee,
#         'port_of_loading': port_of_loading,
#         'port_of_discharge': port_of_discharge,
#         'container_numbers': container_numbers,
#         'flight_or_vessel': flight_or_vessel,
#         'product_description': product_description,
#         'raw_text': ocr_text
#     }

# def extract_fields(file_path):
#     print('=== extract_fields function called ===')
#     try:
#         response = extract_text_from_file(file_path)
#         image_response = response

#         all_text = ""
#         for page_response in image_response.responses:
#             all_text += page_response.full_text_annotation.text + "\n"

#         if 'AIR WAYBILL' in all_text.upper():
#             fields = parse_air_waybill_fields(all_text, page_response)
#         else:

#             fields = parse_bill_of_lading_fields(all_text, page_response)

#         print("flight_or_vessel:", fields.get("flight_or_vessel", ""))
#         print("product_description:", fields.get("product_description", ""))

#         return fields
#     except Exception as e:
#         logging.error(f"Vision API failed: {e}.")
#         return {'error': str(e)}
