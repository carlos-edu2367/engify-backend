from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation
from uuid import UUID


_PIX_GUI = "BR.GOV.BCB.PIX"
_DEFAULT_RECEIVER_NAME = "Engify Payments"
_DEFAULT_CITY = "GOIANIA"
_EMAIL_RE = re.compile(r"^[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}$", re.IGNORECASE)
_PHONE_RE = re.compile(r"^\+[1-9]\d{7,14}$")
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def generate_pix_copy_and_past(
    payment_code: str | None,
    amount: Decimal | str | None = None,
    receiver_name: str | None = None,
    city: str | None = None,
) -> str | None:
    if not payment_code:
        return None

    raw_code = payment_code.strip()
    if not raw_code:
        return None

    if is_pix_payload(raw_code):
        return raw_code

    pix_key = normalize_pix_key(raw_code)
    if not pix_key:
        return None

    merchant_name = _normalize_text(receiver_name or _DEFAULT_RECEIVER_NAME, max_len=25)
    merchant_city = _normalize_text(city or _DEFAULT_CITY, max_len=15)

    payload_parts = [
        _field("00", "01"),
        _field(
            "26",
            _field("00", _PIX_GUI) + _field("01", pix_key),
        ),
        _field("52", "0000"),
        _field("53", "986"),
    ]

    formatted_amount = _format_amount(amount)
    if formatted_amount:
        payload_parts.append(_field("54", formatted_amount))

    payload_parts.extend(
        [
            _field("58", "BR"),
            _field("59", merchant_name),
            _field("60", merchant_city),
            _field("62", _field("05", "***")),
        ]
    )

    payload_without_crc = "".join(payload_parts) + "6304"
    crc = _crc16_ccitt(payload_without_crc)
    return f"{payload_without_crc}{crc}"


def is_pix_payload(value: str | None) -> bool:
    if not value:
        return False
    normalized = re.sub(r"\s+", "", value)
    if len(normalized) < 36 or not normalized.startswith("000201"):
        return False
    if _PIX_GUI not in normalized.upper():
        return False
    body, received_crc = normalized[:-4], normalized[-4:]
    expected_crc = _crc16_ccitt(body)
    return received_crc.upper() == expected_crc


def normalize_pix_key(value: str | None) -> str | None:
    if not value:
        return None

    raw = value.strip()
    if not raw:
        return None

    if _EMAIL_RE.fullmatch(raw):
        return raw.lower()

    digits_only = re.sub(r"\D", "", raw)
    if _is_valid_cpf(digits_only) or _is_valid_cnpj(digits_only):
        return digits_only

    phone = _normalize_phone(raw)
    if phone:
        return phone

    try:
        return str(UUID(raw))
    except ValueError:
        pass

    if _UUID_RE.fullmatch(raw):
        return raw.lower()

    return None


def _normalize_phone(value: str) -> str | None:
    compact = re.sub(r"[^\d+]", "", value)
    if compact.startswith("00"):
        compact = f"+{compact[2:]}"
    elif compact.startswith("55") and not compact.startswith("+"):
        compact = f"+{compact}"
    elif compact.startswith("0") and not compact.startswith("+"):
        compact = f"+55{compact.lstrip('0')}"
    elif compact.startswith("+"):
        compact = f"+{re.sub(r'\D', '', compact[1:])}"
    else:
        digits = re.sub(r"\D", "", compact)
        if len(digits) in {10, 11}:
            compact = f"+55{digits}"
        else:
            compact = f"+{digits}" if digits else ""

    return compact if _PHONE_RE.fullmatch(compact) else None


def _normalize_text(value: str, max_len: int) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^A-Z0-9 /.-]", "", ascii_only.upper())
    compact = re.sub(r"\s+", " ", cleaned).strip()
    return (compact or "NA")[:max_len]


def _format_amount(amount: Decimal | str | None) -> str | None:
    if amount is None:
        return None
    try:
        decimal_amount = amount if isinstance(amount, Decimal) else Decimal(str(amount))
    except (InvalidOperation, ValueError):
        return None
    if decimal_amount <= 0:
        return None
    return f"{decimal_amount.quantize(Decimal('0.01'))}"


def _field(field_id: str, value: str) -> str:
    return f"{field_id}{len(value):02d}{value}"


def _crc16_ccitt(payload: str) -> str:
    crc = 0xFFFF
    for char in payload:
        crc ^= ord(char) << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1
            crc &= 0xFFFF
    return f"{crc:04X}"


def _is_valid_cpf(value: str) -> bool:
    if len(value) != 11 or value == value[0] * 11:
        return False
    total = sum(int(digit) * weight for digit, weight in zip(value[:9], range(10, 1, -1)))
    first_digit = (total * 10 % 11) % 10
    total = sum(int(digit) * weight for digit, weight in zip(value[:10], range(11, 1, -1)))
    second_digit = (total * 10 % 11) % 10
    return value[-2:] == f"{first_digit}{second_digit}"


def _is_valid_cnpj(value: str) -> bool:
    if len(value) != 14 or value == value[0] * 14:
        return False
    first_weights = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    second_weights = [6, *first_weights]
    first_total = sum(int(digit) * weight for digit, weight in zip(value[:12], first_weights))
    first_digit = 11 - (first_total % 11)
    first_digit = 0 if first_digit >= 10 else first_digit
    second_total = sum(int(digit) * weight for digit, weight in zip(value[:13], second_weights))
    second_digit = 11 - (second_total % 11)
    second_digit = 0 if second_digit >= 10 else second_digit
    return value[-2:] == f"{first_digit}{second_digit}"
