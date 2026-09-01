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


@mcp.tool()
def list_ert_dialog_controls(name: str) -> str:
    """Разобранный (структурированный) список элементов управления формы
    внешней обработки — id, класс контрола (BUTTON/STATIC/1CEDIT/BMASKED/...),
    подпись, координаты/размер, привязанный реквизит и его тип, действие
    (обработчик). Используйте перед add_ert_dialog_control/
    update_ert_dialog_control/remove_ert_dialog_control, чтобы узнать id
    существующих элементов и не пересекаться с ними по координатам. Работает
    для ЛЮБОЙ обработки (не только из --edit-path) — это инструмент чтения.
    Для сырого текста формы (без разбора) используйте get_ert_form.

    Args:
        name: Имя обработки без расширения .ert.
    """
    return tools.list_ert_dialog_controls(name)


@mcp.tool()
def get_ert_print_form(name: str) -> str:
    """Разобранная печатная форма (Page.1, формат MOXCEL — встроенная "таблица"
    1С 7.7, на основе которой строится печатный вывод отчёта/обработки):
    список непустых текстовых ячеек по строкам, с привязками к реквизитам/
    выражениям (например значение ячейки может быть именем переменной
    модуля вроде "ПоставщикОКПО" — тогда 1С подставит туда значение при
    формировании печати). Работает для ЛЮБОЙ обработки (не только из
    --edit-path) — это инструмент чтения. Встроенные объекты (картинки,
    линии, OLE) не разбираются подробно, только их количество. Именованные
    секции (для `Таблица.ВывестиСекцию()`) не показаны здесь — см.
    list_ert_print_form_sections. Ячейки типа "expression"/"pattern"/
    "fixed_pattern" (см. print_form_rows в create_ert_file) помечены суффиксом
    вида "[pattern]" после значения.

    Args:
        name: Имя обработки без расширения .ert.
    """
    return tools.get_ert_print_form(name)


# --- External processing (.ert) write tools — require --edit-path ---
#
# Эти инструменты позволяют создавать/редактировать внешние обработки, но
# работают ТОЛЬКО с файлами внутри каталога, заданного параметром запуска
# сервера --edit-path. Если сервер запущен без --edit-path, все они
# возвращают текстовое сообщение об ошибке вместо результата.


@mcp.tool()
def create_ert_file(
    name: str,
    module_text: str = "",
    caption: str = "",
    print_form_rows: list[list[str | dict]] | None = None,
) -> str:
    """Создать новую внешнюю обработку (.ert) в каталоге --edit-path.
    Требует запуска сервера с параметром --edit-path.

    Создаёт файл с пустой (или заданным начальным текстом) формой и модулем.
    После создания используйте add_ert_dialog_control, чтобы добавить
    элементы управления на форму, update_ert_module, чтобы изменить код,
    update_ert_print_form, чтобы позже изменить печатную форму, и
    add_ert_print_form_section, чтобы задать именованные секции
    ("Шапка"/"Строка"/"Подвал" и т.п.) для `Таблица.ВывестиСекцию()`.

    Args:
        name: Имя новой обработки без расширения .ert (без '/', '\\', '..').
        module_text: Начальный текст программного модуля (БСЛ). Можно
                     оставить пустым и заполнить позже через update_ert_module.
        caption: Заголовок окна формы. Пусто — заголовок по умолчанию (" ").
        print_form_rows: Необязательная начальная печатная форма (таблица) —
                     список строк, каждая строка — список ячеек по колонкам.
                     Каждая ячейка — либо просто строка (обычный текст,
                     выводится как есть, например "Кол-во"), либо словарь
                     {"text": ..., "type": ...} для отчётных ячеек:
                     - "text" — тип по умолчанию, литеральный текст;
                     - "expression" — "text" это имя реквизита/переменной
                       1С (например "Наименование"), которое при печати
                       подставится вычисленным значением;
                     - "pattern" (шаблон) — "text" это строка с плейсхолдерами
                       "[Выражение]" внутри, например
                       "Всего [ИтогоПоТаблице] шт.";
                     - "fixed_pattern" (фиксированный шаблон) — как pattern,
                       но вычисляется 1С только один раз.
                     Пример: [["Товар","Кол-во"],
                     [{"text":"Наименование","type":"expression"}, "5"]].
                     Пусто — печатная форма не используется (как у
                     большинства служебных обработок без визуального отчёта).
    """
    return tools.create_ert_file(name, module_text, caption, print_form_rows)


