"""From the options a user confirmed and the file's sniffed shape to the table the
job will build: column names, types, which columns are skipped, and whether a
type is strict (the user set it, so a bad value fails the job) or inferred (a bad
value widens the column to text)."""

from dataclasses import dataclass, field

from workspaces import naming
from workspaces.errors import ImportOptionsInvalid
from workspaces.imports.sniff import Sniffed


@dataclass
class PlannedColumn:
    index: int
    name: str
    header: str
    type: str | None  # None until the scan decides it
    strict: bool
    description: str = ""


@dataclass
class Plan:
    table_name: str
    columns: list[PlannedColumn]
    description: str = ""
    primary_key: list[str] = field(default_factory=list)
    relations: list[dict] = field(default_factory=list)
    header_descriptions: bool = False


def build(sniffed: Sniffed, options: dict, default_table: str) -> Plan:
    overrides: dict[int, dict] = {}
    for item in options.get("columns") or []:
        index = item.get("index")
        if not isinstance(index, int) or not 0 <= index < sniffed.column_count:
            raise ImportOptionsInvalid(
                "A column override names a column the file does not have."
            )
        if index in overrides:
            raise ImportOptionsInvalid("A column is listed twice.")
        overrides[index] = item
    columns: list[PlannedColumn] = []
    taken: list[str] = []
    for index in range(sniffed.column_count):
        item = overrides.get(index, {})
        if item.get("skip"):
            continue
        header = sniffed.headers[index]
        if item.get("name"):
            name = naming.column_name(item["name"], taken)
        else:
            name = naming.column_name(sniffed.headers[index], taken)
        taken.append(name)
        api_type = item.get("type")
        if api_type is not None:
            naming.column_type(api_type)  # InvalidName on an unknown type
        columns.append(
            PlannedColumn(
                index=index,
                name=name,
                header=header,
                type=api_type,
                strict=api_type is not None,
                description=(item.get("description") or "").strip(),
            )
        )
    if not columns:
        raise ImportOptionsInvalid("Every column was skipped.")
    names = {c.name for c in columns}
    primary_key = list(options.get("primary_key") or [])
    if any(n not in names for n in primary_key):
        raise ImportOptionsInvalid(
            "The primary key names a column that is not imported."
        )
    relations = list(options.get("relations") or [])
    for relation in relations:
        if any(n not in names for n in relation.get("columns", [])):
            raise ImportOptionsInvalid(
                "A relation names a column that is not imported."
            )
    return Plan(
        table_name=default_table,
        columns=columns,
        description=(options.get("description") or "").strip(),
        primary_key=primary_key,
        relations=relations,
        header_descriptions=bool(options.get("header_descriptions")),
    )
