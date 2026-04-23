"""Generate synthetic medical record PDFs for testing"""

import os
from pathlib import Path
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT


def create_test_data_dir():
    """Create test_data directory if it doesn't exist"""
    test_dir = Path("test_data")
    test_dir.mkdir(exist_ok=True)
    return test_dir


def create_medical_record_pdf(filename: str, applicant_name: str, case_type: str):
    """Create a synthetic medical record PDF"""
    test_dir = create_test_data_dir()
    filepath = test_dir / filename

    doc = SimpleDocTemplate(str(filepath), pagesize=letter)
    story = []
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#1f4788'),
        spaceAfter=12,
        alignment=TA_CENTER,
    )

    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=colors.HexColor('#1f4788'),
        spaceAfter=8,
        spaceBefore=6,
    )

    # Header
    story.append(Paragraph("MEDICAL RECORD", title_style))
    story.append(Paragraph("Royal Cambodian Hospital", styles['Normal']))
    story.append(Spacer(1, 12))

    # Applicant info
    info_data = [
        ["Name:", applicant_name],
        ["Date of Examination:", datetime.now().strftime("%Y-%m-%d")],
        ["Examiner:", "Dr. Soy Vichea, MD"],
        ["Policy Number:", "POL-2026-0001"],
    ]
    info_table = Table(info_data, colWidths=[2*inch, 4*inch])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e8f0f8')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 12))

    # Add case-specific content
    if case_type == "healthy":
        _add_healthy_case(story, styles, heading_style)
    elif case_type == "hypertensive":
        _add_hypertensive_case(story, styles, heading_style)
    elif case_type == "diabetic":
        _add_diabetic_case(story, styles, heading_style)
    elif case_type == "high_risk":
        _add_high_risk_case(story, styles, heading_style)

    # Build PDF
    doc.build(story)
    print(f"[OK] Created {filepath}")
    return filepath


def _add_healthy_case(story, styles, heading_style):
    """Healthy 35-year-old applicant"""
    story.append(Paragraph("VITAL SIGNS", heading_style))

    vitals_data = [
        ["Height:", "1.75 m", "Weight:", "75 kg"],
        ["BMI:", "24.5", "Blood Pressure:", "120/80 mmHg"],
        ["Heart Rate:", "72 bpm", "Temperature:", "37.0°C"],
    ]
    vitals_table = Table(vitals_data, colWidths=[1.5*inch, 1.5*inch, 1.5*inch, 1.5*inch])
    vitals_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f0f8f0')),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))
    story.append(vitals_table)
    story.append(Spacer(1, 10))

    story.append(Paragraph("LABORATORY RESULTS (2026-03-15)", heading_style))
    lab_data = [
        ["Test", "Result", "Unit", "Reference Range"],
        ["Fasting Glucose", "95", "mg/dL", "70-100"],
        ["Total Cholesterol", "185", "mg/dL", "<200"],
        ["HDL Cholesterol", "55", "mg/dL", ">40"],
        ["LDL Cholesterol", "110", "mg/dL", "<130"],
        ["Triglycerides", "100", "mg/dL", "<150"],
    ]
    lab_table = Table(lab_data, colWidths=[1.8*inch, 1.2*inch, 1*inch, 1.6*inch])
    lab_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f9f9f9')),
    ]))
    story.append(lab_table)
    story.append(Spacer(1, 10))

    story.append(Paragraph("CLINICAL HISTORY", heading_style))
    story.append(Paragraph("Tobacco Status: Never smoker<br/>Medical Conditions: None reported<br/>Current Medications: None<br/>Family History: No significant cardiac or metabolic disease", styles['Normal']))


def _add_hypertensive_case(story, styles, heading_style):
    """Hypertensive 45-year-old applicant"""
    story.append(Paragraph("VITAL SIGNS", heading_style))

    vitals_data = [
        ["Height:", "1.70 m", "Weight:", "88 kg"],
        ["BMI:", "30.4", "Blood Pressure:", "145/92 mmHg"],
        ["Heart Rate:", "78 bpm", "Temperature:", "37.2°C"],
    ]
    vitals_table = Table(vitals_data, colWidths=[1.5*inch, 1.5*inch, 1.5*inch, 1.5*inch])
    vitals_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fff0f0')),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))
    story.append(vitals_table)
    story.append(Spacer(1, 10))

    story.append(Paragraph("LABORATORY RESULTS (2026-03-10)", heading_style))
    lab_data = [
        ["Test", "Result", "Unit", "Reference Range"],
        ["Fasting Glucose", "102", "mg/dL", "70-100"],
        ["Total Cholesterol", "215", "mg/dL", "<200"],
        ["HDL Cholesterol", "40", "mg/dL", ">40"],
        ["LDL Cholesterol", "145", "mg/dL", "<130"],
        ["Triglycerides", "160", "mg/dL", "<150"],
    ]
    lab_table = Table(lab_data, colWidths=[1.8*inch, 1.2*inch, 1*inch, 1.6*inch])
    lab_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f9f9f9')),
    ]))
    story.append(lab_table)
    story.append(Spacer(1, 10))

    story.append(Paragraph("CLINICAL HISTORY", heading_style))
    story.append(Paragraph("Tobacco Status: Former smoker (quit 2 years ago)<br/>Medical Conditions: Hypertension (diagnosed 5 years ago)<br/>Current Medications: Amlodipine 5mg daily, Lisinopril 10mg daily<br/>Family History: Father had myocardial infarction at age 60", styles['Normal']))


