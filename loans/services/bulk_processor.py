"""
Bulk CSV processing module for dedupe checking.
Handles CSV validation, row processing, and result generation.
"""

import csv
from typing import List
from .lender_call import process_lender


def process_csv(
    input_csv_path: str,
    output_csv_path: str,
    lenders: List[str],
    check_dedupe: bool = False,
    send_leads: bool = False
) -> None:
    """
    Process a CSV file for bulk dedupe checking.
    
    Args:
        input_csv_path: Path to input CSV file
        output_csv_path: Path to output CSV file
        lenders: List of lender names to check against
        check_dedupe: Whether to perform dedupe checks
        send_leads: Whether to create leads
    
    Raises:
        ValueError: If CSV validation fails
        FileNotFoundError: If input CSV doesn't exist
    """
    rows = _read_and_validate_csv(input_csv_path)
    results = _process_rows(rows, lenders, check_dedupe, send_leads)
    _write_results_csv(output_csv_path, results)


def _read_and_validate_csv(csv_path: str) -> List[dict]:
    """
    Read and validate CSV file.
    
    Args:
        csv_path: Path to CSV file
    
    Returns:
        List of row dictionaries
    
    Raises:
        ValueError: If CSV doesn't contain required columns
        FileNotFoundError: If file doesn't exist
    """
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        if not reader.fieldnames:
            raise ValueError("CSV file is empty or has no headers")
        
        headers = [h.strip() for h in reader.fieldnames]
        
        has_phone = 'phoneNumber' in headers or 'phonenumber' in headers or 'mobile' in headers
        has_pan = 'pan' in headers
        
        if not has_phone and not has_pan:
            raise ValueError(
                "CSV must contain at least one of these columns: 'phoneNumber' or 'pan'"
            )
        
        rows = []
        for row in reader:
            normalized_row = {k.strip(): v for k, v in row.items()}
            rows.append(normalized_row)
        
        return rows


def _process_rows(rows: List[dict], lenders: List[str], check_dedupe: bool, send_leads: bool) -> List[dict]:
    """
    Process all rows against all lenders.
    
    Args:
        rows: List of CSV row dictionaries
        lenders: List of lender names
        check_dedupe: Whether to perform dedupe checks
        send_leads: Whether to create leads
    
    Returns:
        List of result dictionaries
    """
    results = []
    
    for row_num, row in enumerate(rows, start=1):
        for lender in lenders:
            lender_result = process_lender(lender, row, check_dedupe, send_leads)
            
            result_row = {
                'row_number': row_num,
                'lender': lender,
                'status': lender_result.get('status', ''),
                'result': lender_result.get('result', ''),
                'lead_id': lender_result.get('lead_id', ''),
                'utm_link': lender_result.get('utm_link', ''),
                'message': lender_result.get('message', '')
            }
            
            results.append(result_row)
    
    return results


def _clean_value(value: str) -> str | None:
    """
    Clean and normalize a CSV value.
    
    Args:
        value: Raw value from CSV
    
    Returns:
        Cleaned value or None if empty
    """
    if value is None:
        return None
    
    cleaned = value.strip()
    
    if not cleaned:
        return None
    
    return cleaned


def _write_results_csv(output_path: str, results: List[dict]) -> None:
    """
    Write results to output CSV file.
    
    Args:
        output_path: Path to output CSV file
        results: List of result dictionaries
    """
    fieldnames = [
        'row_number', 'lender', 'status', 'result', 
        'lead_id', 'utm_link', 'message'
    ]
    
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
