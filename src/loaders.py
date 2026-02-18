from pathlib import Path
from typing import Dict, List, Tuple
from pypdf import PdfReader
import docx2txt

def load_pdf(path: Path) -> Tuple[str, Dict]:
    reader = PdfReader(str(path))
    pages = []
    for i, p in enumerate(reader.pages):
        txt = p.extract_text() or ""
        pages.append(txt)
    text = "\n".join(pages)
    meta = {
        "source_file": path.name,
        "file_type": "pdf",
        "page_count": len(reader.pages),
    }
    return text, meta

def load_docx(path: Path) -> Tuple[str, Dict]:
    text = docx2txt.process(str(path)) or ""
    meta = {
        "source_file": path.name,
        "file_type": "docx",
    }
    return text, meta

def load_docs(folder: Path) -> List[Tuple[str, Dict]]:
    results = []
    for p in sorted(folder.glob("*")):
        if p.suffix.lower() == ".pdf":
            text, meta = load_pdf(p)
            results.append((text, meta))
        elif p.suffix.lower() in [".docx", ".doc"]:
            # docx2txt works best for .docx; .doc might fail depending on system.
            text, meta = load_docx(p)
            results.append((text, meta))
    return results
