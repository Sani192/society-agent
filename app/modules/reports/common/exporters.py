#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from openpyxl import Workbook

import csv
import io
from collections.abc import Iterable, Iterator


def export_csv(headers, rows):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def stream_csv_chunks(headers: list, rows: Iterable[list], *, chunk_size: int = 500) -> Iterator[bytes]:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    yield output.getvalue().encode("utf-8")
    output.seek(0)
    output.truncate(0)

    batch: list[list] = []
    for row in rows:
        batch.append(row)
        if len(batch) >= chunk_size:
            writer.writerows(batch)
            yield output.getvalue().encode("utf-8")
            output.seek(0)
            output.truncate(0)
            batch.clear()

    if batch:
        writer.writerows(batch)
        yield output.getvalue().encode("utf-8")


def export_excel(sheet_name: str, headers: list, rows: list):
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name

    ws.append(headers)
    for row in rows:
        ws.append(row)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()
