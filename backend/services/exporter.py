import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from io import BytesIO
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

class AttendanceExporter:
    @staticmethod
    def _get_val(rec, key, default=""):
        if isinstance(rec, dict):
            val = rec.get(key, default)
        else:
            val = getattr(rec, key, default)
        return val if val is not None else default

    @classmethod
    def export_to_excel(cls, records, columns=None):
        """Generates a beautifully formatted Excel file with color-coded status styling and dynamic columns."""
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Attendance Summary"

        if not records:
            headers = columns or ["Employee ID", "Employee Name", "Date", "Shift", "First Check In", "Last Check Out", "Working Hours", "Status"]
        elif columns:
            headers = columns
        elif isinstance(records[0], dict):
            skip_keys = {"raw_idx", "raw_row_data", "working_hours_decimal", "is_overnight", "remarks", "gender", "department"}
            headers = [k for k in records[0].keys() if k not in skip_keys]
        else:
            headers = [
                "Employee ID", "Employee Name", "Department", "Date", "Day",
                "Shift", "First Check In", "Last Check Out", "Working Hours", "Status"
            ]

        # Header style
        header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        center_align = Alignment(horizontal="center", vertical="center")
        left_align = Alignment(horizontal="left", vertical="center")

        ws.append(headers)
        for col_num in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col_num)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = center_align

        # Fills for status color coding
        fill_green = PatternFill(start_color="D1FAE5", end_color="D1FAE5", fill_type="solid")   # Present
        font_green = Font(color="065F46", bold=True)

        fill_yellow = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")  # Missing Checkout
        font_yellow = Font(color="92400E", bold=True)

        fill_orange = PatternFill(start_color="FFEDD5", end_color="FFEDD5", fill_type="solid")  # Overtime
        font_orange = Font(color="C2410C", bold=True)

        fill_red = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")     # Error / Missing Login
        font_red = Font(color="991B1B", bold=True)

        thin_border = Border(
            left=Side(style='thin', color='E2E8F0'),
            right=Side(style='thin', color='E2E8F0'),
            top=Side(style='thin', color='E2E8F0'),
            bottom=Side(style='thin', color='E2E8F0')
        )

        status_col_idx = None
        for i, h in enumerate(headers, start=1):
            if str(h).lower() == "status":
                status_col_idx = i
                break

        for row_idx, rec in enumerate(records, start=2):
            row_data = []
            for h in headers:
                h_lower = str(h).lower().strip()
                if h_lower in ('check out', 'checkout', 'last check out', 'out time', 'last checkout'):
                    val = cls._get_val(rec, 'last_check_out') or cls._get_val(rec, h)
                elif h_lower in ('logout date', 'logout_date', 'check-out date', 'checkout date'):
                    val = cls._get_val(rec, 'logout_date_str') or cls._get_val(rec, 'logout_date') or cls._get_val(rec, 'Logout Date') or cls._get_val(rec, h)
                else:
                    val = cls._get_val(rec, h)
                row_data.append(str(val) if val is not None and val != '' else '')
            ws.append(row_data)

            # Apply cell borders & alignment
            for col_idx in range(1, len(headers) + 1):
                cell = ws.cell(row=row_idx, column=col_idx)
                cell.border = thin_border
                cell.alignment = center_align if col_idx == status_col_idx or "date" in headers[col_idx-1].lower() or "time" in headers[col_idx-1].lower() or "shift" in headers[col_idx-1].lower() else left_align

            # Color code status cell
            if status_col_idx:
                status_cell = ws.cell(row=row_idx, column=status_col_idx)
                st = str(cls._get_val(rec, "status")).lower()
                if "present" in st:
                    status_cell.fill = fill_green
                    status_cell.font = font_green
                elif "missing logout" in st or "missing checkout" in st:
                    status_cell.fill = fill_yellow
                    status_cell.font = font_yellow
                elif "overtime" in st:
                    status_cell.fill = fill_orange
                    status_cell.font = font_orange
                else:
                    status_cell.fill = fill_red
                    status_cell.font = font_red

        # Auto-adjust column widths
        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

        output = BytesIO()
        wb.save(output)
        output.seek(0)
        return output

    @classmethod
    def export_to_pdf(cls, records):
        """Generates a styled PDF report for processed attendance records."""
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        story = []

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'ReportTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#1E293B"),
            spaceAfter=10
        )

        subtitle_style = ParagraphStyle(
            'ReportSubTitle',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#64748B"),
            spaceAfter=15
        )

        story.append(Paragraph("Smart Attendance Summary Report", title_style))
        story.append(Paragraph("Automated shift detection, overnight punch pairing, and anomaly audit report.", subtitle_style))

        # Build Table Data
        table_data = [
            ["Emp ID", "Employee", "Date", "Shift", "Check In", "Check Out", "Hours", "Status", "Remarks"]
        ]

        for r in records:
            table_data.append([
                cls._get_val(r, "employee_id"),
                str(cls._get_val(r, "employee_name"))[:15],
                str(cls._get_val(r, "attendance_date")),
                cls._get_val(r, "shift"),
                cls._get_val(r, "first_check_in", "--"),
                cls._get_val(r, "last_check_out", "--"),
                cls._get_val(r, "working_hours", "00:00"),
                cls._get_val(r, "status"),
                str(cls._get_val(r, "remarks", ""))[:25]
            ])

        t = Table(table_data, colWidths=[65, 100, 75, 45, 60, 60, 55, 90, 160])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E293B")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ]))

        story.append(t)
        doc.build(story)
        buffer.seek(0)
        return buffer
