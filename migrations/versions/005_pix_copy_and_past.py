"""add pix copy and paste payload to pagamentos_agendados

Revision ID: 005
Revises: 004
Create Date: 2026-04-11
"""
from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation
from typing import Sequence, Union
from uuid import UUID

import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql import table, column


revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_PIX_GUI = "BR.GOV.BCB.PIX"
_EMAIL_RE = re.compile(r"^[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}$", re.IGNORECASE)
_PHONE_RE = re.compile(r"^\+[1-9]\d{7,14}$")


def upgrade() -> None:
    op.alter_column(
        "pagamentos_agendados",
        "payment_cod",
        existing_type=sa.String(length=100),
        type_=sa.Text(),
        existing_nullable=True,
    )
    op.add_column(
        "pagamentos_agendados",
        sa.Column("pix_copy_and_past", sa.Text(), nullable=True),
    )

    conn = op.get_bind()
    pagamentos = table(
        "pagamentos_agendados",
        column("id", sa.UUID()),
        column("payment_cod", sa.Text()),
        column("valor_amount", sa.Numeric()),
        column("diarist_id", sa.UUID()),
    )
    diarists = table(
        "diarists",
        column("id", sa.UUID()),
        column("nome", sa.String()),
    )

    rows = conn.execute(
        sa.select(
            pagamentos.c.id,
            pagamentos.c.payment_cod,
            pagamentos.c.valor_amount,
            pagamentos.c.diarist_id,
            diarists.c.nome,
        ).select_from(
            pagamentos.outerjoin(diarists, pagamentos.c.diarist_id == diarists.c.id)
        )
    ).fetchall()

    for row in rows:
        pix_copy_and_past = _generate_pix_copy_and_past(
            payment_code=row.payment_cod,
            amount=row.valor_amount,
            receiver_name=row.nome or "Engify Payments",
            city="GOIANIA",
        )
        if not pix_copy_and_past:
            continue
        conn.execute(
            sa.text(
                """
                UPDATE pagamentos_agendados
                SET pix_copy_and_past = :pix_copy_and_past
                WHERE id = :payment_id
                """
            ),
            {
                "payment_id": row.id,
                "pix_copy_and_past": pix_copy_and_past,
            },
        )


def downgrade() -> None:
    op.drop_column("pagamentos_agendados", "pix_copy_and_past")
    op.alter_column(
        "pagamentos_agendados",
        "payment_cod",
        existing_type=sa.Text(),
        type_=sa.String(length=100),
        existing_nullable=True,
    )


def _generate_pix_copy_and_past(
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

    if _is_pix_payload(raw_code):
        return raw_code

    pix_key = _normalize_pix_key(raw_code)
    if not pix_key:
        return None

    merchant_name = _normalize_text(receiver_name or "Engify Payments", max_len=25)
    merchant_city = _normalize_text(city or "GOIANIA", max_len=15)
    payload_parts = [
        _field("00", "01"),
        _field("26", _field("00", _PIX_GUI) + _field("01", pix_key)),
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
    return f"{payload_without_crc}{_crc16_ccitt(payload_without_crc)}"


def _is_pix_payload(value: str) -> bool:
    normalized = re.sub(r"\s+", "", value)
    if len(normalized) < 36 or not normalized.startswith("000201"):
        return False
    if _PIX_GUI not in normalized.upper():
        return False
    return normalized[-4:].upper() == _crc16_ccitt(normalized[:-4])


def _normalize_pix_key(value: str) -> str | None:
    if _EMAIL_RE.fullmatch(value):
        return value.lower()
    digits_only = re.sub(r"\D", "", value)
    if _is_valid_cpf(digits_only) or _is_valid_cnpj(digits_only):
        return digits_only
    phone = _normalize_phone(value)
    if phone:
        return phone
    try:
        return str(UUID(value))
    except ValueError:
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
