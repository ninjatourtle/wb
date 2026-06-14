import hashlib
import json
import logging
import os
from datetime import datetime
from decimal import Decimal, InvalidOperation
from urllib.request import Request, urlopen

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import AuditEvent, ImportedTender, Tender, TenderImportSource


logger = logging.getLogger(__name__)

DEFAULT_FIELDS = {
    "external_id": "id",
    "number": "number",
    "title": "title",
    "category": "category",
    "description": "description",
    "requirements": "requirements",
    "delivery_address": "delivery_address",
    "budget": "budget",
    "deadline": "deadline",
    "procedure": "procedure",
    "auction_step": "auction_step",
    "status": "status",
    "external_url": "url",
}

DEFAULT_STATUS_MAPPING = {
    "draft": Tender.Status.DRAFT,
    "approval": Tender.Status.APPROVAL,
    "published": Tender.Status.PUBLISHED,
    "active": Tender.Status.PUBLISHED,
    "open": Tender.Status.PUBLISHED,
    "review": Tender.Status.REVIEW,
    "completed": Tender.Status.COMPLETED,
    "closed": Tender.Status.COMPLETED,
    "cancelled": Tender.Status.CANCELLED,
    "canceled": Tender.Status.CANCELLED,
}


class TenderImportError(Exception):
    pass


def value_at(data, path, default=None):
    if not path:
        return data
    value = data
    for part in path.split("."):
        if isinstance(value, dict):
            value = value.get(part, default)
        else:
            return default
    return value


def fetch_source_items(source):
    headers = {"Accept": "application/json", "User-Agent": "TenderFlow/1.0"}
    if source.auth_header and source.auth_env_var:
        token = os.getenv(source.auth_env_var)
        if not token:
            raise TenderImportError(f"Не задана переменная окружения {source.auth_env_var}")
        headers[source.auth_header] = token
    request = Request(source.url, headers=headers)
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise TenderImportError(f"Не удалось получить данные: {exc}") from exc

    items = value_at(payload, source.items_path) if source.items_path else payload
    if isinstance(items, dict):
        items = items.get("items") or items.get("results") or items.get("data")
    if not isinstance(items, list):
        raise TenderImportError("Ответ источника не содержит список тендеров")
    return items


def normalize_datetime(value):
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str):
        result = parse_datetime(value)
    else:
        result = None
    if result is None:
        raise TenderImportError(f"Некорректный deadline: {value!r}")
    if timezone.is_naive(result):
        result = timezone.make_aware(result)
    return result


def normalize_decimal(value, field_name):
    try:
        return Decimal(str(value or 0))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise TenderImportError(f"Некорректное поле {field_name}: {value!r}") from exc


def normalize_choice(value, choices, fallback):
    allowed = {choice for choice, _ in choices}
    return value if value in allowed else fallback


def normalize_item(source, item):
    mapping = {**DEFAULT_FIELDS, **source.field_mapping}
    get = lambda name, default=None: value_at(item, mapping[name], default)
    external_id = str(get("external_id") or get("number") or "").strip()
    number = str(get("number") or external_id).strip()
    title = str(get("title") or "").strip()
    if not external_id or not number or not title:
        raise TenderImportError("У тендера обязательны external_id, number и title")

    raw_status = str(get("status", Tender.Status.PUBLISHED)).lower().strip()
    status_mapping = {**DEFAULT_STATUS_MAPPING, **source.status_mapping}
    status = status_mapping.get(raw_status, Tender.Status.PUBLISHED)
    status = normalize_choice(status, Tender.Status.choices, Tender.Status.PUBLISHED)

    return {
        "external_id": external_id,
        "external_url": str(get("external_url") or "")[:500],
        "tender": {
            "number": number[:40],
            "title": title[:250],
            "category": normalize_choice(
                str(get("category", Tender.Category.OTHER)).lower(),
                Tender.Category.choices,
                Tender.Category.OTHER,
            ),
            "description": str(get("description") or ""),
            "requirements": str(get("requirements") or ""),
            "delivery_address": str(get("delivery_address") or "Не указан")[:300],
            "budget": normalize_decimal(get("budget"), "budget"),
            "deadline": normalize_datetime(get("deadline")),
            "procedure": normalize_choice(
                str(get("procedure", Tender.Procedure.CLOSED)).lower(),
                Tender.Procedure.choices,
                Tender.Procedure.CLOSED,
            ),
            "auction_step": (
                normalize_decimal(get("auction_step"), "auction_step")
                if get("auction_step") not in (None, "")
                else None
            ),
            "status": status,
        },
    }


