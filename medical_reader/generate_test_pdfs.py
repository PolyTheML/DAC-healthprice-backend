"""
Generate sample medical record PDFs for testing the intake node.

Creates three realistic medical records:
1. healthy.pdf - 45yo, good vitals, low risk
2. high-risk.pdf - 62yo, multiple conditions, high risk
3. unreadable.pdf - Poor quality scanned document
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle, SimpleDocTemplate, Spacer, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from pathlib import Path
from datetime import datetime, timedelta
import random


def create_healthy_pdf(filepath):
    """
    Create a healthy patient medical record.
    45-year-old male with good health metrics.
    """
    doc = SimpleDocTemplate(filepath, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []

    # Header
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#1f4788'),
        spaceAfter=12
    )
    elements.append(Paragraph("MEDICAL EVALUATION REPORT", title_style))
    elements.append(Spacer(1, 0.2*inch))

    # Patient info
    elements.append(Paragraph("<b>Patient Information</b>", styles['Heading2']))
    patient_data = [
        ['Name:', 'John Smith'],
        ['Date of Birth:', 'March 15, 1981'],
        ['Age:', '45 years'],
        ['Gender:', 'Male'],
        ['Exam Date:', datetime.now().strftime('%B %d, %Y')],
    ]
    table = Table(patient_data, colWidths=[2*inch, 3*inch])
    table.setStyle(TableStyle([('BACKGROUND', (0, 0), (0, -1), colors.lightgrey)]))
    elements.append(table)
    elements.append(Spacer(1, 0.2*inch))

    # Vital Signs
    elements.append(Paragraph("<b>Vital Signs</b>", styles['Heading2']))
    vitals_data = [
        ['Measurement', 'Value', 'Status'],
        ['Height', '5\'10" (178 cm)', 'Normal'],
        ['Weight', '180 lbs (82 kg)', 'Normal'],
        ['BMI', '25.8', 'Normal'],
        ['Blood Pressure', '118/76 mmHg', 'Normal'],
        ['Heart Rate', '68 bpm', 'Normal'],
        ['Respiratory Rate', '16 breaths/min', 'Normal'],
    ]
    table = Table(vitals_data, colWidths=[2*inch, 2*inch, 1.5*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 0.2*inch))

    # Medical History
    elements.append(Paragraph("<b>Medical History</b>", styles['Heading2']))
    history_data = [
        ['Condition', 'Status'],
        ['Diabetes', 'No'],
        ['Hypertension', 'No'],
        ['High Cholesterol', 'No'],
        ['Coronary Heart Disease', 'No'],
        ['Family History of CHD', 'No'],
        ['Current Smoker', 'No'],
        ['Alcohol Use', 'Moderate'],
    ]
    table = Table(history_data, colWidths=[3*inch, 2*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 0.2*inch))

    # Medications
    elements.append(Paragraph("<b>Current Medications</b>", styles['Heading2']))
    elements.append(Paragraph("None", styles['Normal']))
    elements.append(Spacer(1, 0.2*inch))

    # Physician notes
    elements.append(Paragraph("<b>Physician Notes</b>", styles['Heading2']))
    elements.append(Paragraph(
        "Patient presents in excellent health. All vitals within normal limits. "
        "Maintains healthy lifestyle with regular exercise and good diet. "
        "Recommends continued preventive care and annual check-ups.",
        styles['Normal']
    ))

    doc.build(elements)


def create_high_risk_pdf(filepath):
    """
    Create a high-risk patient medical record.
    62-year-old male with multiple conditions.
    """
    doc = SimpleDocTemplate(filepath, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []

    # Header
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#8b0000'),
        spaceAfter=12
    )
    elements.append(Paragraph("MEDICAL EVALUATION REPORT", title_style))
    elements.append(Spacer(1, 0.2*inch))

    # Patient info
    elements.append(Paragraph("<b>Patient Information</b>", styles['Heading2']))
    patient_data = [
        ['Name:', 'Robert Johnson'],
        ['Date of Birth:', 'July 22, 1964'],
        ['Age:', '62 years'],
        ['Gender:', 'Male'],
        ['Exam Date:', datetime.now().strftime('%B %d, %Y')],
    ]
    table = Table(patient_data, colWidths=[2*inch, 3*inch])
    table.setStyle(TableStyle([('BACKGROUND', (0, 0), (0, -1), colors.lightcoral)]))
    elements.append(table)
    elements.append(Spacer(1, 0.2*inch))

    # Vital Signs
    elements.append(Paragraph("<b>Vital Signs</b>", styles['Heading2']))
    vitals_data = [
        ['Measurement', 'Value', 'Status'],
        ['Height', '5\'9" (175 cm)', 'Normal'],
        ['Weight', '220 lbs (100 kg)', 'Overweight'],
        ['BMI', '32.5', 'Obese'],
        ['Blood Pressure', '158/94 mmHg', 'Elevated'],
        ['Heart Rate', '78 bpm', 'Normal'],
        ['Respiratory Rate', '18 breaths/min', 'Slightly elevated'],
    ]
    table = Table(vitals_data, colWidths=[2*inch, 2*inch, 1.5*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8b0000')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.lightcoral),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 0.2*inch))

    # Medical History
    elements.append(Paragraph("<b>Medical History</b>", styles['Heading2']))
    history_data = [
        ['Condition', 'Status'],
        ['Diabetes', 'Yes (Type 2, since 2015)'],
        ['Hypertension', 'Yes (on medication)'],
        ['High Cholesterol', 'Yes (on statin)'],
        ['Coronary Heart Disease', 'History of angina'],
        ['Family History of CHD', 'Yes (father, age 58)'],
        ['Current Smoker', 'Yes (15 cigarettes/day)'],
        ['Alcohol Use', 'Heavy (daily)'],
    ]
    table = Table(history_data, colWidths=[3*inch, 2*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8b0000')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 0.2*inch))

    # Medications
    elements.append(Paragraph("<b>Current Medications</b>", styles['Heading2']))
    meds = [
        'Atorvastatin 80mg daily (cholesterol)',
        'Lisinopril 10mg daily (blood pressure)',
        'Metformin 500mg twice daily (diabetes)',
        'Aspirin 81mg daily (cardiovascular)',
        'Atenolol 50mg daily (heart)',
    ]
    for med in meds:
        elements.append(Paragraph(f"• {med}", styles['Normal']))
    elements.append(Spacer(1, 0.2*inch))

    # Physician notes
    elements.append(Paragraph("<b>Physician Notes</b>", styles['Heading2']))
    elements.append(Paragraph(
        "Patient presents with multiple cardiovascular risk factors. "
        "Obesity, smoking, diabetes, and hypertension all contribute to elevated risk. "
        "Previous diagnosis of angina is concerning. Blood pressure control is suboptimal. "
        "Strongly recommends smoking cessation, dietary changes, and increased medication compliance. "
        "Patient requires close monitoring and lifestyle modification.",
        styles['Normal']
    ))

    doc.build(elements)


def create_unreadable_pdf(filepath):
    """
    Create a low-quality/unreadable PDF (simulated poor OCR).
    """
    from reportlab.pdfgen import canvas as pdf_canvas
    import io

    # Create a simple low-quality image with poor text
    c = pdf_canvas.Canvas(str(filepath), pagesize=letter)
    c.setFont("Courier", 8)

    # Add garbled text to simulate poor OCR/scan quality
    y = 10.5 * inch
    lines = [
        "~~MEEDICAL EVALUTION REP0RT~~",
        "Pat1ent: ???????",
        "D0B: 19XX-XX-XX",
        "Ag3: [illegible]",
        "BP: 1##/8# [smudged]",
        "BM1: [corrupted] 2?.",
        "Condit1ons: [unreadable text block]",
        "~~[fax artifacts throughout]~~",
        "Phy51c1an: Dr. [illegible]",
        "Date: [corrupted timestamp]",
    ]

    for line in lines:
        c.drawString(0.5*inch, y, line)
        y -= 0.3*inch

    c.save()


def main():
    test_data_dir = Path("C:/DAC-UW-Agent/medical_reader/test_data")
    test_data_dir.mkdir(parents=True, exist_ok=True)

    print("Generating test PDFs...")

    healthy_path = test_data_dir / "healthy.pdf"
    create_healthy_pdf(str(healthy_path))
    print(f"[OK] Created {healthy_path}")

    high_risk_path = test_data_dir / "high_risk.pdf"
    create_high_risk_pdf(str(high_risk_path))
    print(f"[OK] Created {high_risk_path}")

    unreadable_path = test_data_dir / "unreadable.pdf"
    create_unreadable_pdf(str(unreadable_path))
    print(f"[OK] Created {unreadable_path}")

    print(f"\nTest PDFs created in {test_data_dir}")


if __name__ == "__main__":
    main()
