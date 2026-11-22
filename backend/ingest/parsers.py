import shutil
from dataclasses import dataclass
from pathlib import Path

_TESSERACT_AVAILABLE = shutil.which("tesseract") is not None


@dataclass
class ExtractedUnit:
    text: str
    page_number: int | None = None
    slide_number: int | None = None


class ParseError(Exception):
    pass


def extract(path: Path) -> tuple[list[ExtractedUnit], int | None]:
    """Returns (units, page_count). Raises ParseError on unsupported/corrupt files."""
    ext = path.suffix.lower()
    if ext == ".pdf":
        return _extract_pdf(path)
    if ext == ".docx":
        return _extract_docx(path)
    if ext == ".pptx":
        return _extract_pptx(path)
    if ext in (".xlsx",):
        return _extract_xlsx(path)
    if ext in (".xls",):
        return _extract_xls(path)
    if ext == ".csv":
        return _extract_csv(path)
    if ext == ".txt":
        return _extract_txt(path)
    if ext in (".doc", ".ppt"):
        raise ParseError(f"Legacy binary format {ext} is not supported in this build.")
    raise ParseError(f"Unsupported file type: {ext}")


def _extract_pdf(path: Path) -> tuple[list[ExtractedUnit], int | None]:
    try:
        import fitz  # PyMuPDF
    except ImportError as e:
        raise ParseError(f"PyMuPDF not installed: {e}") from e

    try:
        doc = fitz.open(path)
    except Exception as e:
        raise ParseError(f"Could not open PDF: {e}") from e

    units: list[ExtractedUnit] = []
    try:
        for i, page in enumerate(doc):
            text = page.get_text().strip()
            if not text and _TESSERACT_AVAILABLE:
                text = _ocr_pdf_page(page)
            if text:
                units.append(ExtractedUnit(text=text, page_number=i + 1))
        page_count = doc.page_count
    finally:
        doc.close()
    return units, page_count


def _ocr_pdf_page(page) -> str:
    try:
        import pytesseract
        from PIL import Image
        import io

        pix = page.get_pixmap(dpi=200)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        return pytesseract.image_to_string(img).strip()
    except Exception:
        return ""


def _extract_docx(path: Path) -> tuple[list[ExtractedUnit], int | None]:
    try:
        import docx
    except ImportError as e:
        raise ParseError(f"python-docx not installed: {e}") from e

    try:
        document = docx.Document(str(path))
    except Exception as e:
        raise ParseError(f"Could not open DOCX: {e}") from e

    paragraphs = [p.text.strip() for p in document.paragraphs if p.text.strip()]
    for table in document.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                paragraphs.append(" | ".join(cells))

    text = "\n".join(paragraphs)
    if not text.strip():
        return [], None
    return [ExtractedUnit(text=text, page_number=None)], None


def _extract_pptx(path: Path) -> tuple[list[ExtractedUnit], int | None]:
    try:
        from pptx import Presentation
    except ImportError as e:
        raise ParseError(f"python-pptx not installed: {e}") from e

    try:
        prs = Presentation(str(path))
    except Exception as e:
        raise ParseError(f"Could not open PPTX: {e}") from e

    units: list[ExtractedUnit] = []
    for i, slide in enumerate(prs.slides):
        parts = []
        for shape in slide.shapes:
            if shape.has_text_frame and shape.text_frame.text.strip():
                parts.append(shape.text_frame.text.strip())
            if shape.has_table:
                for row in shape.table.rows:
                    cells = [c.text.strip() for c in row.cells if c.text.strip()]
                    if cells:
                        parts.append(" | ".join(cells))
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame.text.strip():
            parts.append("Notes: " + slide.notes_slide.notes_text_frame.text.strip())
        if parts:
            units.append(ExtractedUnit(text="\n".join(parts), slide_number=i + 1))
    return units, len(prs.slides)


def _extract_xlsx(path: Path) -> tuple[list[ExtractedUnit], int | None]:
    try:
        import pandas as pd
    except ImportError as e:
        raise ParseError(f"pandas not installed: {e}") from e

    try:
        sheets = pd.read_excel(path, sheet_name=None, engine="openpyxl")
    except Exception as e:
        raise ParseError(f"Could not open XLSX: {e}") from e

    return _units_from_sheets(sheets), len(sheets)


def _extract_xls(path: Path) -> tuple[list[ExtractedUnit], int | None]:
    try:
        import pandas as pd
    except ImportError as e:
        raise ParseError(f"pandas not installed: {e}") from e

    try:
        sheets = pd.read_excel(path, sheet_name=None, engine="xlrd")
    except Exception as e:
        raise ParseError(f"Could not open XLS: {e}") from e

    return _units_from_sheets(sheets), len(sheets)


def _units_from_sheets(sheets: dict) -> list[ExtractedUnit]:
    units = []
    for name, df in sheets.items():
        if df.empty:
            continue
        preview = df.head(200)
        text = f"Sheet: {name}\nColumns: {', '.join(str(c) for c in df.columns)}\n\n{preview.to_string(index=False)}"
        if len(df) > 200:
            text += f"\n... ({len(df) - 200} more rows truncated)"
        units.append(ExtractedUnit(text=text))
    return units


def _extract_csv(path: Path) -> tuple[list[ExtractedUnit], int | None]:
    try:
        import pandas as pd
    except ImportError as e:
        raise ParseError(f"pandas not installed: {e}") from e

    try:
        df = pd.read_csv(path, on_bad_lines="skip")
    except Exception as e:
        raise ParseError(f"Could not open CSV: {e}") from e

    if df.empty:
        return [], None
    preview = df.head(200)
    text = f"Columns: {', '.join(str(c) for c in df.columns)}\n\n{preview.to_string(index=False)}"
    if len(df) > 200:
        text += f"\n... ({len(df) - 200} more rows truncated)"
    return [ExtractedUnit(text=text)], None


def _extract_txt(path: Path) -> tuple[list[ExtractedUnit], int | None]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore").strip()
    except Exception as e:
        raise ParseError(f"Could not read TXT: {e}") from e
    if not text:
        return [], None
    return [ExtractedUnit(text=text)], None
