"""End-to-end demo: Generate PDFs, extract data, validate, and save results"""

import json
import os
from pathlib import Path
from datetime import datetime

from .generator import generate_all_test_cases
from .extractor import extract_medical_record
from .validator import validate_medical_record


def create_output_dir():
    """Create output directory for results"""
    output_dir = Path("test_outputs")
    output_dir.mkdir(exist_ok=True)
    return output_dir


def run_extraction_demo():
    """
    Main demo:
    1. Generate 4 synthetic medical PDFs
    2. Extract data from each using Claude
    3. Validate data
    4. Save results to JSON
    5. Print summary
    """
    print("\n" + "="*70)
    print("MEDICAL READER DEMO: OCR -> JSON -> Validation")
    print("="*70)

    # Step 1: Generate test PDFs
    print("\n[1/3] Generating synthetic medical record PDFs...")
    generate_all_test_cases()

    # Step 2: Extract and validate
    print("\n[2/3] Extracting and validating medical records...\n")

    test_cases = [
        ("test_data/healthy_applicant.pdf", "POL-2026-0001", "Healthy Applicant"),
        ("test_data/hypertensive_applicant.pdf", "POL-2026-0002", "Hypertensive Applicant"),
        ("test_data/diabetic_applicant.pdf", "POL-2026-0003", "Diabetic Applicant"),
        ("test_data/high_risk_applicant.pdf", "POL-2026-0004", "High-Risk Applicant"),
    ]

    output_dir = create_output_dir()
    results = []

    for pdf_path, policy_id, case_name in test_cases:
        print(f"Processing: {case_name}")
        print(f"  File: {pdf_path}")

        try:
            # Extract
            print(f"  > Extracting with Claude...")
            record = extract_medical_record(pdf_path, policy_id=policy_id)

            # Validate
            print(f"  > Validating...")
            record = validate_medical_record(record)

            # Save to JSON
            output_file = output_dir / f"{policy_id}_extracted.json"
            with open(output_file, "w") as f:
                # Serialize with datetime handling
                record_dict = record.model_dump(mode="json")
                json.dump(record_dict, f, indent=2, default=str)

            results.append({
                "policy_id": policy_id,
                "case": case_name,
                "status": "success",
                "confidence": record.extraction_meta.confidence,
                "routing": record.validation.routing if record.validation else "unknown",
                "flags": record.validation.flags if record.validation else [],
                "output_file": str(output_file),
            })

            # Print validation result
            if record.validation:
                print(f"  [OK] Validation: {record.validation.routing}")
                if record.validation.flags:
                    print(f"    Flags: {', '.join(record.validation.flags[:2])}")
                    if len(record.validation.flags) > 2:
                        print(f"           ... and {len(record.validation.flags) - 2} more")
            print()

        except FileNotFoundError as e:
            print(f"  [ERROR] File not found: {e}\n")
            results.append({
                "policy_id": policy_id,
                "case": case_name,
                "status": "error",
                "error": str(e),
            })
        except Exception as e:
            print(f"  [ERROR] {e}\n")
            results.append({
                "policy_id": policy_id,
                "case": case_name,
                "status": "error",
                "error": str(e),
            })

    # Step 3: Print summary
    print("[3/3] Summary\n")
    print("="*70)

    successful = [r for r in results if r["status"] == "success"]
    failed = [r for r in results if r["status"] == "error"]

    print(f"[OK] Successful extractions: {len(successful)}/{len(results)}")
    for r in successful:
        print(f"  - {r['case']:25} -> {r['routing']:15} (confidence: {r['confidence']:.2f})")

    if failed:
        print(f"\n[ERROR] Failed extractions: {len(failed)}/{len(results)}")
        for r in failed:
            print(f"  - {r['case']:25} -> {r['error']}")

    print(f"\nResults saved to: {output_dir}/")
    print("="*70)

    # Final routing summary
    print("\nRouting Summary:")
    routing_counts = {}
    for r in successful:
        routing = r["routing"]
        routing_counts[routing] = routing_counts.get(routing, 0) + 1

    for routing, count in routing_counts.items():
        print(f"  {routing}: {count} case(s)")

    print("\n" + "="*70)
    print("Demo complete!")
    print("="*70 + "\n")


def inspect_extracted_file(json_path: str):
    """Pretty-print a saved extraction result"""
    try:
        with open(json_path, "r") as f:
            data = json.load(f)
        print(json.dumps(data, indent=2))
    except FileNotFoundError:
        print(f"File not found: {json_path}")
    except json.JSONDecodeError:
        print(f"Invalid JSON in file: {json_path}")


if __name__ == "__main__":
    run_extraction_demo()

    # Optionally inspect first result
    first_output = Path("test_outputs/POL-2026-0001_extracted.json")
    if first_output.exists():
        print("\nExample extracted record (POL-2026-0001):")
        print("-" * 70)
        inspect_extracted_file(str(first_output))
