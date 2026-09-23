
#!/usr/bin/env python3
"""Generate a payment-period invoice PDF from fechas-de-pagos.txt and _config_params.py."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

import _config_params as cfg

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "_config_params.py"
DATES_FILE = BASE_DIR / "fechas-de-pagos.txt"
SENT_PERIODS_FILE = BASE_DIR / "sent_periods.json"
PERIOD_RE = re.compile(
    r"(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})(?:\s*[|]\s*(\d{2}/\d{2}/\d{4}))?"
)
INVOICE_NO_ASSIGN_RE = re.compile(r'(INVOICE_NO\s*=\s*")([^"]+)(")')

Period = tuple[date, date, date]

NAVY = colors.HexColor("#1B365D")
TEAL = colors.HexColor("#0F6C6C")
LIGHT_TEAL = colors.HexColor("#E6F4F4")
ROW_BG = colors.HexColor("#F4F7FA")
LINE = colors.HexColor("#C5CDD6")
MUTED = colors.HexColor("#5A6570")
BALANCE_BG = colors.HexColor("#0F6C6C")


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%m/%d/%Y").date()


def format_period(start: date, end: date) -> str:
    return f"{start.strftime('%m/%d/%Y')} - {end.strftime('%m/%d/%Y')}"


def format_long_date(value: date) -> str:
    return f"{value.strftime('%b')} {value.day} {value.year}"


def format_money(amount: float) -> str:
    return f"{amount:,.2f}"


def load_periods(path: Path) -> list[Period]:
    if not path.exists():
        raise FileNotFoundError(f"Dates file not found: {path}")
    periods: list[Period] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = PERIOD_RE.search(line)
        if not match:
            continue
        start = parse_date(match.group(1))
        end = parse_date(match.group(2))
        due = parse_date(match.group(3)) if match.group(3) else end
        periods.append((start, end, due))
    if not periods:
        raise ValueError(f"No payment periods found in {path}")
    return periods


def last_closed_period(periods: list[Period], today: date) -> Period:
    closed = [period for period in periods if period[1] <= today]
    if not closed:
        raise ValueError(f"No closed payment period found for {today.isoformat()}")
    return max(closed, key=lambda period: period[1])


def load_sent_periods(path: Path = SENT_PERIODS_FILE) -> set[str]:
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        periods = data.get("periods", [])
    elif isinstance(data, list):
        periods = data
    else:
        periods = []
    return {str(item) for item in periods}


def mark_period_sent(
    period_label: str,
    invoice_no: str,
    path: Path = SENT_PERIODS_FILE,
) -> None:
    existing = load_sent_periods(path)
    existing.add(period_label)
    payload = {
        "periods": sorted(existing),
        "last": {
            "period": period_label,
            "invoice_no": invoice_no,
            "sent_at": datetime.now().isoformat(timespec="seconds"),
        },
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def period_already_sent(period_label: str, path: Path = SENT_PERIODS_FILE) -> bool:
    return period_label in load_sent_periods(path)


def build_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "InvoiceTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=28,
            textColor=NAVY,
            alignment=TA_LEFT,
            spaceAfter=4,
        ),
        "period": ParagraphStyle(
            "PeriodHeader",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=12,
            textColor=TEAL,
            alignment=TA_LEFT,
            spaceAfter=10,
        ),
        "label": ParagraphStyle(
            "FieldLabel",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            textColor=MUTED,
            spaceAfter=2,
        ),
        "body": ParagraphStyle(
            "BodyTextCustom",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10,
            textColor=NAVY,
            leading=14,
        ),
        "body_bold": ParagraphStyle(
            "BodyBold",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            textColor=NAVY,
            leading=14,
        ),
        "meta_value": ParagraphStyle(
            "MetaValue",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=NAVY,
        ),
        "table_header": ParagraphStyle(
            "TableHeader",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            textColor=colors.white,
        ),
        "table_cell": ParagraphStyle(
            "TableCell",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            textColor=NAVY,
        ),
        "table_cell_right": ParagraphStyle(
            "TableCellRight",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            textColor=NAVY,
            alignment=TA_RIGHT,
        ),
        "totals_label": ParagraphStyle(
            "TotalsLabel",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10,
            textColor=MUTED,
            alignment=TA_RIGHT,
        ),
        "totals_value": ParagraphStyle(
            "TotalsValue",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            textColor=NAVY,
            alignment=TA_RIGHT,
        ),
        "balance_label": ParagraphStyle(
            "BalanceLabel",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=colors.white,
            alignment=TA_LEFT,
        ),
        "balance_value": ParagraphStyle(
            "BalanceValue",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=18,
            textColor=colors.white,
            alignment=TA_RIGHT,
        ),
        "note_label": ParagraphStyle(
            "NoteLabel",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=MUTED,
            spaceAfter=4,
        ),
        "note_body": ParagraphStyle(
            "NoteBody",
            parent=base["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=10,
            textColor=TEAL,
        ),
        "email": ParagraphStyle(
            "EmailStyle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            textColor=NAVY,
        ),
    }


def make_footer(period_label: str):
    def add_footer(canvas, _doc):
        canvas.saveState()
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.6)
        canvas.line(inch, 0.75 * inch, letter[0] - inch, 0.75 * inch)
        canvas.setFont("Helvetica-Oblique", 9)
        canvas.setFillColor(TEAL)
        canvas.drawString(inch, 0.5 * inch, f"period {period_label}")
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(MUTED)
        canvas.drawRightString(letter[0] - inch, 0.5 * inch, "Page 1 of 1")
        canvas.restoreState()

    return add_footer


def build_story(
    styles: dict[str, ParagraphStyle],
    start: date,
    end: date,
    due: date,
) -> list:
    period_label = format_period(start, end)
    period_text = f"period {period_label}"
    amount = cfg.RATE
    money = format_money(amount)
    invoice_date = format_long_date(end)
    due_date = format_long_date(due)
    to_lines = "<br/>".join([cfg.TO_NAME, *cfg.TO_ADDRESS.splitlines()])

    story: list = [
        Paragraph("Invoice", styles["title"]),
        Paragraph(period_text, styles["period"]),
        HRFlowable(width="100%", thickness=1.5, color=NAVY, spaceAfter=16),
    ]

    parties = Table(
        [
            [
                Paragraph("FROM", styles["label"]),
                Paragraph("TO", styles["label"]),
            ],
            [
                Paragraph(cfg.FROM_NAME, styles["body_bold"]),
                Paragraph(to_lines, styles["body"]),
            ],
        ],
        colWidths=[3.5 * inch, 3.5 * inch],
    )
    parties.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
            ]
        )
    )
    story.extend([parties, Spacer(1, 18)])

    meta = Table(
        [
            [
                Paragraph("INVOICE NO.", styles["label"]),
                Paragraph("DATE", styles["label"]),
                Paragraph("INVOICE DUE", styles["label"]),
            ],
            [
                Paragraph(cfg.INVOICE_NO, styles["meta_value"]),
                Paragraph(invoice_date, styles["meta_value"]),
                Paragraph(due_date, styles["meta_value"]),
            ],
        ],
        colWidths=[2.3 * inch, 2.3 * inch, 2.4 * inch],
    )
    meta.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), ROW_BG),
                ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, 0), 8),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 10),
            ]
        )
    )
    story.extend([meta, Spacer(1, 22)])

    items = Table(
        [
            [
                Paragraph("DESCRIPTION", styles["table_header"]),
                Paragraph("AMOUNT", styles["table_header"]),
                Paragraph("RATE", styles["table_header"]),
                Paragraph("QTY", styles["table_header"]),
            ],
            [
                Paragraph(period_text, styles["table_cell"]),
                Paragraph(f"{cfg.CURRENCY} {money}", styles["table_cell_right"]),
                Paragraph(money, styles["table_cell_right"]),
                Paragraph("1", styles["table_cell_right"]),
            ],
        ],
        colWidths=[3.4 * inch, 1.4 * inch, 1.3 * inch, 0.9 * inch],
    )
    items.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("BACKGROUND", (0, 1), (-1, 1), LIGHT_TEAL),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LINEBELOW", (0, 1), (-1, 1), 0.5, LINE),
            ]
        )
    )
    story.extend([items, Spacer(1, 12)])

    totals = Table(
        [
            [
                Paragraph("Sub Total", styles["totals_label"]),
                Paragraph(money, styles["totals_value"]),
            ],
            [
                Paragraph(f"Total {cfg.CURRENCY}", styles["totals_label"]),
                Paragraph(money, styles["totals_value"]),
            ],
            [
                Paragraph(f"Paid to Date {cfg.CURRENCY}", styles["totals_label"]),
                Paragraph("0.00", styles["totals_value"]),
            ],
        ],
        colWidths=[5.4 * inch, 1.6 * inch],
    )
    totals.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LINEABOVE", (0, 0), (-1, 0), 0.5, LINE),
            ]
        )
    )
    story.extend([totals, Spacer(1, 10)])

    balance = Table(
        [
            [
                Paragraph("BALANCE DUE", styles["balance_label"]),
                Paragraph(f"{cfg.CURRENCY} {money}", styles["balance_value"]),
            ]
        ],
        colWidths=[3.5 * inch, 3.5 * inch],
    )
    balance.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), BALANCE_BG),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                ("BOX", (0, 0), (-1, -1), 0, BALANCE_BG),
            ]
        )
    )
    story.extend([balance, Spacer(1, 24)])

    story.extend(
        [
            Paragraph("INVOICE NOTE", styles["note_label"]),
            Paragraph(period_text, styles["note_body"]),
            Spacer(1, 10),
            Paragraph(f"Email: {cfg.EMAIL}", styles["email"]),
        ]
    )
    return story


def next_invoice_no(invoice_no: str) -> str:
    match = re.match(r"^(.*?)(\d+)$", invoice_no)
    if not match:
        raise ValueError(f"Cannot increment invoice number: {invoice_no}")
    prefix, digits = match.groups()
    return f"{prefix}{int(digits) + 1:0{len(digits)}d}"


def bump_invoice_no(config_path: Path, current: str) -> str:
    nxt = next_invoice_no(current)
    text = config_path.read_text(encoding="utf-8")
    new_text, count = INVOICE_NO_ASSIGN_RE.subn(
        lambda match: f"{match.group(1)}{nxt}{match.group(3)}",
        text,
        count=1,
    )
    if count != 1:
        raise ValueError("Could not update INVOICE_NO in _config_params.py")
    config_path.write_text(new_text, encoding="utf-8")
    return nxt


def generate_invoice(today: date | None = None) -> tuple[Path, str, date]:
    today = today or date.today()
    start, end, due = last_closed_period(load_periods(DATES_FILE), today)
    period_label = format_period(start, end)
    invoice_no = cfg.INVOICE_NO
    output_dir = Path(cfg.OUTPUT_PATH).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{invoice_no}.pdf"
    styles = build_styles()
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=inch,
        rightMargin=inch,
        topMargin=0.7 * inch,
        bottomMargin=inch,
        title=f"{invoice_no} - {period_label}",
        author=cfg.FROM_NAME,
    )
    doc.build(
        build_story(styles, start, end, due),
        onFirstPage=make_footer(period_label),
    )
    return output_path, period_label, due


def _tb_quote(value: str) -> str:
    """Escape a value for Thunderbird -compose key='value' fields."""
    return value.replace("\\", "\\\\").replace("'", "\\'")


def build_email_body(invoice_no: str, period_label: str, due: date) -> str:
    return (
        "Hi ,\n"
        "\n"
        f"A new invoice has been generated for you by {cfg.FROM_NAME}. "
        "Here's a quick summary:\n"
        "\n"
        f"Invoice Details: {invoice_no} - period {period_label}\n"
        "\n"
        f"Total Invoice Amount: {format_money(cfg.RATE)} {cfg.CURRENCY}\n"
        "\n"
        f"Due Date: {format_long_date(due)}\n"
        "\n"
        "You can view the invoice or download a PDF copy of it from the following link:\n"
        "\n"
        "(Please see the attached PDF.)"
    )


def open_thunderbird_with_invoice(pdf_path: Path, period_label: str, due: date) -> None:
    thunderbird = shutil.which("thunderbird")
    if not thunderbird:
        raise FileNotFoundError("Thunderbird not found in PATH")

    invoice_no = pdf_path.stem
    to_addr = getattr(cfg, "EMAIL_TO", "") or ""
    subject = f"Invoice {invoice_no} - period {period_label}"
    body = build_email_body(invoice_no, period_label, due)
    attachment = pdf_path.resolve().as_uri()
    compose = (
        f"to='{_tb_quote(to_addr)}',"
        f"subject='{_tb_quote(subject)}',"
        f"body='{_tb_quote(body)}',"
        f"attachment='{_tb_quote(attachment)}'"
    )
    subprocess.Popen([thunderbird, "-compose", compose])


def run_pipeline(*, if_needed: bool = False, today: date | None = None) -> int:
    today = today or date.today()
    try:
        start, end, due = last_closed_period(load_periods(DATES_FILE), today)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    period_label = format_period(start, end)
    if if_needed and period_already_sent(period_label):
        print(f"Skip: period {period_label} already sent")
        return 0

    if if_needed:
        print(f"Due: period {period_label} not sent yet (invoice due {due.strftime('%m/%d/%Y')})")

    try:
        output_path, period_label, due = generate_invoice(today=today)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Generated {output_path}")

    if getattr(cfg, "OPEN_THUNDERBIRD", False):
        try:
            open_thunderbird_with_invoice(output_path, period_label, due)
            print("Opened Thunderbird compose with PDF attached.")
        except FileNotFoundError as exc:
            print(f"Warning: {exc}", file=sys.stderr)
            return 1

    bump_invoice_no(CONFIG_FILE, output_path.stem)
    mark_period_sent(period_label, output_path.stem)
    print(f"Next invoice: {next_invoice_no(output_path.stem)}")
    print(f"Marked period as sent: {period_label}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Mouri invoice PDF")
    parser.add_argument(
        "--if-needed",
        action="store_true",
        help="Only run if the last closed period was not emailed yet",
    )
    args = parser.parse_args(argv)
    return run_pipeline(if_needed=args.if_needed)


if __name__ == "__main__":
    raise SystemExit(main())
