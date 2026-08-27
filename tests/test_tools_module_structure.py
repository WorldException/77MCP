# -*- coding: utf-8 -*-
"""Tests for module structure tools: procedures, variables, procedure source, enums."""

from __future__ import annotations

from unittest.mock import patch

from mcp_1c77.models import (
    Configuration,
    Enum,
    EnumValue,
    ModuleProcedure,
    ModuleStructure,
    ModuleVariable,
)
from mcp_1c77.tools import (
    get_module_variables,
    get_procedure_source,
    list_enums,
    list_module_procedures,
)

_STRUCTURE = ModuleStructure(
    variables=[
        ModuleVariable(name="гОрг", exported=False, line=1),
        ModuleVariable(name="гВерсия", exported=True, line=2),
    ],
    procedures=[
        ModuleProcedure(
            kind="Процедура", name="Инициализация", params=[], exported=False,
            start_line=4, end_line=6,
        ),
        ModuleProcedure(
            kind="Функция", name="ПолучитьВерсию", params=["Знач X"], exported=True,
            start_line=8, end_line=10,
        ),
    ],
)

_MODULE_TEXT = "\n".join(f"line {i}" for i in range(1, 11))


class TestListModuleProceduresGlobal:
    @patch("mcp_1c77.tools._loader")
    def test_defaults_to_global_module(self, mock_loader):
        mock_loader.is_loaded = True
        mock_loader.get_global_module_structure.return_value = _STRUCTURE
        result = list_module_procedures()
        assert "ГлобальныйМодуль" in result
        assert "Инициализация" in result
        assert "ПолучитьВерсию" in result
        assert "Экспорт" in result

    @patch("mcp_1c77.tools._loader")
    def test_object_module(self, mock_loader):
        mock_loader.is_loaded = True
        mock_loader.get_module_structure.return_value = _STRUCTURE
        result = list_module_procedures("Документ", "Заказ")
        assert "Документ.Заказ" in result
        mock_loader.get_module_structure.assert_called_once_with("Документ", "Заказ")

    @patch("mcp_1c77.tools._loader")
    def test_object_type_without_name_is_error(self, mock_loader):
        mock_loader.is_loaded = True
        result = list_module_procedures("Документ")
        assert "укажите" in result.lower()

    @patch("mcp_1c77.tools._loader")
    def test_empty_module(self, mock_loader):
        mock_loader.is_loaded = True
        mock_loader.get_global_module_structure.return_value = ModuleStructure()
        result = list_module_procedures()
        assert "не найдены" in result


class TestGetModuleVariables:
    @patch("mcp_1c77.tools._loader")
    def test_lists_module_level_variables(self, mock_loader):
        mock_loader.is_loaded = True
        mock_loader.get_global_module_structure.return_value = _STRUCTURE
        result = get_module_variables()
        assert "гОрг" in result
        assert "гВерсия" in result
        assert "Экспорт" in result


class TestGetProcedureSource:
    @patch("mcp_1c77.tools._loader")
    def test_targeted_lookup(self, mock_loader):
        mock_loader.is_loaded = True
        mock_loader.get_module_structure.return_value = _STRUCTURE
        mock_loader.get_module.return_value = _MODULE_TEXT
        result = get_procedure_source("Инициализация", "Документ", "Заказ")
        assert "line 4" in result
        assert "line 6" in result
        assert "line 7" not in result

    @patch("mcp_1c77.tools._loader")
    def test_targeted_lookup_not_found(self, mock_loader):
        mock_loader.is_loaded = True
        mock_loader.get_module_structure.return_value = _STRUCTURE
        result = get_procedure_source("НетТакой", "Документ", "Заказ")
        assert "не найдена" in result

    @patch("mcp_1c77.tools._loader")
    def test_search_all_modules_single_match(self, mock_loader):
        mock_loader.is_loaded = True
        mock_loader.list_modules.return_value = [
            {"type": "ГлобальныйМодуль", "name": "Глобальный модуль", "id": "", "kind": "global"},
        ]
        mock_loader.get_global_module_structure.return_value = _STRUCTURE
        mock_loader.get_global_module.return_value = _MODULE_TEXT
        result = get_procedure_source("Инициализация")
        assert "line 4" in result

    @patch("mcp_1c77.tools._loader")
    def test_search_all_modules_multiple_matches(self, mock_loader):
        mock_loader.is_loaded = True
        mock_loader.list_modules.return_value = [
            {"type": "ГлобальныйМодуль", "name": "Глобальный модуль", "id": "", "kind": "global"},
            {"type": "Документ", "name": "Заказ", "id": "1", "kind": "object"},
        ]
        mock_loader.get_global_module_structure.return_value = _STRUCTURE
        mock_loader.get_module_structure.return_value = _STRUCTURE
        result = get_procedure_source("Инициализация")
        assert "Найдено 2" in result
        assert "Уточните" in result

    @patch("mcp_1c77.tools._loader")
    def test_search_all_modules_no_match(self, mock_loader):
        mock_loader.is_loaded = True
        mock_loader.list_modules.return_value = []
        result = get_procedure_source("НетТакой")
        assert "не найдена" in result


class TestListEnums:
    @patch("mcp_1c77.tools._loader")
    def test_lists_enum_values(self, mock_loader):
        mock_loader.is_loaded = True
        config = Configuration(
            enums=[
                Enum(
                    id="1",
                    name="СтатусЗаказа",
                    comment="Статусы заказа",
                    values=[
                        EnumValue(id="1", name="Новый"),
                        EnumValue(id="2", name="Закрыт", comment="Завершён"),
                    ],
                )
            ]
        )
        mock_loader.config = config
        result = list_enums()
        assert "СтатусЗаказа" in result
        assert "Новый" in result
        assert "Закрыт" in result
        assert "Завершён" in result

    @patch("mcp_1c77.tools._loader")
    def test_no_enums(self, mock_loader):
        mock_loader.is_loaded = True
        mock_loader.config = Configuration()
        result = list_enums()
        assert "не найдены" in result
