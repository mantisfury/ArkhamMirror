import os
import logging
import docx
import extract_msg
from email import policy
from email.parser import BytesParser
from PIL import Image

logger = logging.getLogger(__name__)


def convert_to_pdf(file_path):
    """
    Converts various file formats (.docx, .msg, .eml, images) to PDF.
    Returns the path to the generated PDF.
    """
    ext = os.path.splitext(file_path)[1].lower()
    output_pdf_path = file_path + ".converted.pdf"

    try:
        if ext == ".docx":
            _convert_docx_to_pdf(file_path, output_pdf_path)
        elif ext == ".msg":
            _convert_msg_to_pdf(file_path, output_pdf_path)
        elif ext == ".eml":
            _convert_eml_to_pdf(file_path, output_pdf_path)
        elif ext == ".txt":
            _convert_txt_to_pdf(file_path, output_pdf_path)
        elif ext in [".jpg", ".jpeg", ".png", ".bmp", ".tiff"]:
            _convert_image_to_pdf(file_path, output_pdf_path)
        else:
            raise ValueError(f"Unsupported file type for conversion: {ext}")

        return output_pdf_path
    except Exception as e:
        logger.error(f"Conversion failed for {file_path}: {e}")
        if os.path.exists(output_pdf_path):
            os.remove(output_pdf_path)
        raise e


def _convert_docx_to_pdf(docx_path, pdf_path):
    # Quick and dirty: Extract text and create a simple PDF using ReportLab
    # Ideally, we'd use LibreOffice or win32com for perfect layout preservation,
    # but that introduces heavy dependencies. For v0.1, text extraction is key.
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter

    doc = docx.Document(docx_path)
    c = canvas.Canvas(pdf_path, pagesize=letter)
    width, height = letter
    y = height - 40

    for para in doc.paragraphs:
        text = para.text
        # Simple wrapping
        lines = _simple_wrap(text, 80)
        for line in lines:
            if y < 40:
                c.showPage()
                y = height - 40
            c.drawString(40, y, line)
            y -= 12

    c.save()


def _convert_msg_to_pdf(msg_path, pdf_path):
    msg = extract_msg.Message(msg_path)
    _create_text_pdf(
        msg.body,
        pdf_path,
        f"Subject: {msg.subject}\nFrom: {msg.sender}\nTo: {msg.to}\nDate: {msg.date}\n\n",
    )
    msg.close()


def _convert_eml_to_pdf(eml_path, pdf_path):
    with open(eml_path, "rb") as f:
        msg = BytesParser(policy=policy.default).parse(f)

    body = msg.get_body(preferencelist=("plain")).get_content()
    header = f"Subject: {msg['subject']}\nFrom: {msg['from']}\nTo: {msg['to']}\nDate: {msg['date']}\n\n"
    _create_text_pdf(body, pdf_path, header)


def _convert_image_to_pdf(img_path, pdf_path):
    image = Image.open(img_path)
    if image.mode != "RGB":
        image = image.convert("RGB")
    image.save(pdf_path, "PDF", resolution=100.0)


def _convert_txt_to_pdf(txt_path, pdf_path):
    with open(txt_path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    _create_text_pdf(text, pdf_path)


def _create_text_pdf(text, pdf_path, header=""):
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter

    c = canvas.Canvas(pdf_path, pagesize=letter)
    width, height = letter
    y = height - 40

    full_text = header + (text or "")

    for line in full_text.split("\n"):
        wrapped_lines = _simple_wrap(line, 90)
        for w_line in wrapped_lines:
            if y < 40:
                c.showPage()
                y = height - 40
            c.drawString(40, y, w_line)
            y -= 12
    c.save()


def _simple_wrap(text, max_chars):
    return [text[i : i + max_chars] for i in range(0, len(text), max_chars)]
