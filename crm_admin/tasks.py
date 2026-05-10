import csv
import logging
import json
import tempfile
import os
from datetime import datetime
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor, as_completed

from celery import shared_task
from django.core.validators import validate_email
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models.signals import post_save

from crm_admin.models import UploadJob, UploadedLeadRow
from users.models import User
from loans.services.lender_call import process_lender


HEADER_ALIASES = {
    'phone_number': ['phone_number', 'phone', 'mobile', 'mobile_number', 'contact', 'contact_number'],
    'first_name': ['first_name', 'firstname', 'first'],
    'last_name': ['last_name', 'lastname', 'surname', 'last'],
    'email': ['email', 'email_id', 'mail'],
    'pan_number': ['pan_number', 'pan', 'pan_no', 'pancard', 'pan_card'],
    'date_of_birth': ['date_of_birth', 'dob', 'birth_date'],
    'gender': ['gender', 'sex'],
    'city': ['city', 'town'],
    'state': ['state', 'province'],
    'pin_code': ['pin_code', 'pincode', 'pin', 'zip', 'zipcode', 'postal_code'],
    'monthly_income': ['monthly_income', 'income', 'salary', 'monthly_salary'],
    'profession': ['profession', 'employment_type', 'occupation', 'job_type'],
    'bureau_score': ['bureau_score', 'cibil', 'cibil_score', 'credit_score'],
    'name': ['name', 'full_name', 'fullname'],
}

VALID_GENDERS = {'Male', 'Female', 'Other'}
GENDER_MAP = {
    'm': 'Male',
    'male': 'Male',
    'f': 'Female',
    'female': 'Female',
    'o': 'Other',
    'other': 'Other',
}
VALID_PROFESSIONS = {'Salaried', 'Self-Employed', 'Business'}
PROFESSION_MAP = {
    'salaried': 'Salaried',
    'self employed': 'Self-Employed',
    'self-employed': 'Self-Employed',
    'business': 'Business',
}
PAN_FOURTH_ALLOWED = {'P', 'C', 'H', 'F', 'A', 'T', 'B', 'G', 'J', 'L'}


logger = logging.getLogger(__name__)


def _normalize_header(header):
    if not header:
        return ''
    normalized = str(header).replace('\ufeff', '').strip().lower()
    out = []
    last_underscore = False
    for ch in normalized:
        if ch.isalnum():
            out.append(ch)
            last_underscore = False
        elif not last_underscore:
            out.append('_')
            last_underscore = True
    return ''.join(out).strip('_')


def _build_header_lookup(fieldnames):
    lookup = {}
    for field in fieldnames or []:
        normalized = _normalize_header(field)
        if normalized and normalized not in lookup:
            lookup[normalized] = field
    return lookup


def _get_value(row, header_lookup, canonical_key):
    aliases = HEADER_ALIASES.get(canonical_key, [canonical_key])
    for alias in aliases:
        source = header_lookup.get(alias)
        if source is not None:
            return (row.get(source) or '').strip()
    return ''


def _parse_date(raw):
    if not raw:
        return None
    for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%Y/%m/%d'):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _valid_pan(raw_pan):
    pan = (raw_pan or '').strip().upper()
    if len(pan) != 10:
        return ''
    if not (pan[:5].isalpha() and pan[5:9].isdigit() and pan[9].isalpha()):
        return ''
    if pan[3] not in PAN_FOURTH_ALLOWED:
        return ''
    return pan


def _valid_pin(raw_pin):
    pin = (raw_pin or '').strip()
    if pin.isdigit() and len(pin) == 6:
        return pin
    return ''


def _valid_email(raw_email):
    email = (raw_email or '').strip()
    if not email:
        return ''
    try:
        validate_email(email)
        return email
    except DjangoValidationError:
        return ''


def _valid_gender(raw_gender):
    if not raw_gender:
        return ''
    mapped = GENDER_MAP.get(raw_gender.strip().lower(), raw_gender.strip())
    return mapped if mapped in VALID_GENDERS else ''


