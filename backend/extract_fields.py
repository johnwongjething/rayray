import re
import io
import os
import logging
from google.cloud import vision
from dotenv import load_dotenv
from typing import List, Dict, Tuple

logging.basicConfig(level=logging.INFO)
load_dotenv()
client = vision.ImageAnnotatorClient()

def extract_text_from_pdf(pdf_path: str) -> vision.AnnotateFileResponse:
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    if not pdf_path.lower().endswith('.pdf'):
        raise ValueError("Input file must be a PDF")
    with io.open(pdf_path, 'rb') as f:
        content = f.read()
    input_doc = vision.InputConfig(content=content, mime_type='application/pdf')
    feature = vision.Feature(type_=vision.Feature.Type.DOCUMENT_TEXT_DETECTION)
    request = vision.AnnotateFileRequest(input_config=input_doc, features=[feature])
    response = client.batch_annotate_files(requests=[request])
    if not response.responses:
        raise ValueError("No response received from Vision API")
    return response.responses[0]

def extract_bl_number(text: str) -> str:
    lines = text.splitlines()
    candidate_labels = ['Waybill No.', 'Document No.', 'Bill of Lading Number', 'B/L No.', 'BL NO', 'B/L NO']
    for i, line in enumerate(lines):
        for label in candidate_labels:
            if label.lower() in line.lower():
                match = re.search(r'[:\s\-]*([A-Z0-9\-]{8,})', line)
                if match:
                    candidate = match.group(1).strip()
                    if candidate.upper() != 'LADING':
                        return candidate
                if i + 1 < len(lines):
                    match2 = re.search(r'\b[A-Z0-9\-]{8,}\b', lines[i + 1])
                    if match2 and match2.group(0).upper() != 'LADING':
                        return match2.group(0)
    match = re.search(r'\b\d{10,}\b|\b[A-Z]{3}\d{6,}\b|\b\d{3}-\d{7,8}\b', text)
    if match and match.group(0).upper() != 'LADING':
        return match.group(0)
    return ""

def parse_bol_fields(ocr_text: str, page_response: vision.AnnotateFileResponse) -> Dict:
    text = ocr_text
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    def find_after_keyword(keywords: List[str], default: str = "") -> str:
        for i, line in enumerate(lines):
            for k in keywords:
                if k.lower() in line.lower():
                    next_line = lines[i + 1] if i + 1 < len(lines) else ""
                    if next_line:
                        return next_line.split('\n')[0].strip()
        return default

    def find_port_after_keyword(keywords: List[str], default: str = "") -> str:
        for i, line in enumerate(lines):
            for k in keywords:
                if k.lower() in line.lower():
                    next_line = lines[i + 1] if i + 1 < len(lines) else ""
                    if next_line:
                        return next_line.split(',')[0].strip()
        return default

    bl_number = extract_bl_number(text)
    container_numbers = ', '.join(sorted(set(re.findall(r'([A-Z]{4}\d{7})', text))))
    shipper = find_after_keyword(['2. exporter', 'shipper', 'shippe'])
    consignee = find_after_keyword(['3. consigned to', 'consignee'])
    port_of_loading = find_port_after_keyword(['port of loading', 'port of export', 'place of receipt'])
    port_of_discharge = find_port_after_keyword(['port of discharge', 'place of delivery', 'foreign port of unloading'])
    vessel = find_after_keyword(['exporting carrier', 'vessel', 'ocean vessel'])

    # Override for CMA CGM
    if 'CMA CGM' in text.upper():
        port_match = re.search(r'PORT OF LOADING\s*[\n:]?\s*(.+)', text, re.IGNORECASE)
        if port_match:
            possible_port = port_match.group(1).strip()
            if "FREIGHT" not in possible_port.upper() and len(possible_port) <= 30:
                port_of_loading = possible_port

    product_description = ""
    for i, line in enumerate(lines):
        if 'description of commodities' in line.lower() or 'description of goods' in line.lower():
            for j in range(i + 1, i + 5):
                if j < len(lines) and not lines[j].lower().startswith('freight'):
                    product_description = lines[j]
                    break
            break

    return {
        'document_type': 'BOL',
        'shipper': shipper,
        'consignee': consignee,
        'port_of_loading': port_of_loading,
        'port_of_discharge': port_of_discharge,
        'bl_number': bl_number,
        'container_numbers': container_numbers,
        'flight_or_vessel': vessel,
        'product_description': product_description,
        'raw_text': text
    }