@mcp.tool()
def update_ert_module(name: str, new_text: str) -> str:
    """Полностью заменить текст программного модуля (БСЛ) внешней обработки
    в каталоге --edit-path. Требует запуска сервера с параметром --edit-path
    и того, чтобы файл '<name>.ert' уже находился именно в --edit-path
    (обработки из других каталогов, например ExtForms, недоступны для записи).

    Перед изменением получите текущий код через get_ert_module, отредактируйте
    его и передайте сюда целиком. Для больших модулей, где нужно поправить
    лишь несколько мест, предпочтительнее patch_ert_module или
    replace_ert_module_lines, а для добавления нового кода в конец —
    append_ert_module_text; все три не требуют пересылки всего текста модуля.

    Args:
        name: Имя обработки без расширения .ert.
        new_text: Новый полный текст модуля.
    """
    return tools.update_ert_module(name, new_text)


@mcp.tool()
def patch_ert_module(name: str, edits: list[dict]) -> str:
    """Применить набор точечных правок к тексту программного модуля (БСЛ)
    внешней обработки в каталоге --edit-path, не пересылая весь текст модуля
    целиком. Требует --edit-path.

    Каждая правка — словарь {"old_string": ..., "new_string": ...,
    "replace_all": ...} ("replace_all" необязателен, по умолчанию false).
    "old_string" должен встречаться в модуле ровно один раз на момент
    применения правки — включите достаточно окружающего контекста, чтобы
    фрагмент был уникальным, — либо укажите "replace_all": true, если
    нужно заменить все вхождения. Правки применяются по порядку; если
    хотя бы одна не находит совпадения, файл не изменяется.

    Предпочтительнее update_ert_module для точечных исправлений в больших
    модулях. Для замены целого известного блока по номерам строк (например,
    процедуры целиком) используйте replace_ert_module_lines.

    Args:
        name: Имя обработки без расширения .ert.
        edits: Список правок вида {"old_string", "new_string", "replace_all"}.
    """
    return tools.patch_ert_module(name, edits)


@mcp.tool()
def append_ert_module_text(name: str, text: str) -> str:
    """Добавить текст в конец программного модуля (БСЛ) внешней обработки в
    каталоге --edit-path, не пересылая существующий (возможно, большой)
    текст модуля целиком. Требует --edit-path.

    Удобно для добавления новой процедуры/функции в конец модуля — особенно
    когда добавляемый текст сам по себе большой, а существующий модуль
    менять не нужно. Разделяющий перевод строки добавляется автоматически,
    если текущий текст ещё не оканчивается им.

    Args:
        name: Имя обработки без расширения .ert.
        text: Текст, добавляемый в конец модуля.
    """
    return tools.append_ert_module_text(name, text)


@mcp.tool()
def replace_ert_module_lines(name: str, start_line: int, end_line: int, new_text: str) -> str:
    """Заменить диапазон строк (нумерация с 1, включительно) текста
    программного модуля (БСЛ) внешней обработки в каталоге --edit-path, не
    пересылая весь текст модуля целиком. Требует --edit-path.

    Точные номера строк узнайте заранее через get_ert_module или
    get_ert_procedure_source. Для точечных исправлений, где легко указать
    уникальный фрагмент текста, предпочтительнее patch_ert_module.

    Args:
        name: Имя обработки без расширения .ert.
        start_line: Первая заменяемая строка (с 1).
        end_line: Последняя заменяемая строка (включительно).
        new_text: Новый текст, которым заменяется указанный диапазон строк.
    """
    return tools.replace_ert_module_lines(name, start_line, end_line, new_text)


@mcp.tool()
def set_ert_dialog_frame(
    name: str, caption: str | None = None, width: int | None = None, height: int | None = None
) -> str:
    """Изменить заголовок и/или размер окна формы внешней обработки в
    каталоге --edit-path. Требует --edit-path.

    Args:
        name: Имя обработки без расширения .ert.
        caption: Новый заголовок окна формы, если нужно изменить.
        width: Новая ширина окна формы, если нужно изменить.
        height: Новая высота окна формы, если нужно изменить.
    """
    return tools.set_ert_dialog_frame(name, caption, width, height)