def _valid_profession(raw_profession):
    if not raw_profession:
        return ''
    mapped = PROFESSION_MAP.get(raw_profession.strip().lower(), raw_profession.strip())
    return mapped if mapped in VALID_PROFESSIONS else ''


def _valid_income(raw_income):
    if not raw_income:
        return None
    try:
        return float(raw_income)
    except (TypeError, ValueError):
        return None


def _valid_bureau(raw_score):
    if not raw_score:
        return None
    try:
        score = int(raw_score)
    except (TypeError, ValueError):
        return None
    return score if 0 <= score <= 900 else None


def _row_to_user(row, header_lookup):
    phone = _get_value(row, header_lookup, 'phone_number')
    phone = ''.join(ch for ch in phone if ch.isdigit())
    if len(phone) != 10:
        return None

    first_name = _get_value(row, header_lookup, 'first_name')
    last_name = _get_value(row, header_lookup, 'last_name')
    if not first_name and not last_name:
        full_name = _get_value(row, header_lookup, 'name')
        if full_name:
            parts = full_name.split(None, 1)
            first_name = parts[0]
            if len(parts) > 1:
                last_name = parts[1]

    return User(
        phone_number=phone,
        first_name=first_name,
        last_name=last_name,
        email=_valid_email(_get_value(row, header_lookup, 'email')),
        
        pan_number=_valid_pan(_get_value(row, header_lookup, 'pan_number')),
        date_of_birth=_parse_date(_get_value(row, header_lookup, 'date_of_birth')),
        gender=_valid_gender(_get_value(row, header_lookup, 'gender')),
        city=_get_value(row, header_lookup, 'city'),
        state=_get_value(row, header_lookup, 'state'),
        pin_code=_valid_pin(_get_value(row, header_lookup, 'pin_code')),
        profession=_valid_profession(_get_value(row, header_lookup, 'profession')),
        monthly_income=_valid_income(_get_value(row, header_lookup, 'monthly_income')),
        bureau_score=_valid_bureau(_get_value(row, header_lookup, 'bureau_score')),
        status='pending',
    )


@contextmanager
def _suspend_user_post_save_signal():
    """Temporarily disconnect User post_save receivers if any are connected."""
    disconnected = []
    try:
        # Copy receiver list so we can safely iterate while disconnecting.
        for _key, receiver_ref, _is_async in list(post_save.receivers):
            receiver = receiver_ref()
            if receiver is None:
                continue
            disconnected_ok = post_save.disconnect(receiver=receiver, sender=User)
            if disconnected_ok:
                disconnected.append(receiver)
        yield
    finally:
        for receiver in disconnected:
            post_save.connect(receiver=receiver, sender=User)


def _flush_batch(batch, batch_size):
    """Insert one batch and clear batch memory. Returns True on success."""
    if not batch:
        return True
    try:
        with transaction.atomic():
            User.objects.bulk_create(batch, batch_size=batch_size, ignore_conflicts=True)
        return True
    except Exception as exc:
        logger.error('Bulk insert batch failed; continuing. err=%s', exc)
        return False
    finally:
        batch.clear()


