import csv
import os
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from users.models import User


HEADER_ALIASES = {
    'phone_number': ['phone_number', 'phone', 'mobile', 'mobile_number', 'contact', 'contact_number'],
    'first_name': ['first_name', 'firstname', 'first', 'given_name'],
    'last_name': ['last_name', 'lastname', 'surname', 'last', 'family_name'],
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


def normalize_header(header):
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


def build_header_lookup(fieldnames):
    lookup = {}
    for field in fieldnames or []:
        normalized = normalize_header(field)
        if normalized and normalized not in lookup:
            lookup[normalized] = field
    return lookup


def get_value(row, header_lookup, canonical_key):
    aliases = HEADER_ALIASES.get(canonical_key, [canonical_key])
    for alias in aliases:
        source = header_lookup.get(alias)
        if source is not None:
            return (row.get(source) or '').strip()
    return ''


def parse_date(raw):
    if not raw:
        return None
    for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%Y/%m/%d'):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def valid_pan(raw_pan):
    pan = (raw_pan or '').strip().upper()
    if len(pan) != 10:
        return ''
    if not (pan[:5].isalpha() and pan[5:9].isdigit() and pan[9].isalpha()):
        return ''
    if pan[3] not in PAN_FOURTH_ALLOWED:
        return ''
    return pan


def valid_pin(raw_pin):
    pin = (raw_pin or '').strip()
    if pin.isdigit() and len(pin) == 6:
        return pin
    return ''


def valid_gender(raw_gender):
    if not raw_gender:
        return ''
    mapped = GENDER_MAP.get(raw_gender.strip().lower(), raw_gender.strip())
    return mapped if mapped in VALID_GENDERS else ''


def valid_profession(raw_profession):
    if not raw_profession:
        return ''
    mapped = PROFESSION_MAP.get(raw_profession.strip().lower(), raw_profession.strip())
    return mapped if mapped in VALID_PROFESSIONS else ''


def valid_income(raw_income):
    if not raw_income:
        return None
    try:
        return float(raw_income)
    except (TypeError, ValueError):
        return None


def valid_bureau(raw_score):
    if not raw_score:
        return None
    try:
        score = int(raw_score)
    except (TypeError, ValueError):
        return None
    return score if 0 <= score <= 900 else None


def row_to_user(row, header_lookup):
    phone = get_value(row, header_lookup, 'phone_number')
    phone = ''.join(ch for ch in phone if ch.isdigit())
    if len(phone) != 10:
        raise ValueError('Invalid or missing phone number')

    first_name = get_value(row, header_lookup, 'first_name')
    last_name = get_value(row, header_lookup, 'last_name')
    if not first_name and not last_name:
        full_name = get_value(row, header_lookup, 'name')
        if full_name:
            parts = full_name.split(None, 1)
            first_name = parts[0]
            if len(parts) > 1:
                last_name = parts[1]

    return User(
        phone_number=phone,
        first_name=first_name,
        last_name=last_name,
        email=get_value(row, header_lookup, 'email'),
        pan_number=valid_pan(get_value(row, header_lookup, 'pan_number')),
        date_of_birth=parse_date(get_value(row, header_lookup, 'date_of_birth')),
        gender=valid_gender(get_value(row, header_lookup, 'gender')),
        city=get_value(row, header_lookup, 'city'),
        state=get_value(row, header_lookup, 'state'),
        pin_code=valid_pin(get_value(row, header_lookup, 'pin_code')),
        profession=valid_profession(get_value(row, header_lookup, 'profession')),
        monthly_income=valid_income(get_value(row, header_lookup, 'monthly_income')),
        bureau_score=valid_bureau(get_value(row, header_lookup, 'bureau_score')),
        status='pending',
    )


class Command(BaseCommand):
    help = 'Import leads from CSV into users_user using memory-safe batched bulk inserts.'

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, help='Path to input CSV file')
        parser.add_argument('--batch-size', type=int, default=500, help='Bulk insert batch size (default: 500)')
        parser.add_argument('--progress-every', type=int, default=5000, help='Print progress every N rows (default: 5000)')
        parser.add_argument('--dry-run', action='store_true', help='Validate and parse rows without writing to DB')
        parser.add_argument(
            '--error-csv',
            type=str,
            default='',
            help='Optional output path for skipped-row CSV. If omitted, a timestamped file is created in current directory.',
        )

    def handle(self, *args, **options):
        file_path = options['file_path']
        batch_size = max(1, min(options['batch_size'], 1000))
        progress_every = max(1, options['progress_every'])
        dry_run = options['dry_run']
        error_csv_path = options['error_csv'].strip()

        if not error_csv_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            error_csv_path = f'import_leads_errors_{timestamp}.csv'

        self.stdout.write(self.style.WARNING('Starting CSV import...'))
        self.stdout.write(f'File: {file_path}')
        self.stdout.write(f'Batch size: {batch_size}')
        self.stdout.write(f'Dry run: {dry_run}')

        total_rows = 0
        skipped_rows = 0
        batch_failures = 0
        inserted_rows = 0

        batch = []
        error_file = None
        error_writer = None

        try:
            error_file = open(error_csv_path, 'w', encoding='utf-8', newline='')
            error_writer = csv.writer(error_file)
            error_writer.writerow(['row_number', 'reason', 'raw_row'])

            with open(file_path, 'r', encoding='utf-8-sig', newline='') as csv_file:
                reader = csv.DictReader(csv_file)
                header_lookup = build_header_lookup(reader.fieldnames)

                phone_aliases = HEADER_ALIASES['phone_number']
                if not any(alias in header_lookup for alias in phone_aliases):
                    raise CommandError('Missing required phone column. Accepted: phone_number, phone, mobile')

                for row in reader:
                    total_rows += 1

                    try:
                        user_obj = row_to_user(row, header_lookup)
                        batch.append(user_obj)
                    except Exception as row_exc:
                        skipped_rows += 1
                        if error_writer is not None:
                            error_writer.writerow([total_rows, str(row_exc), repr(row)])
                        if skipped_rows <= 20:
                            self.stderr.write(f'Row {total_rows}: skipped ({row_exc})')

                    if len(batch) >= batch_size:
                        ok, created = self._flush_batch(batch, batch_size, dry_run)
                        if ok:
                            inserted_rows += created
                        else:
                            batch_failures += 1

                    if total_rows % progress_every == 0:
                        self.stdout.write(
                            f'Processed {total_rows} rows | Inserted {inserted_rows} | Skipped {skipped_rows} | Batch failures {batch_failures}'
                        )

                if batch:
                    ok, created = self._flush_batch(batch, batch_size, dry_run)
                    if ok:
                        inserted_rows += created
                    else:
                        batch_failures += 1

        except FileNotFoundError:
            raise CommandError(f'File not found: {file_path}')
        except UnicodeDecodeError:
            raise CommandError('Failed to decode CSV. Ensure UTF-8/UTF-8-SIG encoding.')
        finally:
            if error_file is not None:
                error_file.close()

            # Remove empty error file when there were no skipped rows.
            if skipped_rows == 0 and os.path.exists(error_csv_path):
                os.remove(error_csv_path)

        self.stdout.write(self.style.SUCCESS('Import finished.'))
        self.stdout.write(f'Total rows read: {total_rows}')
        self.stdout.write(f'Inserted rows: {inserted_rows}')
        self.stdout.write(f'Skipped rows: {skipped_rows}')
        self.stdout.write(f'Batch failures: {batch_failures}')
        if skipped_rows > 0:
            self.stdout.write(f'Skipped row details CSV: {error_csv_path}')

    def _flush_batch(self, batch, batch_size, dry_run):
        if not batch:
            return True, 0

        try:
            if dry_run:
                return True, len(batch)

            phones = [obj.phone_number for obj in batch if obj.phone_number]
            existing = set(
                User.objects.filter(phone_number__in=phones).values_list('phone_number', flat=True)
            )
            to_insert = [obj for obj in batch if obj.phone_number not in existing]

            if to_insert:
                with transaction.atomic():
                    User.objects.bulk_create(to_insert, batch_size=batch_size, ignore_conflicts=True)

            return True, len(to_insert)
        except Exception as exc:
            self.stderr.write(self.style.WARNING(f'Batch insert failed and was skipped: {exc}'))
            return False, 0
        finally:
            batch.clear()
