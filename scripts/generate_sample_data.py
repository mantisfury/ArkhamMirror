import os
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import docx
from PIL import Image, ImageDraw, ImageFont
from email.message import EmailMessage

DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "tutorial_case")


def ensure_dir():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)


def create_pdf(filename, content):
    path = os.path.join(DATA_DIR, filename)
    c = canvas.Canvas(path, pagesize=letter)
    width, height = letter
    c.setFont("Helvetica", 12)
    y = height - 50
    for line in content.split("\n"):
        c.drawString(50, y, line)
        y -= 15
        if y < 50:
            c.showPage()
            y = height - 50
    c.save()
    print(f"Created PDF: {path}")


def create_docx(filename, content):
    path = os.path.join(DATA_DIR, filename)
    doc = docx.Document()
    for line in content.split("\n"):
        doc.add_paragraph(line)
    doc.save(path)
    print(f"Created DOCX: {path}")


def create_email(filename, sender, recipient, subject, body):
    path = os.path.join(DATA_DIR, filename)
    msg = EmailMessage()
    msg.set_content(body)
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient

    with open(path, "wb") as f:
        f.write(msg.as_bytes())
    print(f"Created EML: {path}")


def create_image(filename, text):
    path = os.path.join(DATA_DIR, filename)
    img = Image.new("RGB", (800, 600), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    # Use default font if specific one not found, or try to load a basic one
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except IOError:
        font = ImageFont.load_default()

    d.text((50, 50), text, fill=(0, 0, 0), font=font)
    img.save(path)
    print(f"Created Image: {path}")


def generate_samples():
    ensure_dir()
    print(f"Generating Tutorial Case in: {DATA_DIR}")

    # 1. PDF: The Official Cover Story
    create_pdf(
        "Shipping_Manifest_Oct2023.pdf",
        """
        OFFICIAL SHIPPING MANIFEST
        Vessel: The Iron Mermaid
        Date: Oct 15, 2023
        Destination: Port of Antwerp
        
        Cargo List:
        1. Textiles (20 crates)
        2. Electronics (50 pallets)
        3. Agricultural Machinery (5 units)
        4. "Special Handling" Containers (ref: C-999) - DO NOT INSPECT
        
        Captain: J. Silver
        Authorized by: Global Logistics Corp
        """,
    )

    # 2. DOCX: The Internal Leak
    create_docx(
        "Draft_Complaint_Letter.docx",
        """
        DRAFT - INTERNAL USE ONLY
        
        To: Management
        From: Warehouse Supervisor
        
        I am writing to express my concern regarding the C-999 containers.
        The crew is complaining about a strange smell coming from them.
        Captain Silver refused to let us check the seals.
        
        We are not paid enough to look the other way if this is hazardous waste or worse.
        Please advise.
        """,
    )

    # 3. EML: The Incriminating Evidence
    create_email(
        "Re_Payment_Issues.eml",
        sender="fixer@globallogistics.corp",
        recipient="silver@sea-mail.com",
        subject="Re: Payment for the 'Special' Job",
        body="""
        Silver,
        
        The funds have been wired to your offshore account in Panama.
        Remember, if anyone asks about C-999, it's just "industrial parts".
        
        Do not fail us. The client is very impatient.
        
        - The Fixer
        """,
    )

    # 4. Image: The Physical Proof
    create_image(
        "Evidence_Photo_001.png",
        """
        [HANDWRITTEN NOTE FOUND IN CAPTAIN'S QUARTERS]
        
        Code for C-999 Lock: 77-21-90
        
        Contact 'The Ghost' upon arrival.
        Phone: 555-0199
        """,
    )

    print("\nTutorial dataset generated successfully!")
    print(
        "Drag these files into the ArkhamMirror 'Upload Files' area to test ingestion."
    )


if __name__ == "__main__":
    generate_samples()
