import re


def extract_text_from_file(file_path: str, file_type: str) -> str:
    """Extract plain text from PDF, DOCX, TXT, or CSV."""
    if file_type == 'txt':
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()

    if file_type == 'csv':
        import csv
        lines = []
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.reader(f)
            for row in reader:
                lines.append(' | '.join(row))
        return '\n'.join(lines)

    if file_type == 'pdf':
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                return '\n'.join(page.extract_text() or '' for page in pdf.pages)
        except ImportError:
            try:
                import fitz  # PyMuPDF
                doc = fitz.open(file_path)
                return '\n'.join(page.get_text() for page in doc)
            except ImportError:
                return '[PDF extraction requires pdfplumber or PyMuPDF]'

    if file_type == 'docx':
        try:
            import docx
            doc = docx.Document(file_path)
            return '\n'.join(p.text for p in doc.paragraphs if p.text.strip())
        except ImportError:
            return '[DOCX extraction requires python-docx]'

    return ''


def clean_text(text: str) -> str:
    """Remove excessive whitespace and common junk."""
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)
    text = re.sub(r'Page \d+ of \d+', '', text)
    text = text.strip()
    return text
