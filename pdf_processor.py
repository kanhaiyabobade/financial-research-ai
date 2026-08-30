import pymupdf as fitz
import re
from typing import Dict, Any, List

def clean_extracted_text(text: str) -> str:
    """
    Cleans raw extracted PDF text by removing null bytes, normalizing line breaks,
    and removing excessive whitespace noise while keeping structural headers.
    """
    if not text:
        return ""
    # Remove null bytes
    cleaned = text.replace("\x00", "")
    # Replace horizontal carriage returns / tabs with space
    cleaned = cleaned.replace("\r", "\n").replace("\t", " ")
    # Replace non-breaking spaces
    cleaned = cleaned.replace("\xa0", " ")
    # Strip trailing whitespace on individual lines
    lines = [line.strip() for line in cleaned.splitlines()]
    cleaned = "\n".join(lines)
    # Collapse 3 or more consecutive newlines to 2
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()

def segment_drhp_by_topics(text: str) -> Dict[str, str]:
    """
    Segments extracted DRHP text into key financial and prospectus section topics.
    Uses flexible case-insensitive regex pattern matching.
    """
    cleaned = clean_extracted_text(text)
    if not cleaned:
        return {}

    topic_patterns = {
        "Company Overview & Industry": [
            r"company\s+overview", r"about\s+the\s+company", r"industry\s+overview", r"our\s+industry"
        ],
        "Business Model & Products": [
            r"our\s+business", r"business\0*model", r"products\s+and\s+services", r"main\s+objects"
        ],
        "Financial Statements & Performance": [
            r"financial\s+information", r"financial\s+statements", r"restated\s+financial", r"summary\s+financial"
        ],
        "Revenue, Assets & Liabilities": [
            r"revenue\s+from\s+operations", r"balance\s+sheet", r"cash\s+flow", r"indebtedness", r"borrowings"
        ],
        "Promoters & Shareholding": [
            r"our\s+promoters", r"promoter\s+group", r"capital\s+structure", r"shareholding\s+pattern"
        ],
        "IPO Structure & Proceeds": [
            r"objects\s+of\s+the\s+offer", r"objects\s+of\s+the\s+issue", r"use\s+of\s+proceeds", r"offer\s+structure"
        ],
        "Risk Factors": [
            r"risk\s+factors", r"internal\s+risk\s+factors", r"external\s+risk\s+factors"
        ],
        "Legal, Regulatory & Related Party": [
            r"legal\s+and\s+other\s+information", r"pending\s+litigation", r"related\s+party\s+transactions", r"outstanding\s+litigation"
        ],
        "Competitors & Growth": [
            r"competition", r"competitive\s+strengths", r"growth\s+strategies", r"business\s+strategies"
        ]
    }

    sections: Dict[str, str] = {}
    cleaned_lower = cleaned.lower()
    snippet_len = 15000

    for topic, patterns in topic_patterns.items():
        matched_text = ""
        for pattern in patterns:
            match = re.search(pattern, cleaned_lower)
            if match:
                pos = match.start()
                matched_text = cleaned[pos : pos + snippet_len]
                break
        if matched_text:
            sections[topic] = matched_text

    return sections

def chunk_text(text: str, max_chunk_chars: int = 40000, overlap_chars: int = 2000) -> List[str]:
    """
    Splits long text into overlapping chunks to prevent loss of context across section boundaries.
    """
    if not text:
        return []
    if len(text) <= max_chunk_chars:
        return [text]

    chunks = []
    start = 0
    total_len = len(text)

    while start < total_len:
        end = min(start + max_chunk_chars, total_len)
        # Try to break at a paragraph boundary (\n\n) if possible
        if end < total_len:
            last_para = text.rfind("\n\n", start, end)
            if last_para != -1 and last_para > start + (max_chunk_chars // 2):
                end = last_para

        chunks.append(text[start:end])
        if end >= total_len:
            break
        start = max(start + 1, end - overlap_chars)

    return chunks

def extract_pdf_data(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    """
    Extracts page-by-page text from PDF bytes in memory, preserving page markers and section segmentation.
    
    Args:
        file_bytes (bytes): Raw bytes of the uploaded PDF file.
        filename (str): Original filename.

    Returns:
        Dict[str, Any]: Extraction result dictionary.
    """
    if not file_bytes:
        return {
            "success": False,
            "filename": filename,
            "page_count": 0,
            "char_count": 0,
            "text": "",
            "sections": {},
            "error": "Uploaded file is empty (0 bytes)."
        }

    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        page_count = len(doc)

        if page_count == 0:
            return {
                "success": False,
                "filename": filename,
                "page_count": 0,
                "char_count": 0,
                "text": "",
                "sections": {},
                "error": "The uploaded PDF document contains 0 pages."
            }

        extracted_pages = []
        total_uncleaned_chars = 0

        for page_num in range(page_count):
            page = doc.load_page(page_num)
            page_text = page.get_text() or ""
            total_uncleaned_chars += len(page_text)
            if page_text.strip():
                extracted_pages.append(f"--- Page {page_num + 1} ---\n{page_text.strip()}")

        doc.close()

        if not extracted_pages or total_uncleaned_chars < 50:
            return {
                "success": False,
                "filename": filename,
                "page_count": page_count,
                "char_count": 0,
                "text": "",
                "sections": {},
                "error": "The PDF document appears to be unreadable or scanned images without selectable text."
            }

        full_text = "\n\n".join(extracted_pages)
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
            "error": f"Failed to extract PDF data: {str(e)}"
        }

if __name__ == "__main__":
    print("Self-testing pdf_processor.py...")
    test_doc = fitz.open()
    page = test_doc.new_page()
    page.insert_text((50, 50), "DRAFT RED HERRING PROSPECTUS\nABC TECH LIMITED\nOBJECTS OF THE OFFER\nFresh Issue of Rs 500 Cr.")
    pdf_bytes = test_doc.write()
    test_doc.close()

    res = extract_pdf_data(pdf_bytes, "test.pdf")
    print(f"Extraction success: {res['success']}, pages: {res['page_count']}, chars: {res['char_count']}")
    assert res["success"] is True
    assert "--- Page 1 ---" in res["text"]
    print("pdf_processor.py self-test passed!")
