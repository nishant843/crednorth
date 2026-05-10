"""
CSV parsing utility for staging table ingestion.
Streams CSV rows and bulk-inserts into UploadedLeadRow.
Memory-safe for large uploads.
"""

import csv
import io
import logging
from django.db import transaction
from crm_admin.models import UploadedLeadRow, UploadJob

logger = logging.getLogger(__name__)


def parse_csv_stream(csv_file, encoding='utf-8-sig'):
    """
    Stream CSV file and detect encoding.
    
    Args:
        csv_file: Django UploadedFile object
        encoding: Default encoding to try
    
    Yields:
        csv.DictReader rows
    
    Raises:
        ValueError if encoding not detected
    """
    raw_bytes = csv_file.read()
    
    decoded_csv = None
    for enc in (encoding, 'utf-8', 'utf-16'):
        try:
            decoded_csv = raw_bytes.decode(enc)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    
    if decoded_csv is None:
        raise ValueError("CSV encoding not supported (utf-8-sig, utf-8, utf-16)")
    
    reader = csv.DictReader(io.StringIO(decoded_csv))
    if not reader.fieldnames:
        raise ValueError("CSV file is empty or has no headers")
    
    return reader, reader.fieldnames


def bulk_insert_lead_rows(upload_job, reader, fieldnames, batch_size=500):
    """
    Stream CSV rows and bulk insert into UploadedLeadRow.
    Updates UploadJob total_rows and current_batch.
    
    Args:
        upload_job: UploadJob instance
        reader: csv.DictReader
        fieldnames: CSV column names
        batch_size: Rows per bulk_create batch
    
    Returns:
        Total rows inserted
    
    Raises:
        ValueError if required fields missing
    """
    # Validate required fields
    required_fields = ['phoneNumber', 'phonenumber', 'mobile', 'phone_number']
    has_phone = any(
        field.lower().replace('_', '').replace('-', '') 
        in [f.lower().replace('_', '').replace('-', '') for f in fieldnames]
        for field in required_fields
    )
    
    if not has_phone:
        raise ValueError(
            "CSV must contain phone column: phoneNumber, phonenumber, mobile, or phone_number"
        )
    
    # Build field normalization lookup
    field_lookup = {}
    for field in fieldnames:
        normalized = field.strip().lower()
        field_lookup[normalized] = field
    
    batch = []
    total_rows = 0
    batch_count = 0
    
    try:
        with transaction.atomic():
            for row_num, row in enumerate(reader, start=1):
                total_rows += 1
                
                # Extract phone number with flexible field matching
                phone = None
                for phone_alias in ['phonenumber', 'phone_number', 'mobile', 'phone']:
                    key = next(
                        (k for k in field_lookup.keys() 
                         if k.replace('_', '').replace('-', '') == phone_alias),
                        None
                    )
                    if key and key in field_lookup:
                        phone = row.get(field_lookup[key], '').strip()
                        if phone:
                            break
                
                # Normalize phone to digits only
                if phone:
                    phone = ''.join(c for c in phone if c.isdigit())
                    if len(phone) != 10:
                        phone = ''
                
                # Extract other fields
                pan = row.get('pan_number') or row.get('pan') or row.get('pancard') or ''
                pan = (pan or '').strip().upper()
                
                pincode = row.get('pincode') or row.get('pin_code') or row.get('pin') or ''
                pincode = ''.join(c for c in (pincode or '') if c.isdigit())
                if len(pincode) != 6:
                    pincode = ''
                
                # Create staging row
                lead_row = UploadedLeadRow(
                    upload_job=upload_job,
                    phone_number=phone or '',
                    pan_number=pan,
                    pincode=pincode,
                    raw_data=dict(row),
                    lender_selection='[]',  # Will be set later
                    processing_status=UploadedLeadRow.STATUS_PENDING
                )
                
                batch.append(lead_row)
                
                # Flush batch
                if len(batch) >= batch_size:
                    UploadedLeadRow.objects.bulk_create(batch, batch_size=batch_size)
                    batch_count += 1
                    
                    # Update progress
                    upload_job.total_rows = total_rows
                    upload_job.current_batch = batch_count
                    upload_job.save(update_fields=['total_rows', 'current_batch', 'updated_at'])
                    
                    batch.clear()
                    logger.info(f"Batch {batch_count} inserted for job {upload_job.id}")
            
            # Flush remaining rows
            if batch:
                UploadedLeadRow.objects.bulk_create(batch, batch_size=batch_size)
                batch_count += 1
                logger.info(f"Final batch {batch_count} inserted for job {upload_job.id}")
        
        # Update job totals
        upload_job.total_rows = total_rows
        upload_job.total_batches = batch_count
        upload_job.save(update_fields=['total_rows', 'total_batches', 'updated_at'])
        
        logger.info(f"CSV parsing complete: {total_rows} rows in {batch_count} batches for job {upload_job.id}")
        
        return total_rows
    
    except Exception as exc:
        logger.exception(f"CSV bulk insert failed for job {upload_job.id}: {exc}")
        raise