def parse_air_waybill_fields(ocr_text: str, page_response: vision.AnnotateFileResponse) -> Dict:
    lines = [line.strip() for line in ocr_text.splitlines() if line.strip()]

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

    awb_number = ""
    awb_match = re.search(r'\b\d{3}-\d{7,8}\b', ocr_text)
    if awb_match:
        awb_number = awb_match.group(0)

    shipper = find_first_company_line(["Shipper's Name and Address"], ["Consignee"])
    consignee = find_first_company_line(["Consignee's Name and Address"], ["Issuing Carrier", "Agent"])
    port_of_loading = find_label_value(["Airport of Departure"])
    port_of_discharge = find_label_value(["Airport of Destination"])
    container_numbers = ""
    pkg_match = re.search(r'(\d{1,3})\s*(pieces|pkgs|packages|pcs)', ocr_text, re.IGNORECASE)
    if pkg_match:
        container_numbers = pkg_match.group(1)

    flight_or_vessel = find_label_value(["Requested Flight/Date", "Exporting Carrier"])
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

def extract_fields(file_path: str) -> Dict:
    print('=== extract_fields function called ===')
    try:
        response = extract_text_from_pdf(file_path)
        all_text = ""
        for page_response in response.responses:
            all_text += page_response.full_text_annotation.text + "\n"

        if 'AIR WAYBILL' in all_text.upper():
            fields = parse_air_waybill_fields(all_text, response.responses[0])
        else:
            fields = parse_bol_fields(all_text, response.responses[0])

        print("flight_or_vessel:", fields.get("flight_or_vessel", ""))
        print("product_description:", fields.get("product_description", ""))

        return fields
    except Exception as e:
        logging.error(f"Vision API failed: {e}.")
        return {'error': str(e)}

if __name__ == "__main__":
    result = extract_fields("your_pdf_file.pdf")
    print(result)

# import re
# import io
# import os
# import logging
# from google.cloud import vision
# from dotenv import load_dotenv
# from typing import List, Dict, Tuple

# logging.basicConfig(level=logging.INFO)
# load_dotenv()
# client = vision.ImageAnnotatorClient()

# def extract_text_from_pdf(pdf_path: str) -> vision.AnnotateFileResponse:
#     if not os.path.exists(pdf_path):
#         raise FileNotFoundError(f"PDF file not found: {pdf_path}")
#     if not pdf_path.lower().endswith('.pdf'):
#         raise ValueError("Input file must be a PDF")
#     with io.open(pdf_path, 'rb') as f:
#         content = f.read()
#     input_doc = vision.InputConfig(content=content, mime_type='application/pdf')
#     feature = vision.Feature(type_=vision.Feature.Type.DOCUMENT_TEXT_DETECTION)
#     request = vision.AnnotateFileRequest(input_config=input_doc, features=[feature])
#     response = client.batch_annotate_files(requests=[request])
#     if not response.responses:
#         raise ValueError("No response received from Vision API")
#     return response.responses[0]

# def extract_bl_number(text: str) -> str:
#     lines = text.splitlines()
#     candidate_labels = ['Waybill No.', 'Document No.', 'Bill of Lading Number', 'B/L No.', 'BL NO', 'B/L NO']
#     for i, line in enumerate(lines):
#         for label in candidate_labels:
#             if label.lower() in line.lower():
#                 match = re.search(r'[:\s\-]*([A-Z0-9\-]{8,})', line)
#                 if match:
#                     candidate = match.group(1).strip()
#                     if candidate.upper() != 'LADING':
#                         return candidate
#                 if i + 1 < len(lines):
#                     match2 = re.search(r'\b[A-Z0-9\-]{8,}\b', lines[i + 1])
#                     if match2 and match2.group(0).upper() != 'LADING':
#                         return match2.group(0)
#     match = re.search(r'\b\d{10,}\b|\b[A-Z]{3}\d{6,}\b|\b\d{3}-\d{7,8}\b', text)
#     if match and match.group(0).upper() != 'LADING':
#         return match.group(0)
#     return ""

# def parse_bol_fields(ocr_text: str, page_response: vision.AnnotateFileResponse) -> Dict:
#     text = ocr_text
#     lines = [line.strip() for line in text.splitlines() if line.strip()]

#     def find_after_keyword(keywords: List[str], default: str = "") -> str:
#         for i, line in enumerate(lines):
#             for k in keywords:
#                 if k.lower() in line.lower():
#                     next_line = lines[i + 1] if i + 1 < len(lines) else ""
#                     if next_line:
#                         return next_line.split('\n')[0].strip()
#         return default

#     def find_port_after_keyword(keywords: List[str], default: str = "") -> str:
#         for i, line in enumerate(lines):
#             for k in keywords:
#                 if k.lower() in line.lower():
#                     next_line = lines[i + 1] if i + 1 < len(lines) else ""
#                     if next_line:
#                         return next_line.split(',')[0].strip()
#         return default