@mcp.tool()
def add_ert_dialog_control(
    name: str,
    caption: str,
    control_class: str,
    x: int,
    y: int,
    width: int,
    height: int,
    action: str = "",
    bound_attribute: str = "",
    type_code: str = "",
    tab_group_name: str = "Основной",
) -> str:
    """Добавить новый элемент управления на форму внешней обработки в
    каталоге --edit-path. Требует --edit-path. Используйте
    list_ert_dialog_controls перед вызовом, чтобы посмотреть уже занятые
    координаты и существующие id.

    Args:
        name: Имя обработки без расширения .ert.
        caption: Текст/подпись элемента (для BUTTON/STATIC/CHECKBOX и т.п.).
        control_class: Класс элемента, например BUTTON, STATIC, 1CEDIT,
                       BMASKED, CHECKBOX.
        x: Координата X (в единицах формы 1С).
        y: Координата Y.
        width: Ширина элемента.
        height: Высота элемента.
        action: Обработчик/действие, например "Сформировать()" или "#Закрыть"
                для стандартной кнопки закрытия.
        bound_attribute: Имя реквизита формы, с которым связан элемент
                         (для полей ввода типа 1CEDIT/BMASKED).
        type_code: Код типа значения реквизита — один из: S(Строка),
                   N(Число), D(Дата), B(Справочник), E(Перечисление),
                   O(Документ), P(ПланСчетов), U(Неопределенный),
                   L(Логический). Пусто, если элемент ни к чему не привязан.
        tab_group_name: Имя группы табуляции (по умолчанию "Основной").
    """
    return tools.add_ert_dialog_control(
        name, caption, control_class, x, y, width, height,
        action, bound_attribute, type_code, tab_group_name,
    )


@mcp.tool()
def update_ert_dialog_control(
    name: str,
    control_id: int,
    caption: str | None = None,
    control_class: str | None = None,
    x: int | None = None,
    y: int | None = None,
    width: int | None = None,
    height: int | None = None,
    action: str | None = None,
    bound_attribute: str | None = None,
    type_code: str | None = None,
    tab_group_name: str | None = None,
) -> str:
    """Изменить поля существующего элемента управления формы внешней
    обработки в каталоге --edit-path. Требует --edit-path. Указывайте
    только те параметры, которые нужно изменить — остальные останутся
    прежними. id элемента можно узнать через list_ert_dialog_controls.

    Args:
        name: Имя обработки без расширения .ert.
        control_id: id изменяемого элемента управления.
        caption: Новый текст/подпись, если нужно изменить.
        control_class: Новый класс элемента, если нужно изменить.
        x: Новая координата X, если нужно изменить.
        y: Новая координата Y, если нужно изменить.
        width: Новая ширина, если нужно изменить.
        height: Новая высота, если нужно изменить.
        action: Новый обработчик/действие, если нужно изменить.
        bound_attribute: Новый привязанный реквизит, если нужно изменить.
        type_code: Новый код типа (см. add_ert_dialog_control), если нужно изменить.
        tab_group_name: Новая группа табуляции, если нужно изменить.
    """
    return tools.update_ert_dialog_control(
        name, control_id, caption, control_class, x, y, width, height,
        action, bound_attribute, type_code, tab_group_name,
    )


@mcp.tool()
def update_ert_print_form(name: str, rows: list[list[str | dict]]) -> str:
    """Заменить печатную форму (Page.1, MOXCEL-таблица) внешней обработки в
    каталоге --edit-path простой сеткой ячеек (текст/выражение/шаблон/
    фиксированный шаблон — см. print_form_rows в create_ert_file). Требует
    --edit-path. Форматирование (шрифты/границы/цвета), объединение ячеек и
    встроенные объекты (картинки/линии) этим инструментом не поддерживаются;
    для сложного оформления печатную форму нужно доработать вручную в
    дизайнере 1С.

    ВАЖНО: этот инструмент строит печатную форму заново с нуля, поэтому
    стирает все ранее заданные секции (см. list_ert_print_form_sections/
    add_ert_print_form_section) — вызывайте его до настройки секций, а не
    после.

    Args:
        name: Имя обработки без расширения .ert.
        rows: Список строк таблицы, каждая строка — список текстов ячеек по
              колонкам (см. print_form_rows в create_ert_file).
    """
    return tools.update_ert_print_form(name, rows)


@mcp.tool()
def remove_ert_dialog_control(name: str, control_id: int) -> str:
    """Удалить элемент управления с формы внешней обработки в каталоге
    --edit-path. Требует --edit-path.

    Args:
        name: Имя обработки без расширения .ert.
        control_id: id удаляемого элемента управления (см. list_ert_dialog_controls).
    """
    return tools.remove_ert_dialog_control(name, control_id)


