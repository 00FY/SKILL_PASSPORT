import io
import re
from typing import List, Dict, Any, Tuple
from pypdf import PdfReader

class PDFParser:
    """
    Extracts raw text, embedded hyperlinks, and structural metadata from PDF or text documents.
    """

    def parse_pdf_bytes(self, content_bytes: bytes) -> Tuple[str, List[str]]:
        reader = PdfReader(io.BytesIO(content_bytes))
        full_text = []
        links: List[str] = []

        for page in reader.pages:
            text = page.extract_text()
            if text:
                full_text.append(text)

            # Extract any annotations or link objects embedded in PDF
            if "/Annots" in page:
                for annot in page["/Annots"]:
                    obj = annot.get_object()
                    if "/A" in obj and "/URI" in obj["/A"]:
                        uri = obj["/A"]["/URI"]
                        if uri and uri not in links:
                            links.append(uri)

        extracted_text = "\n".join(full_text)
        # Also extract raw URLs with regex from the text
        url_matches = re.findall(r'https?://[^\s<>"\')]+', extracted_text)
        for url in url_matches:
            clean_url = url.rstrip(".,;:)")
            if clean_url not in links:
                links.append(clean_url)

        return extracted_text, links

    def parse_text_or_markdown(self, raw_text: str) -> Tuple[str, List[str]]:
        links: List[str] = []
        url_matches = re.findall(r'https?://[^\s<>"\')]+', raw_text)
        for url in url_matches:
            clean_url = url.rstrip(".,;:)")
            if clean_url not in links:
                links.append(clean_url)
        return raw_text, links
