#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jan 23 16:51:26 2026

@author: anonymous
"""


from openpyxl import Workbook

import csv
import io

def export_csv(headers, rows):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(rows)
    return output.getvalue()


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
