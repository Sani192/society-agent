#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jan 23 17:34:26 2026

@author: anonymous
"""

from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors


def build_table(headers, rows):
    data = [headers] + rows
    table = Table(data, repeatRows=1)

    numeric_tokens = (
        "amount",
        "paid",
        "pending",
        "expected",
        "balance",
        "income",
        "expense",
        "refund",
        "total",
        "closing",
        "opening",
        "cash"
    )
    numeric_columns = [
        idx for idx, header in enumerate(headers)
        if any(token in header.lower() for token in numeric_tokens)
    ]

    styles = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1976D2")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONT", (0, 0), (-1, 0), "DejaVu"),
        ("FONT", (0, 1), (-1, -1), "DejaVu"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
    ]

    for col in numeric_columns:
        styles.append(("ALIGN", (col, 1), (col, -1), "RIGHT"))

    pending_index = headers.index("Pending") if "Pending" in headers else None
    for idx, row in enumerate(rows, start=1):
        if pending_index is None or pending_index >= len(row):
            continue
        pending = row[pending_index]
        if isinstance(pending, str):
            try:
                pending = float(pending.replace(",", ""))
            except ValueError:
                continue
        if pending == 0:
            styles.append(
                ("TEXTCOLOR", (0, idx), (-1, idx), colors.HexColor("#2E7D32"))
            )
        else:
            styles.append(
                ("TEXTCOLOR", (0, idx), (-1, idx), colors.HexColor("#C62828"))
            )

    table.setStyle(TableStyle(styles))
    return table
