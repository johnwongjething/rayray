
# extract_fields_universal_boxlogic.py - patched for bounding-box shipper/consignee, cleaned port logic

import re
import io
import os
from google.cloud import vision
from dotenv import load_dotenv

load_dotenv()
client = vision.ImageAnnotatorClient()

def extract_text_from_pdf(pdf_path):
    with io.open(pdf_path, 'rb') as f:
        content = f.read()
    input_doc = vision.InputConfig(content=content, mime_type='application/pdf')
    feature = vision.Feature(type_=vision.Feature.Type.DOCUMENT_TEXT_DETECTION)
    request = vision.AnnotateFileRequest(input_config=input_doc, features=[feature])
    response = client.batch_annotate_files(requests=[request])
    return response.responses[0]

def get_center(bbox):
    vertices = bbox.vertices
    return sum(v.x for v in vertices) / 4, sum(v.y for v in vertices) / 4

def find_nearest_label_text(target_keywords, blocks):
    result = ""
    candidates = []
    for block in blocks:
        text = ''.join([s.text for p in block.paragraphs for w in p.words for s in w.symbols])
        candidates.append((text.strip(), get_center(block.bounding_box)))

    for keyword in target_keywords:
        for text, center in candidates:
            if keyword.lower() in text.lower():
                nearby = [
                    (t, y) for t, (x, y) in candidates
                    if abs(center[0] - x) < 150 and y > center[1]
                ]
                nearby.sort(key=lambda b: b[1])
                if nearby:
                    return nearby[0][0]
    return ""

def parse_boxes(page_response):
    blocks = []
    for page in page_response.full_text_annotation.pages:
        for block in page.blocks:
            blocks.extend(block.paragraphs)
    return blocks

def parse_bol_fields(ocr_text, page_response):
    text = ocr_text
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    blocks = []
    for page in page_response.full_text_annotation.pages:
        for block in page.blocks:
            blocks.append(block)

    def find_by_prefix(prefixes):
        for block in blocks:
            for para in block.paragraphs:
                for word in para.words:
                    word_text = ''.join([s.text for s in word.symbols])
                    for prefix in prefixes:
                        if prefix.lower() in word_text.lower():
                            full_line = ' '.join(''.join(s.text for s in w.symbols) for w in para.words)
                            return full_line
        return ""

    def find_after_keyword(keywords, default=""):
        for i, line in enumerate(lines):
            for k in keywords:
                if k.lower() in line.lower():
                    if i+1 < len(lines):
                        return lines[i+1]
        return default

    bl_number = ""
    for i, line in enumerate(lines):
        if 'B/L NUMBER' in line.upper() or 'BILL OF LADING NUMBER' in line.upper():
            match = re.search(r'[A-Z0-9]{6,}', line)
            if match:
                bl_number = match.group(0)
        elif 'B/L' in line.upper():
            match = re.search(r'[A-Z0-9]{6,}', line)
            if match:
                bl_number = match.group(0)
    if not bl_number:
        match = re.search(r'\b[A-Z]{3,}\d{6,}\b', text)
        if match:
            bl_number = match.group(0)

    container_numbers = re.findall(r'([A-Z]{4}\d{7})', text)
    container_numbers = ', '.join(sorted(set(container_numbers)))

    shipper = find_after_keyword(['2. EXPORTER', 'SHIPPER'])
    consignee = find_after_keyword(['3. CONSIGNED TO', 'CONSIGNEE'])

    if '\n' in shipper:
        shipper = shipper.split('\n')[0]
    if '\n' in consignee:
        consignee = consignee.split('\n')[0]

    port_of_loading = find_after_keyword(['PORT OF LOADING', 'PORT OF EXPORT'])
    port_of_discharge = find_after_keyword(['PORT OF DISCHARGE', 'PLACE OF DELIVERY', 'FOREIGN PORT OF UNLOADING'])

    vessel = find_after_keyword(['EXPORTING CARRIER', 'VESSEL', 'OCEAN VESSEL'])

    product_description = ""
    for i, line in enumerate(lines):
        if 'DESCRIPTION OF COMMODITIES' in line.upper() or 'DESCRIPTION OF GOODS' in line.upper():
            for j in range(i+1, i+5):
                if j < len(lines) and not lines[j].lower().startswith('freight'):
                    product_description = lines[j]
                    break
            break

    return {
        'document_type': 'BOL',
        'shipper': shipper.strip(),
        'consignee': consignee.strip(),
        'port_of_loading': port_of_loading.strip(),
        'port_of_discharge': port_of_discharge.strip(),
        'bl_number': bl_number.strip(),
        'container_numbers': container_numbers.strip(),
        'flight_or_vessel': vessel.strip(),
        'product_description': product_description.strip(),
        'raw_text': text
    }

def extract_fields(file_path):
    response = extract_text_from_pdf(file_path)
    all_text = ""
    for page_response in response.responses:
        all_text += page_response.full_text_annotation.text + "\n"

    return parse_bol_fields(all_text, response.responses[0])



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
