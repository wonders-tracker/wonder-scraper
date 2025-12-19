"""
Storage for CSV reports using Postgres (text column).
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict
from sqlmodel import Session, select, desc

from app.db import engine
from app.models.market import Report


def upload_csv(filename: str, content: bytes) -> str:
    """
    Store CSV in Postgres and return a unique identifier.

    Returns the report ID as a string (for compatibility with blob storage API).
    """
    csv_text = content.decode("utf-8")

    # Determine report type from filename
    report_type = "daily"
    if "weekly" in filename.lower():
        report_type = "weekly"
    elif "monthly" in filename.lower():
        report_type = "monthly"

    with Session(engine) as session:
        report = Report(filename=filename, report_type=report_type, content=csv_text)
        session.add(report)
        session.commit()
        session.refresh(report)

        return f"db://report/{report.id}"


def get_report(report_id: int) -> Optional[Report]:
    """Get a report by ID."""
    with Session(engine) as session:
        return session.get(Report, report_id)


def get_report_content(report_id: int) -> Optional[str]:
    """Get report content by ID."""
    report = get_report(report_id)
    return report.content if report else None


def list_reports(report_type: Optional[str] = None, limit: int = 20) -> List[Dict]:
    """List recent reports."""
    with Session(engine) as session:
        query = select(Report).order_by(desc(Report.created_at)).limit(limit)

        if report_type:
            query = query.where(Report.report_type == report_type)

        reports = session.exec(query).all()

        return [
            {
                "id": r.id,
                "filename": r.filename,
                "report_type": r.report_type,
                "created_at": r.created_at.isoformat(),
                "size": len(r.content),
            }
            for r in reports
        ]


def delete_report(report_id: int) -> bool:
    """Delete a report by ID."""
    with Session(engine) as session:
        report = session.get(Report, report_id)
        if report:
            session.delete(report)
            session.commit()
            return True
        return False


def cleanup_old_reports(days: int = 30) -> int:
    """Delete reports older than N days. Returns count deleted."""
    from datetime import timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    with Session(engine) as session:
        old_reports = session.exec(select(Report).where(Report.created_at < cutoff)).all()

        count = len(old_reports)
        for report in old_reports:
            session.delete(report)

        session.commit()
        return count