#     bl_number = extract_bl_number(text)
#     container_numbers = ', '.join(sorted(set(re.findall(r'([A-Z]{4}\d{7})', text))))
#     shipper = find_after_keyword(['2. exporter', 'shipper', 'shippe'])
#     consignee = find_after_keyword(['3. consigned to', 'consignee'])
#     port_of_loading = find_port_after_keyword(['port of loading', 'port of export', 'place of receipt'])
#     port_of_discharge = find_port_after_keyword(['port of discharge', 'place of delivery', 'foreign port of unloading'])
#     vessel = find_after_keyword(['exporting carrier', 'vessel', 'ocean vessel'])

#     # Override for CMA CGM
#     if 'CMA CGM' in text.upper():
#         port_match = re.search(r'PORT OF LOADING\s*[\n:]?\s*(.+)', text, re.IGNORECASE)
#         if port_match:
#             possible_port = port_match.group(1).strip()
#             if "FREIGHT" not in possible_port.upper() and len(possible_port) <= 30:
#                 port_of_loading = possible_port

#     product_description = ""
#     for i, line in enumerate(lines):
#         if 'description of commodities' in line.lower() or 'description of goods' in line.lower():
#             for j in range(i + 1, i + 5):
#                 if j < len(lines) and not lines[j].lower().startswith('freight'):
#                     product_description = lines[j]
#                     break
#             break

#     return {
#         'document_type': 'BOL',
#         'shipper': shipper,
#         'consignee': consignee,
#         'port_of_loading': port_of_loading,
#         'port_of_discharge': port_of_discharge,
#         'bl_number': bl_number,
#         'container_numbers': container_numbers,
#         'flight_or_vessel': vessel,
#         'product_description': product_description,
#         'raw_text': text
#     }

# def parse_air_waybill_fields(ocr_text: str, page_response: vision.AnnotateFileResponse) -> Dict:
#     lines = [line.strip() for line in ocr_text.splitlines() if line.strip()]

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

# def extract_fields(file_path: str) -> Dict:
#     print('=== extract_fields function called ===')
#     try:
#         response = extract_text_from_pdf(file_path)
#         all_text = ""
#         for page_response in response.responses:
#             all_text += page_response.full_text_annotation.text + "\n"

#         if 'AIR WAYBILL' in all_text.upper():
#             fields = parse_air_waybill_fields(all_text, response.responses[0])
#         else:
#             fields = parse_bol_fields(all_text, response.responses[0])

#         print("flight_or_vessel:", fields.get("flight_or_vessel", ""))
#         print("product_description:", fields.get("product_description", ""))

#         return fields
#     except Exception as e:
#         logging.error(f"Vision API failed: {e}.")
#         return {'error': str(e)}

# if __name__ == "__main__":
#     result = extract_fields("your_pdf_file.pdf")
#     print(result)



# import re
# import io
# import os
# import logging
# from google.cloud import vision
# from dotenv import load_dotenv
# from typing import List, Dict, Tuple

# logging.basicConfig(level=logging.INFO)
# load_dotenv()
# client = vision.ImageAnnotatorClient()

# def extract_text_from_pdf(pdf_path: str) -> vision.AnnotateFileResponse:
#     if not os.path.exists(pdf_path):
#         raise FileNotFoundError(f"PDF file not found: {pdf_path}")
#     if not pdf_path.lower().endswith('.pdf'):
#         raise ValueError("Input file must be a PDF")
#     with io.open(pdf_path, 'rb') as f:
#         content = f.read()
#     input_doc = vision.InputConfig(content=content, mime_type='application/pdf')
#     feature = vision.Feature(type_=vision.Feature.Type.DOCUMENT_TEXT_DETECTION)
#     request = vision.AnnotateFileRequest(input_config=input_doc, features=[feature])
#     response = client.batch_annotate_files(requests=[request])
#     if not response.responses:
#         raise ValueError("No response received from Vision API")
#     return response.responses[0]

# def get_center(bbox: vision.BoundingPoly) -> Tuple[float, float]:
#     vertices = bbox.vertices
#     return sum(v.x for v in vertices) / 4, sum(v.y for v in vertices) / 4

# def find_nearest_label_text(target_keywords: List[str], blocks: List[vision.Block]) -> str:
#     candidates = []
#     for block in blocks:
#         text = ''.join(s.text for p in block.paragraphs for w in p.words for s in w.symbols)
#         candidates.append((text.strip(), get_center(block.bounding_box)))
#     for keyword in target_keywords:
#         for text, center in candidates:
#             if any(k.lower() in text.lower() for k in keyword.split()):
#                 nearby = [(t, y) for t, (x, y) in candidates if abs(center[0] - x) < 150 and y > center[1]]
#                 nearby.sort(key=lambda b: b[1])
#                 if nearby:
#                     return nearby[0][0]
#     return ""

