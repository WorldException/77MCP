# -*- coding: utf-8 -*-
"""Tests for 1C 7.7 SQL/DBF name derivation."""

from __future__ import annotations

from mcp_1c77 import sql_naming


def test_catalog_table():
    assert sql_naming.catalog_table("19") == "SC19"


def test_document_header_and_tabular_tables():
    assert sql_naming.document_header_table("1582") == "DH1582"
    assert sql_naming.document_tabular_table("1582") == "DT1582"


def test_register_totals_and_movements_tables():
    assert sql_naming.register_totals_table("105") == "RG105"
    assert sql_naming.register_movements_table("105") == "RA105"


def test_attribute_field():
    assert sql_naming.attribute_field("45") == "SP45"


def test_constant_field():
    assert sql_naming.constant_field("3") == "CN3"


def test_system_field_maps_are_populated():
    assert sql_naming.CATALOG_SQL_SYSTEM_FIELDS["Код"] == "CODE"
    assert sql_naming.DOCUMENT_SQL_SYSTEM_FIELDS["НомерДок"] == "DOCNO"
