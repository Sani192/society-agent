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

    styles = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1976D2")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONT", (0, 0), (-1, 0), "DejaVu"),
        ("FONT", (0, 1), (-1, -1), "DejaVu"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
    ]

    for idx, row in enumerate(rows, start=1):
        pending = row[-1]
        if pending == 0:
            styles.append(("TEXTCOLOR", (0, idx), (-1, idx), colors.HexColor("#2E7D32")))
        else:
            styles.append(("TEXTCOLOR", (0, idx), (-1, idx), colors.HexColor("#C62828")))

    table.setStyle(TableStyle(styles))
    return table

