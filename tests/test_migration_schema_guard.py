import re
from pathlib import Path

from app.db.base import Base

MIGRATIONS_DIR = Path("docs/migrations")
BASELINE_SUFFIX = "_baseline_schema.sql"
CREATE_TABLE_RE = re.compile(
    r"create\s+table\s+(?:if\s+not\s+exists\s+)?(?:public\.)?\"?([a-zA-Z_][\w$]*)\"?",
    flags=re.IGNORECASE,
)
CREATE_TABLE_BLOCK_RE = re.compile(
    r"create\s+table\s+(?:if\s+not\s+exists\s+)?(?:public\.)?\"?([a-zA-Z_][\w$]*)\"?\s*\((.*?)\);",
    flags=re.IGNORECASE | re.DOTALL,
)
ALTER_TABLE_BLOCK_RE = re.compile(
    r"alter\s+table\s+(?:if\s+exists\s+)?(?:public\.)?\"?([a-zA-Z_][\w$]*)\"?\s+(.*?);",
    flags=re.IGNORECASE | re.DOTALL,
)
ADD_COLUMN_IN_BLOCK_RE = re.compile(
    r"add\s+column\s+(?:if\s+not\s+exists\s+)?\"?([a-zA-Z_][\w$]*)\"?",
    flags=re.IGNORECASE,
)


def _latest_baseline_file() -> Path:
    baseline_files = sorted(MIGRATIONS_DIR.glob(f"*{BASELINE_SUFFIX}"))
    if not baseline_files:
        raise AssertionError("No baseline schema file found in docs/migrations")
    return baseline_files[-1]


def _tables_declared_in_sql(sql_text: str) -> set[str]:
    return {match.group(1).lower() for match in CREATE_TABLE_RE.finditer(sql_text)}


def _column_map_declared_in_sql(sql_text: str) -> dict[str, set[str]]:
    table_columns: dict[str, set[str]] = {}
    for match in CREATE_TABLE_BLOCK_RE.finditer(sql_text):
        table_name = match.group(1).lower()
        block = match.group(2)
        declared: set[str] = set()
        for raw_line in block.splitlines():
            line = raw_line.strip().rstrip(",")
            if not line:
                continue
            lowered = line.lower()
            if lowered.startswith(("constraint ", "primary key", "foreign key", "unique ", "check ")):
                continue
            column_name = line.split()[0].strip('"').lower()
            if column_name:
                declared.add(column_name)
        table_columns.setdefault(table_name, set()).update(declared)

    for match in ALTER_TABLE_BLOCK_RE.finditer(sql_text):
        table_name = match.group(1).lower()
        alter_block = match.group(2)
        for column_match in ADD_COLUMN_IN_BLOCK_RE.finditer(alter_block):
            table_columns.setdefault(table_name, set()).add(column_match.group(1).lower())

    return table_columns


def test_migration_sql_bundle_contains_all_model_tables():
    baseline_file = _latest_baseline_file()
    sql_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    assert baseline_file in sql_files

    declared_tables: set[str] = set()
    for sql_file in sql_files:
        declared_tables |= _tables_declared_in_sql(sql_file.read_text(encoding="utf-8"))

    model_tables = {name.lower() for name in Base.metadata.tables.keys()}

    missing_tables = sorted(model_tables - declared_tables)
    assert not missing_tables, (
        "Migration SQL files are missing model tables: "
        f"{missing_tables}. Add/update SQL migrations before release."
    )


def test_migration_sql_bundle_contains_all_model_columns():
    sql_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    declared_columns_by_table: dict[str, set[str]] = {}
    for sql_file in sql_files:
        file_columns = _column_map_declared_in_sql(sql_file.read_text(encoding="utf-8"))
        for table_name, columns in file_columns.items():
            declared_columns_by_table.setdefault(table_name, set()).update(columns)

    missing_by_table: dict[str, list[str]] = {}
    for table_name, table in Base.metadata.tables.items():
        model_columns = {column.name.lower() for column in table.columns}
        declared_columns = declared_columns_by_table.get(table_name.lower(), set())
        missing_columns = sorted(model_columns - declared_columns)
        if missing_columns:
            missing_by_table[table_name] = missing_columns

    assert not missing_by_table, (
        "Migration SQL files are missing model columns: "
        f"{missing_by_table}. Add/update SQL migrations before release."
    )
