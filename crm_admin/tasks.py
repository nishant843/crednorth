import csv
import logging
from datetime import datetime
from contextlib import contextmanager

from celery import shared_task
from django.core.validators import validate_email
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models.signals import post_save

from crm_admin.models import UploadJob
from users.models import User


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