# def extract_bl_number(text: str) -> str:
#     """Improved logic to extract B/L or Waybill number, avoiding false positives like 'LADING'."""
#     lines = text.splitlines()
#     candidate_labels = ['Waybill No.', 'Document No.', 'Bill of Lading Number', 'B/L No.', 'BL NO', 'B/L NO']

#     for i, line in enumerate(lines):
#         for label in candidate_labels:
#             if label.lower() in line.lower():
#                 # Extract a clean alphanumeric string after the label
#                 match = re.search(r'[:\s\-]*([A-Z0-9\-]{8,})', line)
#                 if match:
#                     candidate = match.group(1).strip()
#                     if candidate.upper() != 'LADING':
#                         return candidate
#                 # Also check next line in case number is there
#                 if i + 1 < len(lines):
#                     match2 = re.search(r'\b[A-Z0-9\-]{8,}\b', lines[i + 1])
#                     if match2 and match2.group(0).upper() != 'LADING':
#                         return match2.group(0)

#     # Fallback (very relaxed)
#     match = re.search(r'\b\d{10,}\b|\b[A-Z]{3}\d{6,}\b|\b\d{3}-\d{7,8}\b', text)
#     if match and match.group(0).upper() != 'LADING':
#         return match.group(0)

#     return ""

# def extract_first_line_near_label(boxes: List[Dict], label_keywords: List[str]) -> str:
#     label_boxes = [b for b in boxes if any(k.lower() in b['text'].lower() for k in label_keywords)]
#     if not label_boxes:
#         return ''
#     label_box = label_boxes[0]
#     label_y = (label_box['top'] + label_box['bottom']) / 2
#     center_x = (label_box['left'] + label_box['right']) / 2
#     candidates = [
#         b for b in boxes 
#         if b['top'] > label_y and abs(((b['left'] + b['right']) / 2) - center_x) < 300
#     ]
#     candidates.sort(key=lambda b: b['top'])
#     if candidates:
#         for candidate in candidates[:3]:
#             text = candidate['text'].strip()
#             if not any(k.lower() in text.lower() for k in label_keywords):
#                 return text
#         return candidates[0]['text'].strip() if candidates else ''
#     return ''



# def parse_bol_fields(ocr_text: str, page_response: vision.AnnotateFileResponse) -> Dict:
#     """Extract fields for Bill of Lading."""
#     text = ocr_text
#     lines = [line.strip() for line in text.splitlines() if line.strip()]
#     blocks = []
#     for page in page_response.full_text_annotation.pages:
#         for block in page.blocks:
#             blocks.append(block)

#     def find_after_keyword(keywords: List[str], default: str = "") -> str:
#         for i, line in enumerate(lines):
#             for k in keywords:
#                 if k.lower() in line.lower():
#                     next_line = lines[i + 1] if i + 1 < len(lines) else ""
#                     if next_line:
#                         return next_line.split('\n')[0].strip()
#         return default

#     def find_port_after_keyword(keywords: List[str], default: str = "") -> str:
#         for i, line in enumerate(lines):
#             for k in keywords:
#                 if k.lower() in line.lower():
#                     next_line = lines[i + 1] if i + 1 < len(lines) else ""
#                     if next_line:
#                         return next_line.split(',')[0].strip()
#         return default

#     bl_number = extract_bl_number(text)

#     container_numbers = ', '.join(sorted(set(re.findall(r'([A-Z]{4}\d{7})', text) + re.findall(r'(?:CONTAINER|MRKU|Seal)\s*[NO.]?\s*(\w{4}\d{7})', text, re.IGNORECASE))))

#     shipper = find_after_keyword(['2. exporter', 'shipper', 'shippe'])
#     consignee = find_after_keyword(['3. consigned to', 'consignee'])
#     port_of_loading = find_port_after_keyword([
#     'port of loading', 'port of export', 'place of receipt', 'place of receipt/date', '(13) Place of Receipt/Date'
# ])

#     port_of_discharge = find_port_after_keyword(['port of discharge', 'place of delivery', 'foreign port of unloading'])
#     vessel = find_after_keyword(['exporting carrier', 'vessel', 'ocean vessel'])

#     product_description = ""
#     for i, line in enumerate(lines):
#         if 'description of commodities' in line.lower() or 'description of goods' in line.lower():
#             for j in range(i + 1, i + 5):
#                 if j < len(lines) and not lines[j].lower().startswith('freight'):
#                     product_description = lines[j]
#                     break
#             break

