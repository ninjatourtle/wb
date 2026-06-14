import hashlib
import json
import logging
import os
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from html import unescape
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.html import strip_tags

from .models import AuditEvent, ImportedTender, Tender, TenderImportSource, TenderLot


logger = logging.getLogger(__name__)
BIDZAAR_DETAIL_VERSION = 2

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
    if source.adapter == TenderImportSource.Adapter.BIDZAAR:
        return fetch_bidzaar_items(source)

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


def fetch_json(url, headers=None):
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "TenderFlow/1.0",
            **(headers or {}),
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise TenderImportError(f"Не удалось получить данные: {exc}") from exc


def fetch_optional_json(url, default):
    try:
        return fetch_json(url)
    except TenderImportError:
        logger.warning("Optional Bidzaar endpoint is unavailable: %s", url)
        return default


def bidzaar_category(title):
    value = title.lower()
    if any(word in value for word in ("монтаж", "ремонт", "строитель", "устройств", "работ")):
        return Tender.Category.CONSTRUCTION
    if any(word in value for word in ("обслужив", "услуг", "утилизац", "перевоз", "аренд")):
        return Tender.Category.SERVICES
    if any(word in value for word in ("сервер", "программ", "информац", "связ", "телеком")):
        return Tender.Category.IT
    return Tender.Category.GOODS


def bidzaar_address(addresses):
    values = []
    for address in addresses or []:
        structured = ", ".join(
            filter(
                None,
                (
                    address.get("country"),
                    address.get("region"),
                    address.get("area"),
                    address.get("city"),
                    address.get("building"),
                ),
            )
        )
        value = address.get("comment") or structured or address.get("search")
        if value:
            values.append(value)
    return "; ".join(values) or "Не указан"


def transform_bidzaar_item(item, origin):
    external_id = str(item["id"])
    title = str(item.get("name") or item.get("number") or external_id)
    status = {
        1: Tender.Status.PUBLISHED,
        2: Tender.Status.REVIEW,
        3: Tender.Status.COMPLETED,
        8: Tender.Status.PUBLISHED,
    }.get(item.get("status"), Tender.Status.PUBLISHED)
    deadline = item.get("acceptanceEndDate") or item.get("finishDate") or item.get("publishDate")
    published = item.get("publishDate") or "не указана"
    result = {
        "id": external_id,
        "number": item.get("number") or external_id,
        "title": title,
        "category": bidzaar_category(title),
        "description": (
            f"Закупка компании {item.get('companyName') or 'ВАЙЛДБЕРРИЗ'}, "
            f"опубликована на Bidzaar {published}."
        ),
        "requirements": "Условия участия и документы доступны в оригинальной закупке на Bidzaar.",
        "delivery_address": bidzaar_address(item.get("deliveryAddresses")),
        "budget": "0",
        "deadline": deadline,
        "procedure": Tender.Procedure.CLOSED,
        "status": status,
        "url": f"{origin}/app/process/light/{external_id}",
        "bidzaar": item,
    }
    result["_listing_hash"] = payload_hash(result)
    return result


def plain_text(value):
    html = re.sub(r"</(?:p|div|li|h[1-6])\s*>", "\n", str(value or ""), flags=re.I)
    return unescape(strip_tags(html)).strip()


def bidzaar_detail_urls(origin, external_id, version_id=None, request_id=None):
    base = f"{origin}/api/process/light/procedures"
    urls = {"main": f"{base}/read/{external_id}/main-view"}
    if version_id:
        version_base = f"{base}/read/{external_id}/versions/{version_id}"
        urls.update({
            "positions": f"{version_base}/positions",
            "groups": f"{version_base}/groups",
        })
    if request_id:
        urls["questionnaire"] = f"{origin}/api/questionnairenew/requests/{request_id}"
    return urls


def fetch_bidzaar_details(item):
    origin = item["url"].split("/app/process/light/", 1)[0]
    main = fetch_json(bidzaar_detail_urls(origin, item["id"])["main"])
    version = main.get("versionInformation") or {}
    urls = bidzaar_detail_urls(origin, item["id"], version.get("id"), version.get("requestId"))
    positions = fetch_optional_json(urls["positions"], []) if urls.get("positions") else []
    groups = fetch_optional_json(urls["groups"], []) if urls.get("groups") else []
    questionnaire = (
        fetch_optional_json(urls["questionnaire"], {"groups": []})
        if urls.get("questionnaire")
        else {"groups": []}
    )
    general = main.get("generalInformation") or {}
    parameters = main.get("parameters") or {}
    criteria = [
        {
            "id": criterion.get("id"),
            "group": group.get("name") or "Неценовые критерии",
            "title": criterion.get("text") or "Критерий",
            "comment": criterion.get("comment") or "",
            "type": criterion.get("type") or "",
            "required": bool(criterion.get("required")),
            "options": [
                option.get("value")
                for option in (criterion.get("dataSource") or {}).get("items", [])
                if option.get("value")
            ],
        }
        for group in questionnaire.get("groups", [])
        for criterion in group.get("items", [])
    ]
    documents = [
        {
            "id": document.get("id"),
            "title": document.get("name") or document.get("originalName") or "Документ",
            "extension": document.get("extension") or "",
            "size": document.get("length") or 0,
            "url": f"{origin}/api/filestorage/files/download/{document.get('fileId')}",
        }
        for document in general.get("files", [])
        if document.get("fileId")
    ]
    rules = [
        {"label": "Вид запроса", "value": "Открытый" if parameters.get("openType") == 0 else "Закрытый"},
        {"label": "Валюта запроса", "value": parameters.get("currency") or "RUB"},
        {
            "label": "После подачи предложения участники видят",
            "value": "Только свое предложение"
            if parameters.get("otherParticipantsVisibility") == 0
            else "Предложения других участников",
        },
        {
            "label": "Альтернативных предложений",
            "value": str(parameters.get("maxAlternativeProposalCount") or 0),
        },
        {
            "label": "Напоминание о завершении приема",
            "value": f"за {parameters.get('acceptanceEndNotificationHours')} ч"
            if parameters.get("acceptanceEndNotificationHours")
            else "Не задано",
        },
        {
            "label": "Ориентировочный срок подведения итогов",
            "value": f"{parameters.get('approximateDeadlineForSummingUp')} календ. дн."
            if parameters.get("approximateDeadlineForSummingUp")
            else "Не задано",
        },
    ]
    if groups:
        rules.extend([
            {
                "label": "Изменение цены",
                "value": "Можно повышать и понижать"
                if any(group.get("params", {}).get("permitUpDown") for group in groups)
                else "Только понижение",
            },
            {
                "label": "Минимальный шаг изменения цены",
                "value": f"{groups[0].get('params', {}).get('reductionStep') or 0} %",
            },
        ])
    return {
        "schema_version": BIDZAAR_DETAIL_VERSION,
        "main": main,
        "positions": positions,
        "groups": groups,
        "criteria": criteria,
        "documents": documents,
        "parameters": parameters,
        "rules": rules,
    }


