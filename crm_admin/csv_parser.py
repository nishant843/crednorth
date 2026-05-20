"""
CSV parsing utility for staging table ingestion.
Streams CSV rows and bulk-inserts into UploadedLeadRow.
Memory-safe for large uploads.
"""

import csv
import io
import logging
from contextlib import contextmanager

from django.db import transaction

from crm_admin.models import UploadedLeadRow

logger = logging.getLogger(__name__)


def _detect_csv_encoding(csv_file, encoding='utf-8-sig', sample_size=4096):
    """Detect a usable encoding without reading the full file into memory."""
    binary_stream = getattr(csv_file, 'file', csv_file)

    if hasattr(binary_stream, 'seek'):
        binary_stream.seek(0)

    sample = binary_stream.read(sample_size)
    if hasattr(binary_stream, 'seek'):
        binary_stream.seek(0)

    if not sample:
        raise ValueError('CSV file is empty or has no headers')

    for enc in (encoding, 'utf-8', 'utf-16'):
        try:
            sample.decode(enc)
            return enc
        except (UnicodeDecodeError, LookupError):
            continue

    raise ValueError('CSV encoding not supported (utf-8-sig, utf-8, utf-16)')


@contextmanager
def parse_csv_stream(csv_file, encoding='utf-8-sig'):
    """Yield a streaming DictReader for an uploaded CSV file."""
    detected_encoding = _detect_csv_encoding(csv_file, encoding=encoding)
    binary_stream = getattr(csv_file, 'file', csv_file)

    if hasattr(binary_stream, 'seek'):
        binary_stream.seek(0)

    text_handle = io.TextIOWrapper(binary_stream, encoding=detected_encoding, newline='')
    try:
        reader = csv.DictReader(text_handle)
        if not reader.fieldnames:
            raise ValueError('CSV file is empty or has no headers')
        yield reader, reader.fieldnames
    finally:
        try:
            text_handle.detach()
        except Exception:
            pass


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
    batch_size = max(1, min(int(batch_size or 1), 1000))

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
        for row_num, row in enumerate(reader, start=1):
            total_rows += 1

            # Extract phone number with flexible field matching.
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

            # Normalize phone to digits only.
            if phone:
                phone = ''.join(c for c in phone if c.isdigit())
                if len(phone) != 10:
                    phone = ''

            # Extract other fields.
            pan = row.get('pan_number') or row.get('pan') or row.get('pancard') or ''
            pan = (pan or '').strip().upper()

            pincode = row.get('pincode') or row.get('pin_code') or row.get('pin') or ''
            pincode = ''.join(c for c in (pincode or '') if c.isdigit())
            if len(pincode) != 6:
                pincode = ''

            batch.append(UploadedLeadRow(
                upload_job=upload_job,
                phone_number=phone or '',
                pan_number=pan,
                pincode=pincode,
                raw_data=dict(row),
                lender_selection='[]',
                processing_status=UploadedLeadRow.STATUS_PENDING,
            ))

            if len(batch) >= batch_size:
                with transaction.atomic():
                    UploadedLeadRow.objects.bulk_create(batch, batch_size=batch_size)
                    batch_count += 1
                    upload_job.total_rows = total_rows
                    upload_job.current_batch = batch_count
                    upload_job.total_batches = batch_count
                    upload_job.save(update_fields=['total_rows', 'current_batch', 'total_batches', 'updated_at'])
                batch.clear()
                logger.info('Batch %s inserted for job %s', batch_count, upload_job.id)

        if batch:
            with transaction.atomic():
                UploadedLeadRow.objects.bulk_create(batch, batch_size=batch_size)
                batch_count += 1
                upload_job.total_rows = total_rows
                upload_job.current_batch = batch_count
                upload_job.total_batches = batch_count
                upload_job.save(update_fields=['total_rows', 'current_batch', 'total_batches', 'updated_at'])
            logger.info('Final batch %s inserted for job %s', batch_count, upload_job.id)

        upload_job.total_rows = total_rows
        upload_job.total_batches = batch_count
        upload_job.save(update_fields=['total_rows', 'total_batches', 'updated_at'])
        
        logger.info(f"CSV parsing complete: {total_rows} rows in {batch_count} batches for job {upload_job.id}")
        
        return total_rows
    
    except Exception as exc:
        logger.exception(f"CSV bulk insert failed for job {upload_job.id}: {exc}")
        raise