def payload_hash(item):
    serialized = json.dumps(item, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


@transaction.atomic
def sync_item(source, item):
    normalized = normalize_item(source, item)
    external_id = normalized["external_id"]
    defaults = normalized["tender"]
    record = ImportedTender.objects.select_related("tender").filter(
        source=source, external_id=external_id
    ).first()

    created = False
    if record:
        tender = record.tender
    else:
        tender = Tender.objects.filter(
            organization=source.organization, number=defaults["number"]
        ).first()
        if tender and not hasattr(tender, "import_record"):
            raise TenderImportError(
                f"Номер {defaults['number']} уже используется тендером, созданным вручную"
            )
        if not tender:
            tender = Tender.objects.create(
                owner=source.owner, organization=source.organization, **defaults
            )
            created = True
        record = ImportedTender(source=source, external_id=external_id, tender=tender)

    changed_fields = []
    for field, value in defaults.items():
        if getattr(tender, field) != value:
            setattr(tender, field, value)
            changed_fields.append(field)
    if changed_fields:
        tender.save(update_fields=[*changed_fields, "updated_at"])

    now = timezone.now()
    current_hash = payload_hash(item)
    changed = created or record.payload_hash != current_hash or bool(changed_fields)
    record.external_url = normalized["external_url"]
    record.payload_hash = current_hash
    record.raw_data = item
    record.last_seen_at = now
    if changed:
        record.last_changed_at = now
    record.save()

    if created or changed_fields:
        AuditEvent.objects.create(
            user=source.owner,
            organization=source.organization,
            action="tender_import_created" if created else "tender_import_updated",
            object_type="Tender",
            object_id=str(tender.pk),
            details={"source": source.name, "external_id": external_id, "fields": changed_fields},
        )
    return "created" if created else "updated" if changed else "unchanged"


def sync_source(source):
    result = {"created": 0, "updated": 0, "unchanged": 0, "failed": 0, "cancelled": 0}
    seen_ids = set()
    for item in fetch_source_items(source):
        try:
            external_id = normalize_item(source, item)["external_id"]
            seen_ids.add(external_id)
            result[sync_item(source, item)] += 1
        except Exception:
            result["failed"] += 1
            logger.exception("Failed to import tender from %s", source.name)

    if source.cancel_missing and seen_ids:
        missing = source.imported_tenders.exclude(external_id__in=seen_ids).exclude(
            tender__status__in=[Tender.Status.COMPLETED, Tender.Status.CANCELLED]
        )
        for record in missing.select_related("tender"):
            record.tender.status = Tender.Status.CANCELLED
            record.tender.save(update_fields=["status", "updated_at"])
            AuditEvent.objects.create(
                user=source.owner,
                organization=source.organization,
                action="tender_import_cancelled",
                object_type="Tender",
                object_id=str(record.tender_id),
                details={"source": source.name, "external_id": record.external_id},
            )
            result["cancelled"] += 1

    source.last_synced_at = timezone.now()
    source.last_error = (
        f"Не удалось обработать тендеров: {result['failed']}" if result["failed"] else ""
    )
    source.save(update_fields=["last_synced_at", "last_error"])
    return result


def sync_active_sources():
    results = {}
    for source in TenderImportSource.objects.filter(is_active=True):
        try:
            results[source.name] = sync_source(source)
        except Exception as exc:
            source.last_error = str(exc)
            source.last_synced_at = timezone.now()
            source.save(update_fields=["last_error", "last_synced_at"])
            logger.exception("Failed to sync tender source %s", source.name)
            results[source.name] = {"error": str(exc)}
    return results