#     return {
#         'document_type': 'BOL',
#         'shipper': shipper,
#         'consignee': consignee,
#         'port_of_loading': port_of_loading,
#         'port_of_discharge': port_of_discharge,
#         'bl_number': bl_number,
#         'container_numbers': container_numbers,
#         'flight_or_vessel': vessel,
#         'product_description': product_description,
#         'raw_text': text
#     }

# def parse_air_waybill_fields(ocr_text: str, page_response: vision.AnnotateFileResponse) -> Dict:
#     """Extract fields for Air Waybill."""
#     lines = [line.strip() for line in ocr_text.splitlines() if line.strip()]

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

# def extract_fields(file_path: str) -> Dict:
#     """Get all fields from a PDF, detecting BOL or AWB."""
#     print('=== extract_fields function called ===')
#     try:
#         response = extract_text_from_pdf(file_path)
#         all_text = ""
#         for page_response in response.responses:
#             all_text += page_response.full_text_annotation.text + "\n"

#         if 'AIR WAYBILL' in all_text.upper():
#             fields = parse_air_waybill_fields(all_text, response.responses[0])
#         else:
#             fields = parse_bol_fields(all_text, response.responses[0])

#         print("flight_or_vessel:", fields.get("flight_or_vessel", ""))
#         print("product_description:", fields.get("product_description", ""))

#         return fields
#     except Exception as e:
#         logging.error(f"Vision API failed: {e}.")
#         return {'error': str(e)}

# if __name__ == "__main__":
#     result = extract_fields("your_pdf_file.pdf")
#     print(result)

# import re
# import io
# import os
# import logging
# from google.cloud import vision
# from dotenv import load_dotenv
# from typing import List, Dict, Tuple

# # Set up logging to show messages if something goes wrong
# logging.basicConfig(level=logging.INFO)

# # Load environment settings (like Google Cloud credentials)
# load_dotenv()
# if not os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
#     raise ValueError("Google Cloud credentials not found in .env file")
# client = vision.ImageAnnotatorClient()

# def extract_text_from_pdf(pdf_path: str) -> vision.AnnotateFileResponse:
#     """Get text from a PDF using Google Cloud Vision."""
#     if not os.path.exists(pdf_path):
#         raise FileNotFoundError(f"PDF file not found: {pdf_path}")
#     if not pdf_path.lower().endswith('.pdf'):
#         raise ValueError("Input file must be a PDF")
    
#     try:
#         with io.open(pdf_path, 'rb') as f:
#             content = f.read()
#         input_doc = vision.InputConfig(content=content, mime_type='application/pdf')
#         feature = vision.Feature(type_=vision.Feature.Type.DOCUMENT_TEXT_DETECTION)
#         request = vision.AnnotateFileRequest(input_config=input_doc, features=[feature])
#         response = client.batch_annotate_files(requests=[request])
#         if not response.responses:
#             raise ValueError("No response received from Vision API")
#         return response.responses[0]
#     except Exception as e:
#         raise Exception(f"Error processing PDF with Vision API: {str(e)}")

# def get_center(bbox: vision.BoundingPoly) -> Tuple[float, float]:
#     """Find the center of a text box."""
#     vertices = bbox.vertices
#     return sum(v.x for v in vertices) / 4, sum(v.y for v in vertices) / 4

# def find_nearest_label_text(target_keywords: List[str], blocks: List[vision.Block]) -> str:
#     """Find text near a label with specific keywords."""
#     candidates = []
#     for block in blocks:
#         text = ''.join(s.text for p in block.paragraphs for w in p.words for s in w.symbols)
#         candidates.append((text.strip(), get_center(block.bounding_box)))

#     for keyword in target_keywords:
#         for text, center in candidates:
#             if any(k.lower() in text.lower() for k in keyword.split()):
#                 nearby = [
#                     (t, y) for t, (x, y) in candidates
#                     if abs(center[0] - x) < 150 and y > center[1]
#                 ]
#                 nearby.sort(key=lambda b: b[1])
#                 if nearby:
#                     return nearby[0][0]
#     return ""

# def extract_bl_number(text: str) -> str:
#     """Find the B/L number, prioritizing near 'B/L' or 'BILL OF LADING' labels."""
#     lines = text.splitlines()
#     for i, line in enumerate(lines):
#         if any(label in line.upper() for label in ['B/L NO.', 'B/L NUMBER', 'BILL OF LADING NUMBER', 'B/L NO', 'BL NO']):
#             match = re.search(r'(?:B/L\s*No\.\s*)?(\w{3}\d{6,})', line)
#             if match:
#                 return match.group(1)
#             if i + 1 < len(lines):
#                 next_match = re.search(r'\w{3}\d{6,}', lines[i + 1])
#                 if next_match:
#                     return next_match.group(0)
#     # Fallback to general pattern with stricter criteria
#     match = re.search(r'\b[A-Z]{3}\d{6,}\b(?![^\n]*CONSIGNEE|\s*EXPORT)', text)
#     return match.group(0) if match else ''