@mcp.tool()
def list_ert_print_form_sections(name: str) -> str:
    """Разобранный список именованных секций печатной формы (Page.1, MOXCEL)
    внешней обработки — отдельно горизонтальные (диапазоны строк) и
    вертикальные (диапазоны колонок), с уровнем вложенности. Именно эти
    секции 1С-код обработки выводит по имени через
    `Таблица.ВывестиСекцию("ИмяСекции")`, комбинируя их для построения
    итогового отчёта (типичные имена: "Шапка", "Строка", "Подвал",
    "ЗаголовокТаблицы"). Используйте перед add_ert_print_form_section/
    update_ert_print_form_section/remove_ert_print_form_section, чтобы
    узнать уже существующие имена и диапазоны. Работает для ЛЮБОЙ обработки
    (не только из --edit-path) — это инструмент чтения.

    Args:
        name: Имя обработки без расширения .ert.
    """
    return tools.list_ert_print_form_sections(name)


@mcp.tool()
def add_ert_print_form_section(
    name: str, orientation: str, section_name: str, begin: int, end: int, level: int = 0
) -> str:
    """Добавить именованную секцию в печатную форму внешней обработки в
    каталоге --edit-path (не переписывая остальную форму — существующие
    ячейки, форматирование и другие секции сохраняются). Требует
    --edit-path.

    Args:
        name: Имя обработки без расширения .ert.
        orientation: "horizontal" — секция задаёт диапазон строк (begin/end
                     — номера строк), "vertical" — диапазон колонок
                     (begin/end — номера колонок).
        section_name: Имя новой секции (используется в
                      `Таблица.ВывестиСекцию("ИмяСекции")` в коде 1С);
                      должно быть уникальным в пределах указанной ориентации.
        begin: Первая строка/колонка секции (включительно).
        end: Последняя строка/колонка секции (включительно).
        level: Уровень вложенности для группировок секций (0 — верхний
               уровень, как у большинства секций в реальных формах).
    """
    return tools.add_ert_print_form_section(name, orientation, section_name, begin, end, level)


@mcp.tool()
def update_ert_print_form_section(
    name: str,
    orientation: str,
    section_name: str,
    begin: int | None = None,
    end: int | None = None,
    level: int | None = None,
    new_name: str | None = None,
) -> str:
    """Изменить поля существующей именованной секции печатной формы внешней
    обработки в каталоге --edit-path. Требует --edit-path. Указывайте
    только те параметры, которые нужно изменить — остальные останутся
    прежними. Текущие имена и диапазоны секций можно узнать через
    list_ert_print_form_sections.

    Args:
        name: Имя обработки без расширения .ert.
        orientation: "horizontal" или "vertical" — ориентация изменяемой
                     секции (секция ищется по этой ориентации и её текущему
                     имени; сменить ориентацию секции нельзя — удалите и
                     добавьте заново в нужной ориентации).
        section_name: Текущее имя изменяемой секции.
        begin: Новая первая строка/колонка, если нужно изменить.
        end: Новая последняя строка/колонка, если нужно изменить.
        level: Новый уровень вложенности, если нужно изменить.
        new_name: Новое имя секции, если нужно переименовать.
    """
    return tools.update_ert_print_form_section(
        name, orientation, section_name, begin, end, level, new_name
    )


@mcp.tool()
def remove_ert_print_form_section(name: str, orientation: str, section_name: str) -> str:
    """Удалить именованную секцию из печатной формы внешней обработки в
    каталоге --edit-path. Требует --edit-path.

    Args:
        name: Имя обработки без расширения .ert.
        orientation: "horizontal" или "vertical" — ориентация удаляемой
                     секции (см. list_ert_print_form_sections).
        section_name: Имя удаляемой секции.
    """
    return tools.remove_ert_print_form_section(name, orientation, section_name)


@mcp.tool()
def execute_sql_query(query: str, max_rows: int = 200) -> str:
    """Выполнить прямой SQL-запрос к MSSQL базе данных текущей загруженной
    конфигурации 1С 7.7. Требует --allow-sql при запуске сервера и файл
    1Cv7.DBA в каталоге базы (доступно только для реальной базы через
    --basepath, не для произвольно загруженного 1Cv7.MD).

    Разрешены только запросы на чтение: один оператор SELECT (в т.ч. с
    предваряющим WITH/CTE). Любые операторы изменения данных или структуры
    (INSERT, UPDATE, DELETE, MERGE, CREATE, ALTER, DROP, TRUNCATE, EXEC,
    вызовы sp_/xp_-процедур и т.п.), а также несколько операторов через ';'
    — отклоняются до подключения к серверу.

    Args:
        query: Текст SQL-запроса (один SELECT-оператор).
        max_rows: Максимум строк в результате (по умолчанию 200); при
                  превышении результат обрезается с пометкой об этом.
    """
    return tools.execute_sql_query(query, max_rows)