def enrich_bidzaar_item(item, existing=None):
    existing = existing or {}
    if (
        existing.get("_listing_hash") == item.get("_listing_hash")
        and existing.get("details", {}).get("schema_version") == BIDZAAR_DETAIL_VERSION
    ):
        item.update({
            "description": existing.get("description", item["description"]),
            "requirements": existing.get("requirements", item["requirements"]),
            "delivery_address": existing.get("delivery_address", item["delivery_address"]),
            "budget": existing.get("budget", item["budget"]),
            "procedure": existing.get("procedure", item["procedure"]),
            "details": existing["details"],
        })
        return item
    if item.get("status") == Tender.Status.COMPLETED and not existing.get("details"):
        return item

    details = fetch_bidzaar_details(item)
    general = details["main"].get("generalInformation") or {}
    parameters = details["parameters"]
    description = plain_text(general.get("description"))
    criteria_text = "\n\n".join(
        filter(
            None,
            (
                f"{criterion['title']}\n{criterion['comment']}".strip()
                for criterion in details["criteria"]
            ),
        )
    )
    item.update({
        "description": description or item["description"],
        "requirements": criteria_text or item["requirements"],
        "delivery_address": bidzaar_address(general.get("deliveryAddresses")) or item["delivery_address"],
        "budget": str(sum(Decimal(str(group.get("params", {}).get("expectedPrice") or 0)) for group in details["groups"])),
        "procedure": Tender.Procedure.AUCTION if any(
            group.get("params", {}).get("permitUpDown") for group in details["groups"]
        ) else Tender.Procedure.CLOSED,
        "details": details,
    })
    if parameters.get("acceptanceEndDate"):
        item["deadline"] = parameters["acceptanceEndDate"]
    return item


def fetch_bidzaar_items(source):
    parts = urlsplit(source.url)
    origin = f"{parts.scheme}://{parts.netloc}"
    params = [(key, value) for key, value in parse_qsl(parts.query) if key != "id"]
    filter_indexes = [
        int(key.split("[", 1)[1].split("]", 1)[0])
        for key, _ in params
        if key.startswith("filters[") and "]." in key
    ]
    if not any(key.endswith(".field") and value == "procedureType" for key, value in params):
        index = max(filter_indexes, default=-1) + 1
        params.extend([
            (f"filters[{index}].operator", "eq"),
            (f"filters[{index}].field", "procedureType"),
            (f"filters[{index}].value", "1"),
        ])
    params = [
        (key, value)
        for key, value in params
        if key not in {"paging.page", "paging.size"}
    ]
    api_url = urlunsplit((parts.scheme, parts.netloc, "/api/process/light/procedures/available", "", ""))
    page = 1
    page_size = 100
    items = []
    while True:
        query = urlencode([*params, ("paging.page", page), ("paging.size", page_size)])
        payload = fetch_json(f"{api_url}?{query}")
        page_items = payload.get("items", [])
        items.extend(transform_bidzaar_item(item, origin) for item in page_items)
        total = int(payload.get("totalCount", len(items)))
        if not page_items or len(items) >= total:
            break
        page += 1
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
    if source.adapter == TenderImportSource.Adapter.BIDZAAR:
        item = enrich_bidzaar_item(item, record.raw_data if record else None)
        normalized = normalize_item(source, item)
        defaults = normalized["tender"]

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

    if source.adapter == TenderImportSource.Adapter.BIDZAAR and item.get("details"):
        sync_bidzaar_lots(tender, item["details"])

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


def sync_bidzaar_lots(tender, details):
    positions = details.get("positions", [])
    seen = []
    for index, position in enumerate(positions, start=1):
        external_id = str(position.get("id") or "")
        if not external_id:
            continue
        seen.append(external_id)
        TenderLot.objects.update_or_create(
            tender=tender,
            external_id=external_id,
            defaults={
                "title": position.get("name") or f"Позиция {index}",
                "description": position.get("description") or "",
                "quantity": normalize_decimal(position.get("count") or 1, "quantity"),
                "unit": position.get("unit") or "шт.",
                "budget": normalize_decimal(
                    position.get("startPrice") or position.get("price") or 0, "budget"
                ),
            },
        )
    TenderLot.objects.filter(tender=tender).exclude(external_id="").exclude(
        external_id__in=seen
    ).delete()


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