# def extract_first_line_near_label(boxes: List[Dict], label_keywords: List[str]) -> str:
#     """Get the line with BL number pattern below a label."""
#     label_boxes = [b for b in boxes if any(k.lower() in b['text'].lower() for k in label_keywords)]
#     if not label_boxes:
#         return ''
#     label_box = label_boxes[0]
#     label_y = (label_box['top'] + label_box['bottom']) / 2
#     center_x = (label_box['left'] + label_box['right']) / 2
#     candidates = [
#         b for b in boxes 
#         if b['top'] > label_y and abs(((b['left'] + b['right']) / 2) - center_x) < 300
#     ]
#     candidates.sort(key=lambda b: b['top'])
#     if candidates:
#         for candidate in candidates[:3]:  # Check up to 3 lines below
#             text = candidate['text'].strip()
#             if not any(k.lower() in text.lower() for k in label_keywords):  # Exclude label itself
#                 return text
#         return candidates[0]['text'].strip() if candidates else ''
#     return ''

# def parse_boxes(blocks: List[vision.Block], full_text: str) -> Dict:
#     """Extract fields using the position of text boxes."""
#     boxes = []
#     for block in blocks:
#         if not hasattr(block, 'bounding_box') or not block.bounding_box.vertices:
#             logging.warning(f"Skipping block with no valid bounding box: {''.join(s.text for p in block.paragraphs for w in p.words for s in w.symbols)}")
#             continue
#         try:
#             boxes.append({
#                 'text': ''.join(s.text for p in block.paragraphs for w in p.words for s in w.symbols),
#                 'top': min(v.y for v in block.bounding_box.vertices),
#                 'bottom': max(v.y for v in block.bounding_box.vertices),
#                 'left': min(v.x for v in block.bounding_box.vertices),
#                 'right': max(v.x for v in block.bounding_box.vertices)
#             })
#         except ValueError as e:
#             logging.error(f"Error processing block: {str(e)}")
#             continue
    
#     shipper_text = extract_first_line_near_label(boxes, ['shipper', 'exporter', 'shippe'])
#     consignee_text = extract_first_line_near_label(boxes, ['consignee', 'consigned to'])
#     bl_number = extract_first_line_near_label(boxes, ['b/l number', 'bill of lading number', 'b/l no.', 'bl', 'sa. b/l number', 'export references'])
#     if not bl_number:
#         bl_number = extract_bl_number(full_text)
    
#     return {
#         'document_type': 'BOL',
#         'shipper': shipper_text.split('\n')[0] if shipper_text else '',
#         'consignee': consignee_text.split('\n')[0] if consignee_text else '',
#         'port_of_loading': extract_first_line_near_label(boxes, ['port of loading', 'place of receipt']).split(',')[0].strip() if extract_first_line_near_label(boxes, ['port of loading', 'place of receipt']) else '',
#         'port_of_discharge': extract_first_line_near_label(boxes, ['port of discharge', 'place of delivery']).split(',')[0].strip() if extract_first_line_near_label(boxes, ['port of discharge', 'place of delivery']) else '',
#         'bl_number': bl_number,
#         'container_numbers': ', '.join(set(re.findall(r'\b[A-Z]{4}\d{7}\b', full_text) + re.findall(r'(?:CONTAINER|MRKU|Seal)\s*[NO.]?\s*(\w{4}\d{7})', full_text, re.IGNORECASE))),
#         'flight_or_vessel': extract_first_line_near_label(boxes, ['vessel', 'exporting carrier', 'ocean vessel']).split('\n')[0] if extract_first_line_near_label(boxes, ['vessel', 'exporting carrier', 'ocean vessel']) else '',
#         'product_description': '',
#         'raw_text': full_text
#     }

# def parse_bol_fields(ocr_text: str, page_response: vision.AnnotateFileResponse) -> Dict:
#     """Extract fields by searching the text for keywords."""
#     text = ocr_text
#     lines = [line.strip() for line in text.splitlines() if line.strip()]
#     blocks = []
#     for page in page_response.full_text_annotation.pages:
#         for block in page.blocks:
#             blocks.append(block)