@shared_task(bind=True)
def process_csv_upload(self, job_id):
    # Keep memory low for Render 512MB instances.
    batch_size = 500

    try:
        job = UploadJob.objects.get(pk=job_id)
    except UploadJob.DoesNotExist:
        return {'ok': False, 'error': 'job_not_found'}

    job.status = UploadJob.STATUS_PROCESSING
    job.save(update_fields=['status', 'updated_at'])

    try:
        with _suspend_user_post_save_signal():
            with job.file.open('r', encoding='utf-8-sig', newline='') as csv_file:
                # Stream rows line-by-line; never load full CSV into memory.
                reader = csv.DictReader(csv_file)
                header_lookup = _build_header_lookup(reader.fieldnames)

                aliases = HEADER_ALIASES['phone_number']
                if not any(alias in header_lookup for alias in aliases):
                    job.status = UploadJob.STATUS_FAILED
                    job.save(update_fields=['status', 'updated_at'])
                    return {'ok': False, 'error': 'missing_phone_column'}

                batch = []
                total_rows = 0
                failed_batches = 0

                for row in reader:
                    total_rows += 1
                    user_obj = _row_to_user(row, header_lookup)
                    if user_obj is not None:
                        batch.append(user_obj)

                    if len(batch) >= batch_size:
                        ok = _flush_batch(batch, batch_size)
                        if not ok:
                            failed_batches += 1
                        # Persist progress after each batch to keep UI accurate.
                        job.total_rows = total_rows
                        job.processed_rows = total_rows
                        job.save(update_fields=['total_rows', 'processed_rows', 'updated_at'])

                if batch:
                    ok = _flush_batch(batch, batch_size)
                    if not ok:
                        failed_batches += 1

                job.total_rows = total_rows
                job.processed_rows = total_rows
                job.status = UploadJob.STATUS_COMPLETED
                job.save(update_fields=['total_rows', 'processed_rows', 'status', 'updated_at'])

                if failed_batches:
                    logger.warning('CSV job completed with failed batches. job_id=%s failed_batches=%s', job_id, failed_batches)

                return {'ok': True, 'total_rows': total_rows, 'failed_batches': failed_batches}

    except Exception as exc:
        logger.exception('CSV upload task failed. job_id=%s err=%s', job_id, exc)
        job.status = UploadJob.STATUS_FAILED
        job.save(update_fields=['status', 'updated_at'])
        raise


