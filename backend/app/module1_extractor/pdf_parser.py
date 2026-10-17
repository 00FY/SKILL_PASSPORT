import io
import re
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import List, Tuple
from pypdf import PdfReader

MAX_RESUME_BYTES = 5 * 1024 * 1024
MAX_DOCX_XML_BYTES = 20 * 1024 * 1024
SUPPORTED_EXTENSIONS = (".pdf", ".docx", ".txt", ".md")

URL_PATTERN = re.compile(r'https?://[^\s<>"\')\]]+')
# Bare "github.com/user/repo" mentions without a scheme are common on resumes
BARE_REPO_PATTERN = re.compile(r'(?<![\w/.])((?:www\.)?(?:github\.com|gitlab\.com|bitbucket\.org)/[\w.\-]+(?:/[\w.\-]+)?)')

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
R_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


class ResumeParseError(ValueError):
    pass


@dataclass
class ParsedResume:
    text: str
    links: List[str]
    warnings: List[str] = field(default_factory=list)


def extract_links(text: str) -> List[str]:
    links: List[str] = []
    for url in URL_PATTERN.findall(text):
        clean_url = url.rstrip(".,;:)")
        if clean_url not in links:
            links.append(clean_url)
    for bare in BARE_REPO_PATTERN.findall(text):
        url = "https://" + bare.rstrip(".,;:)")
        if url not in links and not any(l.startswith(url) for l in links):
            links.append(url)
    return links


class PDFParser:
    """
    Extracts raw text, embedded hyperlinks, and structural metadata from PDF, DOCX or text documents.
    Hidden runs (micro fonts, white or vanished text) are wrapped in style markers so the
    injection guard can flag and neutralise them.
    """

    def parse_file(self, filename: str, content: bytes) -> ParsedResume:
        if len(content) > MAX_RESUME_BYTES:
            raise ResumeParseError("Resume file is larger than 5 MB.")
        name = (filename or "").lower()
        if name.endswith(".pdf"):
            text, links = self.parse_pdf_bytes(content)
        elif name.endswith(".docx"):
            text, links = self.parse_docx_bytes(content)
        elif name.endswith((".txt", ".md")) or not name:
            text, links = self.parse_text_or_markdown(content.decode("utf-8", errors="ignore"))
        elif name.endswith(".doc"):
            raise ResumeParseError("Legacy .doc files aren't supported. Save the resume as .docx or PDF and try again.")
        else:
            raise ResumeParseError(f"Unsupported file type. Upload one of: {', '.join(SUPPORTED_EXTENSIONS)}.")

        warnings: List[str] = []
        if len(text.strip()) < 40:
            warnings.append(
                "Very little text could be extracted. If this is a scanned or image-only resume, "
                "OCR isn't supported - paste the resume text instead."
            )
        return ParsedResume(text=text, links=links, warnings=warnings)

    def parse_pdf_bytes(self, content_bytes: bytes) -> Tuple[str, List[str]]:
        try:
            reader = PdfReader(io.BytesIO(content_bytes))
            pages = list(reader.pages)
        except Exception as exc:
            raise ResumeParseError(f"Could not read PDF: {exc}") from exc

        full_text = []
        links: List[str] = []

        for page in pages:
            text = page.extract_text() or ""
            if text:
                full_text.append(text)

            # Check for micro-font steganography (< 2pt font size)
            micro_text = []

            def visitor_body(t, cm, tm, font_dict, font_size):
                if font_size is not None and 0 < font_size < 2.0 and t.strip():
                    micro_text.append(t.strip())

            try:
                page.extract_text(visitor_text=visitor_body)
                if micro_text:
                    full_text.append(f"<span style='font-size: 1pt'>[MICRO_FONT: {' '.join(micro_text)}]</span>")
            except Exception:
                pass

            # Extract any annotations or link objects embedded in PDF
            try:
                for annot in page.get("/Annots") or []:
                    obj = annot.get_object()
                    action = obj.get("/A")
                    if action and "/URI" in action:
                        uri = str(action["/URI"])
                        if uri and uri not in links:
                            links.append(uri)
            except Exception:
                pass

        extracted_text = "\n".join(full_text)
        for url in extract_links(extracted_text):
            if url not in links:
                links.append(url)

        return extracted_text, links

    def parse_docx_bytes(self, content_bytes: bytes) -> Tuple[str, List[str]]:
        try:
            archive = zipfile.ZipFile(io.BytesIO(content_bytes))
        except zipfile.BadZipFile as exc:
            raise ResumeParseError("Could not read DOCX: file is not a valid Word document.") from exc

        names = archive.namelist()
        if "word/document.xml" not in names:
            raise ResumeParseError("Could not read DOCX: word/document.xml is missing.")

        parts = ["word/document.xml"] + sorted(n for n in names if re.match(r"word/(header|footer)\d*\.xml$", n))
        paragraphs: List[str] = []
        for part in parts:
            if archive.getinfo(part).file_size > MAX_DOCX_XML_BYTES:
                raise ResumeParseError("DOCX content is too large to process.")
            root = ET.fromstring(archive.read(part))
            for p in root.iter(f"{W_NS}p"):
                paragraphs.append(self._docx_paragraph_text(p))

        links: List[str] = []
        rels_name = "word/_rels/document.xml.rels"
        if rels_name in names:
            rels = ET.fromstring(archive.read(rels_name))
            for rel in rels:
                if rel.get("Type", "").endswith("/hyperlink"):
                    target = rel.get("Target", "")
                    if target.startswith("http") and target not in links:
                        links.append(target)

        text = "\n".join(p for p in paragraphs if p.strip())
        for url in extract_links(text):
            if url not in links:
                links.append(url)
        return text, links

    @staticmethod
    def _docx_paragraph_text(paragraph: ET.Element) -> str:
        out: List[str] = []
        for run in paragraph.iter(f"{W_NS}r"):
            run_text = "".join(t.text or "" for t in run.iter(f"{W_NS}t"))
            if not run_text:
                continue
            styles = []
            rpr = run.find(f"{W_NS}rPr")
            if rpr is not None:
                vanish = rpr.find(f"{W_NS}vanish")
                if vanish is not None and vanish.get(f"{W_NS}val", "true") not in ("0", "false"):
                    styles.append("display: none")
                color = rpr.find(f"{W_NS}color")
                if color is not None and color.get(f"{W_NS}val", "").upper() in ("FFFFFF", "FFF"):
                    styles.append("color: #ffffff")
                size = rpr.find(f"{W_NS}sz")
                try:
                    # w:sz is in half-points
                    if size is not None and int(size.get(f"{W_NS}val", "24")) < 4:
                        styles.append("font-size: 1pt")
                except ValueError:
                    pass
            if styles and run_text.strip():
                out.append(f"<span style='{'; '.join(styles)}'>{run_text}</span>")
            else:
                out.append(run_text)
        return "".join(out)

    def parse_text_or_markdown(self, raw_text: str) -> Tuple[str, List[str]]:
        return raw_text, extract_links(raw_text)