#     def find_after_keyword(keywords: List[str], default: str = "") -> str:
#         for i, line in enumerate(lines):
#             for k in keywords:
#                 if k.lower() in line.lower():
#                     next_line = lines[i + 1] if i + 1 < len(lines) else ""
#                     if next_line:
#                         return next_line.split('\n')[0].strip()
#         return default

#     def find_port_after_keyword(keywords: List[str], default: str = "") -> str:
#         for i, line in enumerate(lines):
#             for k in keywords:
#                 if k.lower() in line.lower():
#                     next_line = lines[i + 1] if i + 1 < len(lines) else ""
#                     if next_line:
#                         return next_line.split(',')[0].strip()
#         return default

#     bl_number = extract_bl_number(text)

#     container_numbers = ', '.join(sorted(set(re.findall(r'([A-Z]{4}\d{7})', text) + re.findall(r'(?:CONTAINER|MRKU|Seal)\s*[NO.]?\s*(\w{4}\d{7})', text, re.IGNORECASE))))

#     shipper = find_after_keyword(['2. exporter', 'shipper', 'shippe'])
#     consignee = find_after_keyword(['3. consigned to', 'consignee'])

#     port_of_loading = find_port_after_keyword(['port of loading', 'port of export'])
#     port_of_discharge = find_port_after_keyword(['port of discharge', 'place of delivery', 'foreign port of unloading'])
#     vessel = find_after_keyword(['exporting carrier', 'vessel', 'ocean vessel'])

#     product_description = ""
#     for i, line in enumerate(lines):
#         if 'description of commodities' in line.lower() or 'description of goods' in line.lower():
#             for j in range(i + 1, i + 5):
#                 if j < len(lines) and not lines[j].lower().startswith('freight'):
#                     product_description = lines[j]
#                     break
#             break

#     return {
#         'document_type': 'BOL',
#         'shipper': shipper,
#         'consignee': consignee,
#         'port_of_loading': port_of_loading,
#         'port_of_discharge': port_of_discharge,
#         'bl_number': bl_number,
#         'container_numbers': container_numbers,
#         'flight_or_vessel': vessel,
#         'product_description': product_description,
#         'raw_text': text
#     }

# def extract_fields(file_path: str) -> Dict:
#     """Get all BOL fields from a PDF and combine different ways of finding them.

#     Args:
#         file_path: The location of the PDF file on your computer.

#     Returns:
#         A dictionary with all the extracted fields.
#     """
#     try:
#         response = extract_text_from_pdf(file_path)
#     except Exception as e:
#         logging.error(f"Failed to extract text from PDF: {str(e)}")
#         return {
#             'document_type': 'BOL',
#             'shipper': '', 'consignee': '', 'port_of_loading': '', 'port_of_discharge': '',
#             'bl_number': '', 'container_numbers': '', 'flight_or_vessel': '', 'product_description': '',
#             'raw_text': ''
#         }

#     all_text = ""
#     all_blocks = []
#     for page_response in response.responses:
#         if not page_response.full_text_annotation:
#             logging.warning("No text annotations found in page response")
#             continue
#         all_text += page_response.full_text_annotation.text + "\n"
#         for page in page_response.full_text_annotation.pages:
#             all_blocks.extend(page.blocks)

#     if not all_blocks or not all_text.strip():
#         logging.warning("No valid blocks or text extracted from PDF")
#         return {
#             'document_type': 'BOL',
#             'shipper': '', 'consignee': '', 'port_of_loading': '', 'port_of_discharge': '',
#             'bl_number': '', 'container_numbers': '', 'flight_or_vessel': '', 'product_description': '',
#             'raw_text': ''
#         }

#     text_result = parse_bol_fields(all_text, response.responses[0])
#     spatial_result = parse_boxes(all_blocks, all_text)

#     combined_result = {}
#     for key in text_result:
#         combined_result[key] = text_result[key] if text_result[key] else spatial_result.get(key, '')

#     return combined_result

# if __name__ == "__main__":
#     result = extract_fields("your_pdf_file.pdf")
#     print(result)


# extract_fields_universal_boxlogic.py - patched for bounding-box shipper/consignee, cleaned port logic

# import re
# import io
# import os
# from google.cloud import vision
# from dotenv import load_dotenv

# load_dotenv()
# client = vision.ImageAnnotatorClient()

# def extract_text_from_pdf(pdf_path):
#     with io.open(pdf_path, 'rb') as f:
#         content = f.read()
#     input_doc = vision.InputConfig(content=content, mime_type='application/pdf')
#     feature = vision.Feature(type_=vision.Feature.Type.DOCUMENT_TEXT_DETECTION)
#     request = vision.AnnotateFileRequest(input_config=input_doc, features=[feature])
#     response = client.batch_annotate_files(requests=[request])
#     return response.responses[0]