@shared_task(bind=True)
def process_lead_dedupe_push(self, job_id):
    """
    Async Celery task for lead processing (dedupe + push).
    NEW: Processes UploadedLeadRow DB records instead of file paths.
    Worker is filesystem-independent (Render-compatible).
    
    Args:
        job_id: UploadJob ID (all other info read from DB)
    """
    BATCH_SIZE = 50  # Process rows in smaller batches for progress updates
    MAX_WORKERS = min(16, max(4, (os.cpu_count() or 1) * 3))
    
    try:
        job = UploadJob.objects.get(pk=job_id)
    except UploadJob.DoesNotExist:
        logger.error(f"UploadJob {job_id} not found")
        return {'ok': False, 'error': 'job_not_found'}
    
    # Mark as processing
    job.status = UploadJob.STATUS_PROCESSING
    job.started_at = datetime.now()
    job.save(update_fields=['status', 'started_at', 'updated_at'])
    
    try:
        # Get lenders and flags from UploadJob
        lenders = json.loads(job.lenders or '[]')
        check_dedupe = job.check_dedupe
        send_leads = job.send_leads
        
        if not lenders:
            raise ValueError("No lenders configured in job")
        
        # Fetch all staging rows for this job
        lead_rows = UploadedLeadRow.objects.filter(
            upload_job=job,
            processing_status=UploadedLeadRow.STATUS_PENDING
        ).order_by('id')
        
        total_rows = lead_rows.count()
        if total_rows == 0:
            raise ValueError("No lead rows to process")
        
        job.total_rows = total_rows
        job.total_batches = (total_rows + BATCH_SIZE - 1) // BATCH_SIZE
        job.save(update_fields=['total_rows', 'total_batches', 'updated_at'])
        
        # Process rows with ThreadPoolExecutor
        success_count = 0
        failed_count = 0
        processed_count = 0
        
        def _process_single_row_lender(lead_row, lender):
            """Process one staging row against one lender."""
            try:
                # Get raw data from staging row
                row_data = lead_row.raw_data or {}
                
                # Process with lender API
                result = process_lender(lender, row_data, check_dedupe, send_leads)
                
                return {
                    'lead_row_id': lead_row.id,
                    'phone': lead_row.phone_number,
                    'lender': lender,
                    'result': result
                }
            except Exception as exc:
                logger.error(f"Error processing row {lead_row.id} for lender {lender}: {exc}")
                return {
                    'lead_row_id': lead_row.id,
                    'phone': lead_row.phone_number,
                    'lender': lender,
                    'result': {
                        'status': 'FAILED',
                        'result': 'PROCESSING_ERROR',
                        'message': str(exc)
                    }
                }
        
        # Build task list: (row, lender) pairs
        tasks = []
        for lead_row in lead_rows:
            for lender in lenders:
                tasks.append((lead_row, lender))
        
        # Process with thread pool
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(_process_single_row_lender, lead_row, lender): (lead_row.id, lender)
                for lead_row, lender in tasks
            }
            
            # Results mapping: {row_id: {lender_name: result}}
            row_results = {}
            
            for future in as_completed(futures):
                try:
                    proc_result = future.result()
                    lead_row_id = proc_result['lead_row_id']
                    lender = proc_result['lender']
                    result = proc_result['result']
                    
                    # Store result for this row/lender combo
                    if lead_row_id not in row_results:
                        row_results[lead_row_id] = {}
                    
                    row_results[lead_row_id][lender] = result
                    
                    if result.get('status') == 'SUCCESS':
                        success_count += 1
                    else:
                        failed_count += 1
                    
                    processed_count += 1
                    
                    # Update progress every BATCH_SIZE operations
                    if processed_count % (BATCH_SIZE * len(lenders)) == 0:
                        job.processed_rows = processed_count
                        job.current_batch = processed_count // (BATCH_SIZE * len(lenders))
                        job.success_count = success_count
                        job.failed_count = failed_count
                        job.save(update_fields=[
                            'processed_rows', 'current_batch', 'success_count',
                            'failed_count', 'updated_at'
                        ])
                
                except Exception as exc:
                    logger.error(f"Future processing error: {exc}")
                    failed_count += 1
        
        # Bulk update UploadedLeadRow records with results
        row_updates = []
        for lead_row_id, lender_results in row_results.items():
            lead_row = UploadedLeadRow.objects.get(pk=lead_row_id)
            lead_row.lender_results = lender_results
            lead_row.processing_status = UploadedLeadRow.STATUS_SUCCESS if any(
                r.get('status') == 'SUCCESS' for r in lender_results.values()
            ) else UploadedLeadRow.STATUS_FAILED
            lead_row.processed_at = datetime.now()
            row_updates.append(lead_row)
        
        # Bulk update
        if row_updates:
            UploadedLeadRow.objects.bulk_update(
                row_updates,
                ['lender_results', 'processing_status', 'processed_at'],
                batch_size=BATCH_SIZE
            )
        
        # Generate downloadable results CSV from staging table
        output_fd, output_path = tempfile.mkstemp(suffix='.csv', prefix='lead_results_')
        os.close(output_fd)
        
        results_list = []
        for lead_row in UploadedLeadRow.objects.filter(upload_job=job):
            for lender, result in (lead_row.lender_results or {}).items():
                results_list.append({
                    'phoneNumber': lead_row.phone_number,
                    'lender': lender,
                    'status': result.get('status', ''),
                    'result': result.get('result', ''),
                    'lead_id': result.get('lead_id', ''),
                    'utm_link': result.get('utm_link', ''),
                    'message': result.get('message', '')
                })
        
        # Write results CSV
        fieldnames = ['phoneNumber', 'lender', 'status', 'result', 'lead_id', 'utm_link', 'message']
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results_list)
        
        # Mark job as completed
        total_operations = total_rows * len(lenders)
        job.status = UploadJob.STATUS_COMPLETED
        job.processed_rows = processed_count
        job.success_count = success_count
        job.failed_count = failed_count
        job.result_file_path = output_path
        job.completed_at = datetime.now()
        job.save(update_fields=[
            'status', 'processed_rows', 'success_count', 'failed_count',
            'result_file_path', 'completed_at', 'updated_at'
        ])
        
        logger.info(f"Lead processing completed. job_id={job_id} success={success_count} failed={failed_count}")
        
        return {
            'ok': True,
            'total_rows': total_rows,
            'success_count': success_count,
            'failed_count': failed_count,
            'output_path': output_path
        }
    
    except Exception as exc:
        logger.exception(f"Lead processing task failed. job_id={job_id} err={exc}")
        job.status = UploadJob.STATUS_FAILED
        job.error_logs = str(exc)
        job.completed_at = datetime.now()
        job.save(update_fields=['status', 'error_logs', 'completed_at', 'updated_at'])
        raise


@shared_task
def test_task():
    import time
    for i in range(5):
        print(f"WORKING {i}")
        time.sleep(1)

    return "DONE"