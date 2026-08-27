"""Derivation of 1C:Enterprise 7.7 SQL/DBF table and field names from internal IDs.

1C 7.7 does not store these names anywhere in 1Cv7.MD — the platform derives
them deterministically from the internal decimal object/attribute ID at
runtime. The prefixes below follow the well-known (community-documented, not
officially published) 1C 7.7 DBF/MS SQL naming convention. Callers should
present these as a convention, not a guaranteed fact.
"""

from __future__ import annotations

NOTE = "по соглашению именования 1С 7.7 (DBF/MS SQL)"

CATALOG_SQL_SYSTEM_FIELDS: dict[str, str] = {
    "Код": "CODE",
    "Наименование": "DESCR",
    "ПометкаУдаления": "ISMARK",
    "Родитель": "PARENTID",
    "Владелец": "PARENTEXT",
}

DOCUMENT_SQL_SYSTEM_FIELDS: dict[str, str] = {
    "НомерДок": "DOCNO",
    "ДатаДок": "DATE_TIME_IDDOC",
}


def catalog_table(obj_id: str) -> str:
    """SQL table name for a catalog (Справочник)."""
    return f"SC{obj_id}"


def document_header_table(obj_id: str) -> str:
    """SQL table name for a document header (шапка документа)."""
    return f"DH{obj_id}"


def document_tabular_table(obj_id: str) -> str:
    """SQL table name for a document tabular section (табличная часть)."""
    return f"DT{obj_id}"


def register_totals_table(obj_id: str) -> str:
    """SQL table name for register totals (итоги регистра)."""
    return f"RG{obj_id}"


def register_movements_table(obj_id: str) -> str:
    """SQL table name for register movements (движения регистра)."""
    return f"RA{obj_id}"


def attribute_field(attr_id: str) -> str:
    """SQL field name for a regular attribute/dimension/resource."""
    return f"SP{attr_id}"


def constant_field(const_id: str) -> str:
    """SQL field name for a constant, stored in the shared _1SCONST table."""
    return f"CN{const_id}"
