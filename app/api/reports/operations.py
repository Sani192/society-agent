from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from typing import Any, cast

from app.api.reports.common import authorize_committee_member_report, record_report_access, require_event
from app.db.models import Society
from app.db.session import get_read_db
from app.modules.reports.common.exporters import export_csv, export_excel
from app.modules.reports.operations.food_pass_report import FoodPassOperationsReport
from app.modules.reports.pdf.food_pass_operations_pdf import generate_food_pass_operations_pdf
from app.utils.response import error_envelope, success

router = APIRouter(prefix="/reports/operations", tags=["Reports | Operations"])


@router.get("/food-pass")
def food_pass_operations_report(
    phone: str | None = Query(default=None),
    event_id: str | None = Query(default=None),
    db: Session = Depends(get_read_db),
):
    member, error_response = authorize_committee_member_report(
        phone=phone,
        db=db,
        report_code="FOOD_PASS_OPERATIONS",
        log_message="Failed to authorize food pass operations report",
    )
    if error_response:
        return error_response

    event, error_response = require_event(db=db, event_id=event_id)
    if error_response:
        return error_response

    report = FoodPassOperationsReport.generate(db=db, event_id=event.id)

    record_report_access(
        db=db,
        member=member,
        report_code="FOOD_PASS_OPERATIONS",
        format="JSON",
        event=event,
    )
    return success(report)


@router.get("/food-pass/export")
def export_food_pass_operations_report(
    phone: str | None = Query(default=None),
    event_id: str | None = Query(default=None),
    format: str = Query(default="csv"),
    db: Session = Depends(get_read_db),
):
    member, error_response = authorize_committee_member_report(
        phone=phone,
        db=db,
        report_code="FOOD_PASS_OPERATIONS",
        log_message="Failed to authorize food pass operations export",
    )
    if error_response:
        return error_response

    event, error_response = require_event(db=db, event_id=event_id)
    if error_response:
        return error_response

    report = FoodPassOperationsReport.generate(db=db, event_id=event.id)

    record_report_access(
        db=db,
        member=member,
        report_code="FOOD_PASS_OPERATIONS",
        format=format,
        event=event,
    )

    if format == "csv":
        return Response(
            content=export_csv(report["headers"], report["rows"]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=food_pass_operations.csv"},
        )

    if format == "excel":
        return Response(
            content=export_excel(
                sheet_name="Food Pass Operations",
                headers=report["headers"],
                rows=report["rows"],
            ),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=food_pass_operations.xlsx"},
        )

    if format == "pdf":
        society = db.query(Society).get(event.society_id)
        if society is None:
            return error_envelope("Society not found")

        branding = cast(dict[str, Any], (society.config_json or {}).get("branding", {}))
        logo_path = branding.get("logo_path")

        return Response(
            content=generate_food_pass_operations_pdf(
                society_name=society.name,
                event_name=event.name,
                report=report,
                logo_path=logo_path,
            ),
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=food_pass_operations.pdf"},
        )

    return error_envelope("Supported formats: csv, excel, pdf")