def _add_diabetic_case(story, styles, heading_style):
    """Type 2 diabetic 52-year-old applicant"""
    story.append(Paragraph("VITAL SIGNS", heading_style))

    vitals_data = [
        ["Height:", "1.68 m", "Weight:", "92 kg"],
        ["BMI:", "32.6", "Blood Pressure:", "138/88 mmHg"],
        ["Heart Rate:", "80 bpm", "Temperature:", "37.1°C"],
    ]
    vitals_table = Table(vitals_data, colWidths=[1.5*inch, 1.5*inch, 1.5*inch, 1.5*inch])
    vitals_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fffaf0')),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))
    story.append(vitals_table)
    story.append(Spacer(1, 10))

    story.append(Paragraph("LABORATORY RESULTS (2026-03-08)", heading_style))
    lab_data = [
        ["Test", "Result", "Unit", "Reference Range"],
        ["Fasting Glucose", "145", "mg/dL", "70-100"],
        ["Total Cholesterol", "228", "mg/dL", "<200"],
        ["HDL Cholesterol", "35", "mg/dL", ">40"],
        ["LDL Cholesterol", "155", "mg/dL", "<130"],
        ["Triglycerides", "210", "mg/dL", "<150"],
    ]
    lab_table = Table(lab_data, colWidths=[1.8*inch, 1.2*inch, 1*inch, 1.6*inch])
    lab_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f9f9f9')),
    ]))
    story.append(lab_table)
    story.append(Spacer(1, 10))

    story.append(Paragraph("CLINICAL HISTORY", heading_style))
    story.append(Paragraph("Tobacco Status: Current smoker (10 cigarettes/day)<br/>Medical Conditions: Type 2 Diabetes (diagnosed 8 years ago), Hypertension<br/>Current Medications: Metformin 1000mg BID, Lisinopril 20mg daily, Simvastatin 40mg daily<br/>Family History: Mother has Diabetes Type 2, Father had stroke at age 68", styles['Normal']))


def _add_high_risk_case(story, styles, heading_style):
    """Multiple comorbidities, high-risk 58-year-old applicant"""
    story.append(Paragraph("VITAL SIGNS", heading_style))

    vitals_data = [
        ["Height:", "1.72 m", "Weight:", "105 kg"],
        ["BMI:", "35.5", "Blood Pressure:", "152/96 mmHg"],
        ["Heart Rate:", "88 bpm", "Temperature:", "37.3°C"],
    ]
    vitals_table = Table(vitals_data, colWidths=[1.5*inch, 1.5*inch, 1.5*inch, 1.5*inch])
    vitals_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#ffecec')),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))
    story.append(vitals_table)
    story.append(Spacer(1, 10))

    story.append(Paragraph("LABORATORY RESULTS (2026-03-05)", heading_style))
    lab_data = [
        ["Test", "Result", "Unit", "Reference Range"],
        ["Fasting Glucose", "168", "mg/dL", "70-100"],
        ["Total Cholesterol", "258", "mg/dL", "<200"],
        ["HDL Cholesterol", "32", "mg/dL", ">40"],
        ["LDL Cholesterol", "175", "mg/dL", "<130"],
        ["Triglycerides", "285", "mg/dL", "<150"],
    ]
    lab_table = Table(lab_data, colWidths=[1.8*inch, 1.2*inch, 1*inch, 1.6*inch])
    lab_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f9f9f9')),
    ]))
    story.append(lab_table)
    story.append(Spacer(1, 10))

    story.append(Paragraph("CLINICAL HISTORY", heading_style))
    story.append(Paragraph("Tobacco Status: Current smoker (20 cigarettes/day)<br/>Medical Conditions: Type 2 Diabetes (10 years), Hypertension, Hyperlipidemia, Obesity<br/>Current Medications: Metformin 1500mg BID, Amlodipine 10mg, Lisinopril 20mg, Atorvastatin 80mg, Aspirin 81mg daily<br/>Family History: Father died of MI at age 62, Mother has Diabetes and Hypertension", styles['Normal']))


def generate_all_test_cases():
    """Generate all four test case PDFs"""
    cases = [
        ("healthy_applicant.pdf", "Khouth Sophea", "healthy"),
        ("hypertensive_applicant.pdf", "Bun Sopheak", "hypertensive"),
        ("diabetic_applicant.pdf", "Chea Visal", "diabetic"),
        ("high_risk_applicant.pdf", "Som Kunthy", "high_risk"),
    ]

    print("\n[INFO] Generating synthetic medical record PDFs...\n")
    for filename, name, case_type in cases:
        create_medical_record_pdf(filename, name, case_type)

    print("\n[OK] All test PDFs generated in test_data/")


if __name__ == "__main__":
    generate_all_test_cases()
