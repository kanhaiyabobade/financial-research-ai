import fitz
import re
from typing import Dict, Any

def clean_extracted_text(text: str) -> str:
    """
    Cleans raw extracted PDF text by removing excessive blank lines,
    null bytes, and repeated header artifacts.
    """
    if not text:
        return ""
    # Remove null bytes
    cleaned = text.replace("\x00", "")
    # Normalize multiple newlines to max 2
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    # Remove trailing spaces from lines
    cleaned = "\n".join(line.strip() for line in cleaned.splitlines())
    return cleaned.strip()

def segment_drhp_by_topics(text: str) -> Dict[str, str]:
    """
    Segments the extracted DRHP text into key topic areas based on section titles.
    """
    cleaned = clean_extracted_text(text)
    if not cleaned:
        return {}
        
    sections = {
        "Executive Summary": "",
        "Risk Factors": "",
        "Business Overview": "",
        "Financial Statements": "",
        "Objects of the Offer": "",
        "Promoters & Management": "",
        "Legal & Regulatory": ""
    }
    
    # 1. Executive summary (First 20,000 chars)
    sections["Executive Summary"] = cleaned[:20000]
    
    # Keyword map for topic boundary detection
    topic_keywords = {
        "Objects of the Offer": ["OBJECTS OF THE OFFER", "USE OF PROCEEDS", "OBJECTS OF THE ISSUE"],
        "Risk Factors": ["SECTION III: RISK FACTORS", "RISK FACTORS", "INTERNAL RISK FACTORS"],
        "Business Overview": ["OUR BUSINESS", "COMPANY OVERVIEW", "BUSINESS MODEL"],
        "Financial Statements": ["FINANCIAL INFORMATION", "FINANCIAL STATEMENTS", "SUMMARY FINANCIAL INFORMATION"],
        "Promoters & Management": ["OUR PROMOTERS", "BOARD OF DIRECTORS", "MANAGEMENT DISCUSSION"],
        "Legal & Regulatory": ["LEGAL AND OTHER INFORMATION", "PENDING LITIGATION", "OUTSTANDING LITIGATION"]
    }
    
    cleaned_lower = cleaned.lower()
    snippet_len = 12000
    
    for topic, kws in topic_keywords.items():
        matched_text = ""
        for kw in kws:
            pos = cleaned_lower.find(kw.lower())
            if pos != -1:
                matched_text = cleaned[pos : pos + snippet_len]
                break
        sections[topic] = matched_text if matched_text else "Section heading not explicitly isolated."
        
    return sections

def extract_pdf_data(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    """
    Extracts text and metadata from PDF bytes in memory.
    
    Args:
        file_bytes (bytes): The raw bytes of the PDF file.
        filename (str): The name of the PDF file.
        
    Returns:
        Dict[str, Any]: A dictionary containing:
            - success (bool): True if processing succeeded, False otherwise.
            - filename (str): The uploaded filename.
            - page_count (int): Total number of pages.
            - char_count (int): Total number of characters extracted.
            - text (str): The complete extracted text.
            - sections (dict): Parsed sections dictionary.
            - error (str or None): Error message if processing failed.
    """
    try:
        # Open the PDF document from the in-memory bytes stream
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        page_count = len(doc)
        
        extracted_text_list = []
        for page_num in range(page_count):
            page = doc.load_page(page_num)
            page_text = page.get_text() or ""
            extracted_text_list.append(page_text)
            
        # Join extracted text from all pages
        full_text = "\n".join(extracted_text_list)
        cleaned_text = clean_extracted_text(full_text)
        char_count = len(cleaned_text)
        sections = segment_drhp_by_topics(cleaned_text)
        
        return {
            "success": True,
            "filename": filename,
            "page_count": page_count,
            "char_count": char_count,
            "text": cleaned_text,
            "sections": sections,
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "filename": filename,
            "page_count": 0,
            "char_count": 0,
            "text": "",
            "sections": {},
            "error": f"Failed to parse PDF document: {str(e)}"
        }

if __name__ == "__main__":
    print("Running pdf_processor.py self-test...")
    
    # 1. Create a dummy PDF in memory using fitz
    test_doc = fitz.open()
    test_page = test_doc.new_page()
    test_text = "Draft Red Herring Prospectus (DRHP) details for ABC Corporation.\nSECTION III: RISK FACTORS\nHigh debt levels of 500 Cr."
    test_page.insert_text((50, 50), test_text)
    
    # Write to a bytes object
    pdf_bytes = test_doc.write()
    test_doc.close()
    
    # 2. Test the extraction function
    result = extract_pdf_data(pdf_bytes, "test_drhp.pdf")
    
    # 3. Print the result
    print("\nResult of processing:")
    for key, value in result.items():
        if key == "text":
            print(f"  {key}: {repr(value[:100])}...")
        else:
            print(f"  {key}: {value}")


