# -*- coding: utf-8 -*-
"""Tests for the lightweight BSL module structure parser."""

from __future__ import annotations

from mcp_1c77.bsl_parser import parse_module_structure

_SAMPLE_MODULE_EN = """\
Var gTrade;
Var gVersion Export;

Procedure Start(Param1, Param2)
    Var Local1;
    gTrade = 1;
EndProcedure

Function GetVersion() Export
    Return gVersion;
EndFunction
"""

_SAMPLE_MODULE_RU = """\
Перем мОрг;
Перем мДата, мСумма Экспорт;

Процедура Инициализация()
    мОрг = "Тест";
КонецПроцедуры

Функция ПолучитьСумму(Знач Параметр) Экспорт
    Возврат мСумма;
КонецФункции
"""


class TestParseModuleStructureEnglish:
    def test_module_level_variables(self):
        structure = parse_module_structure(_SAMPLE_MODULE_EN)
        names = [v.name for v in structure.variables]
        assert names == ["gTrade", "gVersion"]
        assert structure.variables[0].exported is False
        assert structure.variables[1].exported is True

    def test_local_variable_excluded(self):
        structure = parse_module_structure(_SAMPLE_MODULE_EN)
        names = [v.name for v in structure.variables]
        assert "Local1" not in names

    def test_procedures_and_functions(self):
        structure = parse_module_structure(_SAMPLE_MODULE_EN)
        assert len(structure.procedures) == 2

        proc = structure.procedures[0]
        assert proc.kind == "Процедура"
        assert proc.name == "Start"
        assert proc.params == ["Param1", "Param2"]
        assert proc.exported is False
        assert proc.start_line == 4
        assert proc.end_line == 7

        func = structure.procedures[1]
        assert func.kind == "Функция"
        assert func.name == "GetVersion"
        assert func.params == []
        assert func.exported is True


class TestParseModuleStructureRussian:
    def test_module_level_variables(self):
        structure = parse_module_structure(_SAMPLE_MODULE_RU)
        names = [v.name for v in structure.variables]
        assert names == ["мОрг", "мДата", "мСумма"]
        assert structure.variables[2].exported is True

    def test_procedures_and_functions(self):
        structure = parse_module_structure(_SAMPLE_MODULE_RU)
        assert len(structure.procedures) == 2
        assert structure.procedures[0].name == "Инициализация"
        assert structure.procedures[1].name == "ПолучитьСумму"
        assert structure.procedures[1].params == ["Знач Параметр"]
        assert structure.procedures[1].exported is True


_SAMPLE_MODULE_FORWARD_DECL = """\
Процедура Первая() Экспорт Далее
Функция Вторая(X) Далее

Функция Вторая(X)
    Возврат X;
КонецФункции

Процедура Первая() Экспорт
    X = 1;
КонецПроцедуры
"""


class TestParseModuleStructureForwardDeclarations:
    def test_forward_declarations_are_skipped(self):
        structure = parse_module_structure(_SAMPLE_MODULE_FORWARD_DECL)
        names = [p.name for p in structure.procedures]
        assert names == ["Вторая", "Первая"]

    def test_real_definitions_have_correct_ranges(self):
        structure = parse_module_structure(_SAMPLE_MODULE_FORWARD_DECL)
        by_name = {p.name: p for p in structure.procedures}
        assert by_name["Вторая"].start_line == 4
        assert by_name["Вторая"].end_line == 6
        assert by_name["Первая"].start_line == 8
        assert by_name["Первая"].end_line == 10


class TestParseModuleStructureEdgeCases:
    def test_empty_text(self):
        structure = parse_module_structure("")
        assert structure.variables == []
        assert structure.procedures == []

    def test_no_procedures_or_variables(self):
        structure = parse_module_structure("// just a comment\nx = 1;")
        assert structure.variables == []
        assert structure.procedures == []

    def test_unterminated_procedure_closed_at_eof(self):
        text = "Procedure Foo()\n  x = 1;\n"
        structure = parse_module_structure(text)
        assert len(structure.procedures) == 1
        assert structure.procedures[0].end_line == 2
