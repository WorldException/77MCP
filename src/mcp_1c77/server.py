"""MCP server for 1C:Enterprise 7.7 configuration metadata.

Provides LLM clients with access to metadata objects, attributes, modules,
and forms from 1Cv7.MD configuration files.
"""

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from . import tools

# The server is reached over LAN/Docker by IP or container hostname, not just
# localhost — FastMCP's default DNS-rebinding protection only allowlists
# 127.0.0.1/localhost and would reject those requests with HTTP 421.
mcp = FastMCP(
    "1c77-metadata",
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


@mcp.tool()
def reload_configuration(path: str = "") -> str:
    """Перезагрузить конфигурацию (или загрузить другой файл).

    Args:
        path: Путь к файлу 1Cv7.MD. Если пустой — перезагружает текущий файл.
    """
    return tools.reload_configuration(path)


@mcp.tool()
def list_objects(object_type: str = "") -> str:
    """Список объектов метаданных конфигурации.

    Args:
        object_type: Тип объекта для фильтрации (Справочник, Документ, Регистр,
                     Перечисление, Отчёт, Журнал, Константа, ВидРасчёта).
                     Пустая строка — показать все типы.
    """
    return tools.list_objects(object_type)


@mcp.tool()
def get_object(object_type: str, name: str) -> str:
    """Детальная информация об объекте метаданных (реквизиты, табличные части).

    Args:
        object_type: Тип объекта (Справочник, Документ, Регистр, Перечисление, и т.д.)
        name: Имя объекта.
    """
    return tools.get_object(object_type, name)


@mcp.tool()
def get_module(object_type: str, name: str, start_line: int = 0, end_line: int = 0) -> str:
    """Получить исходный код модуля объекта метаданных.

    Args:
        object_type: Тип объекта (Справочник, Документ, Отчёт, ВидРасчёта).
        name: Имя объекта.
        start_line: Начальная строка (1-индексация). 0 = с начала.
        end_line: Конечная строка включительно. 0 = до конца.
                  При обоих 0 модуль усекается до ~1500 строк, если он большой.
    """
    return tools.get_module(object_type, name, start_line, end_line)


@mcp.tool()
def get_form(object_type: str, name: str) -> str:
    """Получить описание формы объекта (элементы управления).

    Args:
        object_type: Тип объекта (Справочник, Документ, Отчёт, ВидРасчёта).
        name: Имя объекта.
    """
    return tools.get_form(object_type, name)


@mcp.tool()
def search(query: str) -> str:
    """Поиск по объектам метаданных (по имени, синониму, комментарию).

    Args:
        query: Строка поиска.
    """
    return tools.search(query)


@mcp.tool()
def get_configuration_info() -> str:
    """Общая информация о загруженной конфигурации."""
    return tools.get_configuration_info()


@mcp.tool()
def validate_field_path(object_type: str, name: str, path: str) -> str:
    """Проверить валидность пути обращения к реквизиту объекта.

    Args:
        object_type: Тип (Документ, Справочник, Регистр, Перечисление)
        name: Имя объекта
        path: Путь к реквизиту (напр. "Сумма", "Товар.Артикул", "Партия.ГТД.Наименование")
    """
    return tools.validate_field_path(object_type, name, path)


@mcp.tool()
def validate_query(query_text: str) -> str:
    """Проверить все пути обращений к реквизитам в тексте запроса/кода 1С 7.7.

    Args:
        query_text: Полный текст запроса или фрагмент кода
    """
    return tools.validate_query(query_text)


@mcp.tool()
def search_field(field_name: str, object_type: str = "") -> str:
    """Найти все объекты, содержащие реквизит с данным именем (обратный поиск).

    Args:
        field_name: Имя реквизита для поиска
        object_type: Опционально: Документ, Справочник, Регистр
    """
    return tools.search_field(field_name, object_type)


@mcp.tool()
def get_objects_batch(object_type: str, names: list[str]) -> str:
    """Пакетное получение метаданных нескольких объектов за один вызов.

    Args:
        object_type: Тип объектов (Документ, Справочник, и т.д.)
        names: Список имён объектов
    """
    return tools.get_objects_batch(object_type, names)


@mcp.tool()
def get_global_module(start_line: int = 0, end_line: int = 0) -> str:
    """Получить исходный код глобального модуля конфигурации.

    Глобальный модуль — это модуль, доступный из любого места конфигурации 1С 7.7.
    Хранится в контейнере TypedText (стрим ModuleText_Number1).

    Args:
        start_line: Начальная строка (1-индексация). 0 = с начала.
        end_line: Конечная строка включительно. 0 = до конца.
                  При обоих 0 модуль усекается до ~1500 строк, если он большой.
    """
    return tools.get_global_module(start_line, end_line)


@mcp.tool()
def list_modules() -> str:
    """Список всех модулей конфигурации, включая глобальный модуль.

    Показывает какие объекты имеют модули с исходным кодом.
    """
    return tools.list_modules()


@mcp.tool()
def search_in_modules(query: str, context_lines: int = 0, limit: int = 200) -> str:
    """Полнотекстовый поиск по исходному коду всех модулей конфигурации.

    Args:
        query: Строка для поиска (без учёта регистра).
        context_lines: Сколько строк до и после совпадения показывать.
        limit: Максимум совпадений в ответе (по всем модулям).
    """
    return tools.search_in_modules(query, context_lines, limit)


@mcp.tool()
def resolve_id(object_id: str) -> str:
    """Определить тип и имя объекта метаданных по его внутреннему ID.

    Args:
        object_id: Внутренний идентификатор объекта (числовая строка)
    """
    return tools.resolve_id(object_id)


@mcp.tool()
def list_module_procedures(object_type: str = "", name: str = "") -> str:
    """Список процедур и функций модуля (с параметрами, Экспорт, диапазоном строк).

    Args:
        object_type: Тип объекта (Документ, Справочник, Отчёт, ВидРасчёта).
                     Пустая строка (вместе с пустым name) или "Глобальный" — глобальный модуль.
        name: Имя объекта. Не требуется для глобального модуля.
    """
    return tools.list_module_procedures(object_type, name)


@mcp.tool()
def get_module_variables(object_type: str = "", name: str = "") -> str:
    """Список переменных модульного уровня (Перем/Var), объявленных в модуле.

    Args:
        object_type: Тип объекта (Документ, Справочник, Отчёт, ВидРасчёта).
                     Пустая строка (вместе с пустым name) или "Глобальный" — глобальный модуль.
        name: Имя объекта. Не требуется для глобального модуля.
    """
    return tools.get_module_variables(object_type, name)


@mcp.tool()
def get_procedure_source(proc_name: str, object_type: str = "", name: str = "") -> str:
    """Исходный текст конкретной процедуры или функции по её имени.

    Args:
        proc_name: Имя процедуры или функции.
        object_type: Тип объекта модуля. Если не указан вместе с name — поиск
                     ведётся по всем модулям конфигурации (включая глобальный).
        name: Имя объекта модуля.
    """
    return tools.get_procedure_source(proc_name, object_type, name)


@mcp.tool()
def list_enums() -> str:
    """Список всех перечислений конфигурации вместе с их значениями."""
    return tools.list_enums()


@mcp.tool()
def list_ert_files() -> str:
    """Список всех найденных внешних обработок 1С (файлов *.ert) — начните с этого
    инструмента, если не знаете точное имя обработки, или чтобы просто узнать,
    какие внешние обработки вообще доступны на сервере.

    Внешняя обработка (файл .ert) — это отдельный от основной конфигурации
    объект 1С:Предприятие 7.7 (внешний отчёт/обработка), у которого есть свой
    программный модуль (процедуры/функции) и своя форма (диалог), но нет
    привязки к объектам основной конфигурации (Справочники, Документы и т.д.).

    Каталоги для поиска задаются при запуске сервера (--exts / ExtForms) и
    сканируются рекурсивно. Не принимает параметров.

    Возвращает список пар "имя — полный путь к файлу". Имя (без расширения
    .ert) — это то, что нужно передавать в качестве параметра name/имя во все
    остальные ert-инструменты (find_ert_file, get_ert_module,
    list_ert_procedures, get_ert_procedure_source, get_ert_form).
    """
    return tools.list_ert_files()


@mcp.tool()
def find_ert_file(name: str) -> str:
    """Проверить, существует ли внешняя обработка с указанным именем, и найти
    её точное имя/путь. Используйте это, чтобы ответить на вопрос вида
    "есть ли обработка <имя>?" или чтобы уточнить точное написание имени
    перед вызовом get_ert_module/list_ert_procedures/get_ert_form.

    Сравнение точное (без учёта регистра), НЕ поиск по подстроке — если имя
    указано не полностью или с ошибкой, инструмент вернёт "не найдена" и
    список похожих имён-подсказок. Если нужен поиск по тексту КОДА модулей
    (а не по имени обработки), используйте search_in_ert_modules. Если нужен
    просто полный список всех обработок — list_ert_files.

    Args:
        name: Имя обработки без расширения .ert (например "Робот1" для файла
              "Робот1.ert"), можно узнать точное написание через list_ert_files.
    """
    return tools.find_ert_file(name)


@mcp.tool()
def list_ert_procedures(name: str) -> str:
    """Список всех процедур и функций (с параметрами, флагом Экспорт и
    диапазоном строк), объявленных в программном модуле внешней обработки.
    Используйте, чтобы узнать, какие методы вообще есть в обработке, прежде
    чем запрашивать исходный код конкретного метода через
    get_ert_procedure_source.

    Args:
        name: Имя обработки без расширения .ert. Точное имя можно получить
              через list_ert_files или find_ert_file.
    """
    return tools.list_ert_procedures(name)


@mcp.tool()
def get_ert_procedure_source(name: str, proc_name: str) -> str:
    """Исходный код одной конкретной процедуры или функции из модуля внешней
    обработки — используйте после list_ert_procedures, когда уже известно
    точное имя метода. Для получения всего модуля целиком используйте
    get_ert_module.

    Args:
        name: Имя обработки без расширения .ert.
        proc_name: Имя процедуры или функции (без учёта регистра), как оно
                   объявлено в модуле, например "Сформировать".
    """
    return tools.get_ert_procedure_source(name, proc_name)


@mcp.tool()
def get_ert_module(name: str, start_line: int = 0, end_line: int = 0) -> str:
    """Весь исходный код программного модуля внешней обработки целиком (или
    указанный диапазон строк). Если нужен код только одной процедуры —
    эффективнее использовать get_ert_procedure_source.

    Args:
        name: Имя обработки без расширения .ert. Точное имя можно получить
              через list_ert_files или find_ert_file.
        start_line: Начальная строка (1-индексация). 0 = с начала.
        end_line: Конечная строка включительно. 0 = до конца.
                  При обоих 0 модуль усекается до ~1500 строк, если он большой.
    """
    return tools.get_ert_module(name, start_line, end_line)


@mcp.tool()
def search_in_ert_modules(query: str, context_lines: int = 0, limit: int = 200) -> str:
    """Полнотекстовый поиск подстроки по исходному коду модулей ВСЕХ найденных
    внешних обработок сразу (без учёта регистра) — используйте, когда нужно
    найти, в какой обработке и в какой строке встречается конкретный текст,
    имя переменной, вызов процедуры и т.п. Это поиск по коду, а НЕ по имени
    файла обработки (для поиска по имени используйте find_ert_file).

    Args:
        query: Строка для поиска (например часть имени процедуры,
               переменной или текстовая константа).
        context_lines: Сколько строк до и после совпадения показывать.
        limit: Максимум совпадений в ответе (по всем обработкам).
    """
    return tools.search_in_ert_modules(query, context_lines, limit)


@mcp.tool()
def get_ert_form(name: str) -> str:
    """Описание формы (диалога) внешней обработки — элементы управления,
    расположение, размеры (сырой текст в формате 1С, "Dialog Stream").

    Args:
        name: Имя обработки без расширения .ert. Точное имя можно получить
              через list_ert_files или find_ert_file.
    """
    return tools.get_ert_form(name)


@mcp.tool()
def reload_ert_files() -> str:
    """Пересканировать каталоги внешних обработок (*.ert) на предмет новых,
    удалённых или изменённых файлов. Вызывайте, если ожидаете, что список
    обработок на диске изменился после последнего сканирования (сервер
    сканирует каталоги один раз при старте и кэширует список)."""
    return tools.reload_ert_files()