# def get_center(bbox):
#     vertices = bbox.vertices
#     return sum(v.x for v in vertices) / 4, sum(v.y for v in vertices) / 4

# def find_nearest_label_text(target_keywords, blocks):
#     result = ""
#     candidates = []
#     for block in blocks:
#         text = ''.join([s.text for p in block.paragraphs for w in p.words for s in w.symbols])
#         candidates.append((text.strip(), get_center(block.bounding_box)))

#     for keyword in target_keywords:
#         for text, center in candidates:
#             if keyword.lower() in text.lower():
#                 nearby = [
#                     (t, y) for t, (x, y) in candidates
#                     if abs(center[0] - x) < 150 and y > center[1]
#                 ]
#                 nearby.sort(key=lambda b: b[1])
#                 if nearby:
#                     return nearby[0][0]
#     return ""



# def parse_boxes(page_response):
#     blocks = []
#     for page in page_response.full_text_annotation.pages:
#         for block in page.blocks:
#             blocks.extend(block.paragraphs)
#     return blocks

# def parse_bol_fields(ocr_text, page_response):
#     text = ocr_text
#     lines = [line.strip() for line in text.splitlines() if line.strip()]
#     blocks = []
#     for page in page_response.full_text_annotation.pages:
#         for block in page.blocks:
#             blocks.append(block)

#     def find_by_prefix(prefixes):
#         for block in blocks:
#             for para in block.paragraphs:
#                 for word in para.words:
#                     word_text = ''.join([s.text for s in word.symbols])
#                     for prefix in prefixes:
#                         if prefix.lower() in word_text.lower():
#                             full_line = ' '.join(''.join(s.text for s in w.symbols) for w in para.words)
#                             return full_line
#         return ""

#     def find_after_keyword(keywords, default=""):
#         for i, line in enumerate(lines):
#             for k in keywords:
#                 if k.lower() in line.lower():
#                     if i+1 < len(lines):
#                         return lines[i+1]
#         return default

#     bl_number = ""
#     for i, line in enumerate(lines):
#         if 'B/L NUMBER' in line.upper() or 'BILL OF LADING NUMBER' in line.upper():
#             match = re.search(r'[A-Z0-9]{6,}', line)
#             if match:
#                 bl_number = match.group(0)
#         elif 'B/L' in line.upper():
#             match = re.search(r'[A-Z0-9]{6,}', line)
#             if match:
#                 bl_number = match.group(0)
#     if not bl_number:
#         match = re.search(r'\b[A-Z]{3,}\d{6,}\b', text)
#         if match:
#             bl_number = match.group(0)

#     container_numbers = re.findall(r'([A-Z]{4}\d{7})', text)
#     container_numbers = ', '.join(sorted(set(container_numbers)))

#     shipper = find_after_keyword(['2. EXPORTER', 'SHIPPER'])
#     consignee = find_after_keyword(['3. CONSIGNED TO', 'CONSIGNEE'])

#     if '\n' in shipper:
#         shipper = shipper.split('\n')[0]
#     if '\n' in consignee:
#         consignee = consignee.split('\n')[0]

#     port_of_loading = find_after_keyword(['PORT OF LOADING', 'PORT OF EXPORT'])
#     port_of_discharge = find_after_keyword(['PORT OF DISCHARGE', 'PLACE OF DELIVERY', 'FOREIGN PORT OF UNLOADING'])

#     vessel = find_after_keyword(['EXPORTING CARRIER', 'VESSEL', 'OCEAN VESSEL'])

#     product_description = ""
#     for i, line in enumerate(lines):
#         if 'DESCRIPTION OF COMMODITIES' in line.upper() or 'DESCRIPTION OF GOODS' in line.upper():
#             for j in range(i+1, i+5):
#                 if j < len(lines) and not lines[j].lower().startswith('freight'):
#                     product_description = lines[j]
#                     break
#             break

#     return {
#         'document_type': 'BOL',
#         'shipper': shipper.strip(),
#         'consignee': consignee.strip(),
#         'port_of_loading': port_of_loading.strip(),
#         'port_of_discharge': port_of_discharge.strip(),
#         'bl_number': bl_number.strip(),
#         'container_numbers': container_numbers.strip(),
#         'flight_or_vessel': vessel.strip(),
#         'product_description': product_description.strip(),
#         'raw_text': text
#     }

# def extract_fields(file_path):
#     response = extract_text_from_pdf(file_path)
#     all_text = ""
#     for page_response in response.responses:
#         all_text += page_response.full_text_annotation.text + "\n"

#     return parse_bol_fields(all_text, response.responses[0])



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
