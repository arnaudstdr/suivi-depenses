import csv
import io
from datetime import date, datetime
from typing import Any

from openpyxl import Workbook, load_workbook

from app.core.errors import AppError

REQUIRED_COLUMNS = {"date", "label", "amount", "category"}


def import_format(filename: str | None) -> str:
    extension = (filename or "").rsplit(".", 1)[-1].lower()
    if extension == "csv":
        return "csv"
    if extension == "xlsx":
        return "xlsx"
    raise AppError(
        code="unsupported_import_format",
        message="Seuls les formats CSV et XLSX sont acceptés.",
        status_code=422,
    )


def parse_import_file(
    *,
    content: bytes,
    source_format: str,
    max_rows: int,
) -> list[dict[str, Any]]:
    if source_format == "csv":
        return _parse_csv(content, max_rows)
    if source_format == "xlsx":
        return _parse_xlsx(content, max_rows)
    raise AppError(
        code="unsupported_import_format",
        message="Seuls les formats CSV et XLSX sont acceptés.",
        status_code=422,
    )


def build_csv(headers: list[str], rows: list[list[Any]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\n")
    writer.writerow(headers)
    writer.writerows([[_spreadsheet_safe(value) for value in row] for row in rows])
    # BOM UTF-8 pour une ouverture correcte dans les tableurs.
    return buffer.getvalue().encode("utf-8-sig")


def build_xlsx(headers: list[str], rows: list[list[Any]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Export"
    sheet.append(headers)
    for row in rows:
        sheet.append([_spreadsheet_safe(value) for value in row])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _parse_csv(content: bytes, max_rows: int) -> list[dict[str, Any]]:
    text = _decode_csv(content)
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;")
    except csv.Error:
        dialect = csv.excel

    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if reader.fieldnames is None:
        raise _invalid_file("Le fichier ne contient pas d'en-tête.")
    try:
        records = [_normalize_record(index + 2, row) for index, row in enumerate(reader)]
    except csv.Error as exc:
        raise _invalid_file("Le fichier CSV est illisible.") from exc
    return _normalize_rows(records, max_rows)


def _parse_xlsx(content: bytes, max_rows: int) -> list[dict[str, Any]]:
    try:
        workbook = load_workbook(
            filename=io.BytesIO(content),
            read_only=True,
            data_only=True,
        )
    except Exception as exc:
        raise _invalid_file("Le fichier XLSX est illisible.") from exc

    try:
        sheet = workbook.active
        iterator = sheet.iter_rows(values_only=True)
        header = next(iterator, None)
        if header is None:
            raise _invalid_file("Le fichier ne contient pas d'en-tête.")
        headers = [_cell_text(value).strip().lower() for value in header]
        records: list[dict[str, Any]] = []
        for index, values in enumerate(iterator):
            if all(value is None or _cell_text(value).strip() == "" for value in values):
                continue
            record = {
                headers[position]: _cell_text(value)
                for position, value in enumerate(values)
                if position < len(headers)
            }
            records.append(_normalize_record(index + 2, record))
        return _normalize_rows(records, max_rows)
    except AppError:
        raise
    except Exception as exc:
        raise _invalid_file("Le fichier XLSX est illisible.") from exc
    finally:
        workbook.close()


def _normalize_rows(
    rows: list[dict[str, Any]],
    max_rows: int,
) -> list[dict[str, Any]]:
    if len(rows) > max_rows:
        raise AppError(
            code="import_too_many_rows",
            message=f"Le fichier dépasse la limite de {max_rows} lignes.",
            status_code=422,
        )
    return rows


def _normalize_record(row_number: int, raw: dict[str, Any]) -> dict[str, Any]:
    normalized = {(key or "").strip().lower(): value for key, value in raw.items()}
    errors: list[str] = []
    missing = REQUIRED_COLUMNS - normalized.keys()
    if missing:
        errors.append("Colonnes obligatoires manquantes : " + ", ".join(sorted(missing)) + ".")

    return {
        "row_number": row_number,
        "date": _text(normalized.get("date")),
        "label": _text(normalized.get("label")),
        "amount": _text(normalized.get("amount")),
        "category": _text(normalized.get("category")),
        "notes": _text(normalized.get("notes")),
        "errors": errors,
    }


def _decode_csv(content: bytes) -> str:
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            return content.decode("cp1252")
        except UnicodeDecodeError as exc:
            raise _invalid_file("L'encodage du fichier CSV est invalide.") from exc


def _spreadsheet_safe(value: Any) -> Any:
    if isinstance(value, str) and value[:1] in {"=", "+", "-", "@", "\t", "\r"}:
        return "'" + value
    return value


def _cell_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _invalid_file(message: str) -> AppError:
    return AppError(
        code="invalid_import_file",
        message=message,
        status_code=422,
    )
