#!/usr/bin/env python3
"""
Debug script to investigate PDF highlight numbering discrepancy.
Analyzes why element #4 in CSV appears as #509 in PDF.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any


def load_full_result() -> Dict[str, Any]:
    """Load the full_result.json from debug directory."""
    debug_path = Path(__file__).parent / "output" / "llm_diff_test" / "debug" / "llm_test" / "full_result.json"
    
    if not debug_path.exists():
        raise FileNotFoundError(f"Could not find full_result.json at {debug_path}")
    
    with open(debug_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def find_target_element(reading_order_data: List[Dict[str, Any]], target_text: str) -> None:
    """Find and analyze the target element with the specified text."""
    print(f"\n=== Searching for element with text: {target_text} ===\n")
    
    found_elements = []
    
    # Search through all elements
    for idx, element in enumerate(reading_order_data):
        if target_text in element.get('text', ''):
            found_elements.append((idx, element))
    
    if not found_elements:
        print(f"WARNING: Could not find element with text '{target_text}'")
        # Let's search for partial matches
        print("\nSearching for partial matches...")
        for idx, element in enumerate(reading_order_data):
            if "団体総合生活補償保険" in element.get('text', ''):
                print(f"Partial match at index {idx}: {element.get('text', '')[:50]}...")
        return
    
    # Print all found elements
    for idx, element in found_elements:
        print(f"Found at index: {idx}")
        print(f"Global order: {element.get('global_order', 'N/A')}")
        print(f"Page: {element.get('page', 'N/A')}")
        print(f"BBox: {element.get('bbox', 'N/A')}")
        print(f"Text: {element.get('text', '')[:100]}...")
        print("-" * 80)


def analyze_data_structure(reading_order_data: List[Dict[str, Any]]) -> None:
    """Analyze the data structure for potential issues."""
    print("\n=== Data Structure Analysis ===\n")
    
    # Check total number of elements
    print(f"Total elements: {len(reading_order_data)}")
    
    # Check for duplicate global_orders
    global_orders = [elem.get('global_order') for elem in reading_order_data if 'global_order' in elem]
    unique_global_orders = set(global_orders)
    
    if len(global_orders) != len(unique_global_orders):
        print(f"WARNING: Found duplicate global_orders! {len(global_orders)} total, {len(unique_global_orders)} unique")
    else:
        print(f"All global_orders are unique: {len(global_orders)} elements")
    
    # Check global_order sequence
    global_orders_sorted = sorted([g for g in global_orders if g is not None])
    if global_orders_sorted:
        print(f"Global order range: {global_orders_sorted[0]} to {global_orders_sorted[-1]}")
        
        # Check for gaps in global_order
        gaps = []
        for i in range(1, len(global_orders_sorted)):
            if global_orders_sorted[i] - global_orders_sorted[i-1] > 1:
                gaps.append((global_orders_sorted[i-1], global_orders_sorted[i]))
        
        if gaps:
            print(f"Found {len(gaps)} gaps in global_order sequence:")
            for start, end in gaps[:5]:  # Show first 5 gaps
                print(f"  Gap between {start} and {end}")
    
    # Check elements per page
    pages = {}
    for elem in reading_order_data:
        page = elem.get('page', 'unknown')
        pages[page] = pages.get(page, 0) + 1
    
    print(f"\nElements per page:")
    for page in sorted(pages.keys()):
        print(f"  Page {page}: {pages[page]} elements")
    
    # Check for elements without global_order
    no_global_order = [idx for idx, elem in enumerate(reading_order_data) if 'global_order' not in elem]
    if no_global_order:
        print(f"\nWARNING: {len(no_global_order)} elements without global_order at indices: {no_global_order[:10]}...")


def check_csv_correspondence() -> None:
    """Check if CSV numbering corresponds to array indices or global_order."""
    csv_path = Path(__file__).parent / "output" / "llm_diff_test" / "debug" / "2023_reading_order_estimated.csv"
    
    if csv_path.exists():
        print("\n=== CSV Analysis ===\n")
        with open(csv_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        # Skip header and check first few data lines
        for i, line in enumerate(lines[1:6], 1):  # Check first 5 data lines
            print(f"CSV Line {i}: {line.strip()[:100]}...")
    else:
        print(f"\nCould not find CSV at {csv_path}")


def main():
    """Main debug function."""
    try:
        # Load the full result
        full_result = load_full_result()
        
        # Extract reading order data for document 1 (2023)
        reading_order_doc1 = full_result.get('reading_order_doc1', [])
        
        if not reading_order_doc1:
            print("ERROR: No reading_order_doc1 data found in full_result.json")
            return
        
        # Find the target element
        target_text = "【団体総合生活補償保険（MS&AD型）、GLTD、所得補償保険】"
        find_target_element(reading_order_doc1, target_text)
        
        # Analyze the data structure
        analyze_data_structure(reading_order_doc1)
        
        # Check CSV correspondence
        check_csv_correspondence()
        
        # Additional check: Look at element #4 (index 3) and element #509 (index 508)
        print("\n=== Direct Element Inspection ===\n")
        
        if len(reading_order_doc1) > 3:
            elem_4 = reading_order_doc1[3]
            print(f"Element at index 3 (CSV #4):")
            print(f"  Global order: {elem_4.get('global_order', 'N/A')}")
            print(f"  Page: {elem_4.get('page', 'N/A')}")
            print(f"  Text: {elem_4.get('text', '')[:100]}...")
        
        if len(reading_order_doc1) > 508:
            elem_509 = reading_order_doc1[508]
            print(f"\nElement at index 508 (CSV #509):")
            print(f"  Global order: {elem_509.get('global_order', 'N/A')}")
            print(f"  Page: {elem_509.get('page', 'N/A')}")
            print(f"  Text: {elem_509.get('text', '')[:100]}...")
        
        # Search for elements with global_order 4 and 509
        print("\n=== Global Order Search ===\n")
        for idx, elem in enumerate(reading_order_doc1):
            if elem.get('global_order') == 4:
                print(f"Element with global_order=4 found at index {idx}:")
                print(f"  Text: {elem.get('text', '')[:100]}...")
            if elem.get('global_order') == 509:
                print(f"Element with global_order=509 found at index {idx}:")
                print(f"  Text: {elem.get('text', '')[:100]}...")
        
        # Check if highlighting is using wrong numbering
        print("\n=== Numbering System Check ===\n")
        print("The discrepancy suggests that:")
        print("- CSV uses global_order (1-based) for numbering")
        print("- PDF highlighting might be using a different numbering system")
        print(f"- Element with global_order=4 is at array index {3}")
        print(f"- Total elements: {len(reading_order_doc1)}")
        
        # Check if there's a pattern with page offsets
        page_offsets = {}
        cumulative = 0
        for elem in reading_order_doc1:
            page = elem.get('page', 0)
            if page not in page_offsets:
                page_offsets[page] = cumulative
            cumulative += 1
        
        print("\nPage offset analysis:")
        for page, offset in sorted(page_offsets.items()):
            print(f"  Page {page} starts at element index {offset}")
        
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()