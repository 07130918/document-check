#!/usr/bin/env python3
"""
Enhanced debug script to investigate PDF highlight numbering discrepancy.
Checks multiple sources of numbering to identify the issue.
"""

import json
import csv
import os
from pathlib import Path
from typing import Dict, List, Any, Tuple


def load_all_debug_data() -> Tuple[Dict[str, Any], List[List[str]], List[List[str]]]:
    """Load all debug data including JSON and CSV files."""
    base_path = Path(__file__).parent / "output" / "llm_diff_test"
    
    # Load full_result.json
    json_path = base_path / "debug" / "llm_test" / "full_result.json"
    with open(json_path, 'r', encoding='utf-8') as f:
        full_result = json.load(f)
    
    # Load CSV files
    csv_path_estimated = base_path / "debug" / "2023_reading_order_estimated.csv"
    csv_path_original = base_path / "debug" / "2023_reading_order_original.csv"
    
    csv_data_estimated = []
    if csv_path_estimated.exists():
        with open(csv_path_estimated, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            csv_data_estimated = list(reader)
    
    csv_data_original = []
    if csv_path_original.exists():
        with open(csv_path_original, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            csv_data_original = list(reader)
    
    return full_result, csv_data_estimated, csv_data_original


def analyze_target_element() -> None:
    """Analyze the specific target element across all data sources."""
    target_text = "【団体総合生活補償保険（MS&AD型）、GLTD、所得補償保険】"
    
    print(f"\n=== Analyzing Target Element: {target_text} ===\n")
    
    # Load all data
    full_result, csv_estimated, csv_original = load_all_debug_data()
    reading_order_doc1 = full_result.get('reading_order_doc1', [])
    
    # 1. Check in reading_order_doc1 (JSON)
    print("1. In reading_order_doc1 (JSON):")
    for idx, element in enumerate(reading_order_doc1):
        if target_text in element.get('text', ''):
            print(f"   - Array index: {idx}")
            print(f"   - CSV row number (1-based): {idx + 1}")
            print(f"   - Global order: {element.get('global_order', 'N/A')}")
            print(f"   - Page: {element.get('page', 'N/A')}")
            print(f"   - BBox: {element.get('bbox', 'N/A')}")
            break
    
    # 2. Check in CSV files
    print("\n2. In CSV files:")
    
    # Check estimated CSV
    if csv_estimated:
        print("   a) In 2023_reading_order_estimated.csv:")
        for row_idx, row in enumerate(csv_estimated[1:], 1):  # Skip header
            if len(row) > 1 and target_text in row[1]:
                print(f"      - CSV row number: {row_idx}")
                print(f"      - CSV number column: {row[0]}")
                print(f"      - Text: {row[1][:100]}...")
                break
    
    # Check original CSV
    if csv_original:
        print("   b) In 2023_reading_order_original.csv:")
        for row_idx, row in enumerate(csv_original[1:], 1):  # Skip header
            if len(row) > 1 and target_text in row[1]:
                print(f"      - CSV row number: {row_idx}")
                print(f"      - CSV number column: {row[0]}")
                print(f"      - Text: {row[1][:100]}...")
                break
    
    # 3. Check differences CSV
    diff_csv_path = Path(__file__).parent / "output" / "llm_diff_test" / "llm_test_differences.csv"
    if diff_csv_path.exists():
        print("\n3. In differences CSV:")
        with open(diff_csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            diff_data = list(reader)
        
        for row_idx, row in enumerate(diff_data[1:], 1):  # Skip header
            if len(row) > 3 and (target_text in row[3] or target_text in row[4]):
                print(f"   - Difference number: {row[0]}")
                print(f"   - Change type: {row[1]}")
                print(f"   - Page: {row[2]}")
                print(f"   - Original text: {row[3][:100] if len(row[3]) > 0 else 'N/A'}")
                print(f"   - Modified text: {row[4][:100] if len(row[4]) > 0 else 'N/A'}")


def check_numbering_consistency() -> None:
    """Check if numbering is consistent across different elements."""
    print("\n=== Numbering Consistency Check ===\n")
    
    full_result, csv_estimated, _ = load_all_debug_data()
    reading_order_doc1 = full_result.get('reading_order_doc1', [])
    
    # Check first 10 elements
    print("First 10 elements comparison (JSON vs CSV):")
    print("-" * 80)
    print(f"{'Index':>6} | {'Global Order':>12} | {'CSV Number':>10} | {'Text (first 40 chars)':>40}")
    print("-" * 80)
    
    for idx in range(min(10, len(reading_order_doc1))):
        element = reading_order_doc1[idx]
        global_order = element.get('global_order', 'N/A')
        text = element.get('text', '')[:40]
        
        # Get CSV number
        csv_number = 'N/A'
        if csv_estimated and idx + 1 < len(csv_estimated):
            csv_row = csv_estimated[idx + 1]  # +1 to skip header
            if len(csv_row) > 0:
                csv_number = csv_row[0]
        
        print(f"{idx:>6} | {global_order:>12} | {csv_number:>10} | {text:>40}")
    
    # Check if there's a pattern
    print("\n\nNumbering Pattern Analysis:")
    mismatches = 0
    for idx, element in enumerate(reading_order_doc1[:50]):  # Check first 50
        global_order = element.get('global_order')
        expected_order = idx + 1
        
        if global_order and global_order != expected_order:
            mismatches += 1
            if mismatches <= 5:  # Show first 5 mismatches
                print(f"Mismatch at index {idx}: global_order={global_order}, expected={expected_order}")
    
    if mismatches > 0:
        print(f"\nTotal mismatches in first 50 elements: {mismatches}")
    else:
        print("\nNo mismatches found - global_order matches array index + 1")


def check_pdf_highlight_labels() -> None:
    """Check what labels would be assigned to PDF highlights."""
    print("\n=== PDF Highlight Label Assignment ===\n")
    
    full_result, _, _ = load_all_debug_data()
    reading_order_doc1 = full_result.get('reading_order_doc1', [])
    
    print("Based on the code in _save_reading_order_pdfs:")
    print("- For each element, the label is: bbox_data.get('global_order', idx + 1)")
    print("\nThis means:")
    print("- If global_order exists, it uses that value")
    print("- If global_order doesn't exist, it uses array index + 1")
    
    # Check if all elements have global_order
    elements_with_global_order = sum(1 for e in reading_order_doc1 if 'global_order' in e)
    print(f"\nElements with global_order: {elements_with_global_order}/{len(reading_order_doc1)}")
    
    if elements_with_global_order == len(reading_order_doc1):
        print("All elements have global_order - PDF labels will match global_order values")
    else:
        print("Some elements missing global_order - those will use array index + 1")


def main():
    """Main debug function."""
    try:
        # Analyze the specific target element
        analyze_target_element()
        
        # Check numbering consistency
        check_numbering_consistency()
        
        # Check PDF highlight label assignment
        check_pdf_highlight_labels()
        
        print("\n\n=== SUMMARY ===")
        print("The numbering system works as follows:")
        print("1. CSV files use the 'global_order' field for numbering (1-based)")
        print("2. PDF highlights also use 'global_order' for labels")
        print("3. Element #4 in CSV corresponds to global_order=4")
        print("4. If you're seeing #509 in the PDF, it might be:")
        print("   - A different element entirely")
        print("   - A different PDF file")
        print("   - An issue with PDF viewer or zoom level")
        
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()