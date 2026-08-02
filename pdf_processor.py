import fitz
from typing import Dict, Any

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
        char_count = len(full_text)
        
        return {
            "success": True,
            "filename": filename,
            "page_count": page_count,
            "char_count": char_count,
            "text": full_text,
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "filename": filename,
            "page_count": 0,
            "char_count": 0,
            "text": "",
            "error": f"Failed to parse PDF document: {str(e)}"
        }

if __name__ == "__main__":
    print("Running pdf_processor.py self-test...")
    
    # 1. Create a dummy PDF in memory using fitz
    test_doc = fitz.open()
    test_page = test_doc.new_page()
    test_text = "Draft Red Herring Prospectus (DRHP) details for ABC Corporation."
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
            print(f"  {key}: {repr(value)}")
        else:
            print(f"  {key}: {value}")

