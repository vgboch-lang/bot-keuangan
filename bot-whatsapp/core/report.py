# ============ OPTIMASI KECEPATAN ============
import reportlab.rl_config
reportlab.rl_config.shapeChecking = False

# ============ IMPORT ============
import os
import locale
import calendar
import time
from datetime import datetime, timedelta
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# ============ IMPORT UTILS & DATABASE ============
from .utils import format_rupiah, format_date
from .database import (
    get_report_data_optimized,
    get_summary,
    get_previous_month_summary,
    get_previous_week_summary
)

# ============ SETUP LOKAL ============
try:
    locale.setlocale(locale.LC_ALL, 'id_ID.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_ALL, 'Indonesian')
    except:
        pass

# ============ WARNA ============
COLOR_NAVY = colors.HexColor('#1A3C4A')
COLOR_ACCENT = colors.HexColor('#C9A227')
COLOR_ZEBRA = colors.HexColor('#F1F5F8')
COLOR_LINE = colors.HexColor('#D9E0E7')
COLOR_GRAY_LIGHT = colors.HexColor('#ECF0F1')
COLOR_GRAY_TEXT = colors.HexColor('#7F8C8D')
COLOR_GREEN = colors.HexColor('#1E8449')
COLOR_RED = colors.HexColor('#C0392B')
COLOR_WHITE = colors.HexColor('#FFFFFF')
COLOR_BLACK = colors.HexColor('#000000')

# ============ KONSTANTA LEBAR TABEL ============
TABLE_WIDTH = 446.69  # pt

# ============ NAMA HARI BAHASA INDONESIA ============
HARI_INDONESIA = {
    0: 'Senin', 1: 'Selasa', 2: 'Rabu', 3: 'Kamis',
    4: 'Jumat', 5: 'Sabtu', 6: 'Minggu'
}

def format_tanggal_with_day(date_obj):
    return f"{date_obj.strftime('%d/%m/%y')} {HARI_INDONESIA[date_obj.weekday()]}"

# ============ HELPER STYLE ============

KPI_STYLE = ParagraphStyle('KPI', parent=getSampleStyleSheet()['Normal'], alignment=TA_CENTER, leading=16, spaceBefore=2, spaceAfter=2)

def _kpi_cell(label, value, color):
    """Sel kartu ringkasan: label kecil + nilai besar"""
    return Paragraph(
        f'<font size="7" color="{color}">{label}</font>'
        f'<br/><font size="13" color="{color}"><b>{value}</b></font>',
        KPI_STYLE
    )

def _style_table(nrows, body_size=8, right_cols=(), total_row=True):
    """Style tabel konsisten: header navy, zebra, border halus, total tebal"""
    cmds = [
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 1), (-1, -1), body_size),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_NAVY),
        ('TEXTCOLOR', (0, 0), (-1, 0), COLOR_WHITE),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.4, COLOR_LINE),
        ('LINEBELOW', (0, 0), (-1, 0), 0.8, COLOR_NAVY),
    ]
    for i in range(2, nrows, 2):
        cmds.append(('BACKGROUND', (0, i), (-1, i), COLOR_ZEBRA))
    for col in right_cols:
        cmds.append(('ALIGN', (col, 1), (col, -1), 'RIGHT'))
    if total_row and nrows >= 2:
        last = nrows - 1
        cmds += [
            ('FONTNAME', (0, last), (-1, last), 'Helvetica-Bold'),
            ('BACKGROUND', (0, last), (-1, last), COLOR_ZEBRA),
            ('LINEABOVE', (0, last), (-1, last), 0.8, COLOR_LINE),
        ]
    return TableStyle(cmds)

# ============ HEADER & FOOTER ============

def _draw_footer(canvas, doc):
    canvas.saveState()
    w, h = A4
    y = 42
    canvas.setStrokeColor(COLOR_LINE)
    canvas.setLineWidth(0.5)
    canvas.line(74.29, y + 10, w - 74.29, y + 10)
    canvas.setFont('Helvetica', 7.5)
    canvas.setFillColor(COLOR_GRAY_TEXT)
    canvas.drawString(74.29, y - 2, f"Bot Catat Keuangan  •  Dicetak: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    canvas.drawRightString(w - 74.29, y - 2, f"Halaman {doc.page}")
    canvas.restoreState()

def _on_first_page(canvas, doc):
    _draw_footer(canvas, doc)

def _on_later_pages(canvas, doc):
    canvas.saveState()
    w, h = A4
    canvas.setStrokeColor(COLOR_NAVY)
    canvas.setLineWidth(1.2)
    canvas.line(74.29, h - 42, w - 74.29, h - 42)
    canvas.setFont('Helvetica-Bold', 9)
    canvas.setFillColor(COLOR_NAVY)
    canvas.drawString(74.29, h - 38, "LAPORAN KEUANGAN")
    canvas.restoreState()
    _draw_footer(canvas, doc)

# ============ GENERATE PDF REPORT ============
def generate_pdf_report(user_id, start_date, end_date, period, label, date_str):
    data = get_report_data_optimized(user_id, start_date.isoformat(), end_date.isoformat())
    
    if not data['pemasukan'] and not data['pengeluaran']:
        return None
    
    # ===== PERBANDINGAN =====
    perbandingan_data = None
    if label == 'Harian':
        perbandingan_data = None
    elif label in ['Mingguan', 'Bulanan', 'BulanIni']:
        if label in ['Bulanan', 'BulanIni']:
            prev_summary = get_previous_month_summary(user_id, start_date)
            label_periode = 'Bulan Lalu'
        else:  # Mingguan
            prev_summary = get_previous_week_summary(user_id, start_date)
            label_periode = 'Minggu Lalu'
        
        if prev_summary:
            perbandingan_data = {
                'label': label_periode,
                'pemasukan': prev_summary.get('total_income', 0),
                'pengeluaran': prev_summary.get('total_expense', 0),
                'saldo': prev_summary.get('balance', 0)
            }

    daily_data = data.get('daily_data', [])
    show_daily = label != 'Harian'
    
    if label == 'Mingguan' and daily_data:
        start_str = start_date.strftime('%d/%m/%y')
        end_str = end_date.strftime('%d/%m/%y')
        filtered_daily = []
        for item in daily_data:
            if start_str <= item['tanggal'] <= end_str:
                filtered_daily.append(item)
        daily_data = filtered_daily
    
    show_budget = label in ['Bulanan', 'BulanIni']
    
    # ===== FILE NAME =====
    if label in ['Bulanan', 'BulanIni']:
        file_date = start_date.strftime('%d-%m-%y')
    else:
        file_date = end_date.strftime('%d-%m-%y')
    
    os.makedirs('reports', exist_ok=True)
    filename = f"reports/Laporan_{label}_{file_date}.pdf"
    
    doc = SimpleDocTemplate(
        filename,
        pagesize=A4,
        leftMargin=74.29,
        rightMargin=74.29,
        topMargin=50,
        bottomMargin=50,
        onFirstPage=_on_first_page,
        onLaterPages=_on_later_pages
    )
    story = []
    styles = getSampleStyleSheet()
    
    # ===== STYLE =====
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=22, textColor=COLOR_NAVY, alignment=TA_LEFT, fontName='Helvetica-Bold', spaceAfter=2)
    label_line_style = ParagraphStyle('LabelLine', parent=styles['Normal'], fontSize=13, textColor=COLOR_ACCENT, fontName='Helvetica-Bold', spaceAfter=2)
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=10, textColor=COLOR_GRAY_TEXT, spaceAfter=0)
    heading_style = ParagraphStyle('Heading', parent=styles['Heading2'], fontSize=12, textColor=COLOR_NAVY, fontName='Helvetica-Bold', spaceAfter=6)
    insight_style = ParagraphStyle('Insight', parent=styles['Normal'], fontSize=9, textColor=COLOR_BLACK, fontName='Helvetica-Bold', spaceAfter=3, leftIndent=10)
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=9, textColor=COLOR_BLACK)
    ringkasan_style = ParagraphStyle('Ringkasan', parent=styles['Normal'], fontSize=11, textColor=COLOR_NAVY, fontName='Helvetica-Bold', spaceAfter=2, alignment=TA_CENTER)
    
    # ============================================================
    # HALAMAN 1
    # ============================================================
    label_upper = label.upper()
    story.append(Paragraph("LAPORAN KEUANGAN", title_style))
    story.append(Paragraph(f"REKAP {label_upper}", label_line_style))
    story.append(Paragraph(data['periode'], subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.4, color=COLOR_ACCENT, spaceBefore=6, spaceAfter=12))
    
    # Ringkasan dalam bentuk kartu KPI
    pem = format_rupiah(data['ringkasan']['pemasukan'])
    peng = format_rupiah(data['ringkasan']['pengeluaran'])
    saldo_val = data['ringkasan']['saldo']
    saldo_color = COLOR_GREEN if saldo_val >= 0 else COLOR_RED
    ringkasan_row = [
        _kpi_cell('PEMASUKAN', pem, COLOR_NAVY),
        _kpi_cell('PENGELUARAN', peng, COLOR_NAVY),
        _kpi_cell('SALDO', format_rupiah(saldo_val), saldo_color),
    ]
    ringkasan_table = Table([ringkasan_row], colWidths=[TABLE_WIDTH/3.0]*3, rowHeights=46)
    ringkasan_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), COLOR_WHITE),
        ('BOX', (0,0), (-1,-1), 0.8, COLOR_LINE),
        ('LINEABOVE', (0,0), (-1,0), 2.5, COLOR_NAVY),
        ('LINEAFTER', (0,0), (0,0), 0.6, COLOR_LINE),
        ('LINEAFTER', (1,0), (1,0), 0.6, COLOR_LINE),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
    ]))
    story.append(ringkasan_table)
    story.append(Spacer(1, 0.12*inch))
    
    if data['insight']:
        story.append(Paragraph("Insight", heading_style))
        for insight in data['insight']:
            story.append(Paragraph(f"• {insight}", insight_style))
        story.append(Spacer(1, 0.08*inch))
    
    if perbandingan_data:
        story.append(Paragraph(f"Perbandingan {perbandingan_data['label']}", heading_style))
        comp_data = [
            ['', 'Periode Ini', perbandingan_data['label']],
            ['Pemasukan', format_rupiah(data['ringkasan']['pemasukan']), format_rupiah(perbandingan_data['pemasukan'])],
            ['Pengeluaran', format_rupiah(data['ringkasan']['pengeluaran']), format_rupiah(perbandingan_data['pengeluaran'])],
            ['Saldo', format_rupiah(data['ringkasan']['saldo']), format_rupiah(perbandingan_data['saldo'])]
        ]
        comp_table = Table(comp_data, colWidths=[TABLE_WIDTH*0.35, TABLE_WIDTH*0.325, TABLE_WIDTH*0.325])
        comp_table.setStyle(_style_table(len(comp_data), body_size=9, right_cols=(1,2), total_row=False))
        story.append(comp_table)
        story.append(Spacer(1, 0.08*inch))
    
    if data['pie_chart']:
        story.append(Paragraph("Pengeluaran per Kategori", heading_style))
        kategori_data = [['Kategori', 'Nominal']]
        for item in data['pie_chart']:
            kategori_data.append([item['kategori'], format_rupiah(item['nominal'])])
        total_kategori = sum(item['nominal'] for item in data['pie_chart'])
        kategori_data.append(['Total', format_rupiah(total_kategori)])
        
        kategori_table = Table(kategori_data, colWidths=[TABLE_WIDTH*0.6, TABLE_WIDTH*0.4])
        kategori_table.setStyle(_style_table(len(kategori_data), body_size=9, right_cols=(1,)))
        story.append(kategori_table)
    
    # ============================================================
    # HALAMAN 2: TOTAL PENGELUARAN HARIAN
    # ============================================================
    if show_daily and daily_data:
        story.append(PageBreak())
        story.append(Paragraph("Total Pengeluaran Harian", heading_style))
        story.append(Spacer(1, 0.08*inch))
        
        daily_table_data = [['Tanggal', 'Pengeluaran']]
        total_harian = 0
        for item in daily_data:
            try:
                date_obj = datetime.strptime(item['tanggal'], '%d/%m/%y')
                tanggal_display = format_tanggal_with_day(date_obj)
            except:
                tanggal_display = item['tanggal']
            nominal = item['nominal']
            total_harian += nominal
            daily_table_data.append([tanggal_display, format_rupiah(nominal) if nominal > 0 else 'Rp0'])
        daily_table_data.append(['Total', format_rupiah(total_harian)])
        
        daily_table = Table(daily_table_data, colWidths=[TABLE_WIDTH*0.4, TABLE_WIDTH*0.6], rowHeights=16)
        daily_table.setStyle(_style_table(len(daily_table_data), body_size=8, right_cols=(1,)))
        story.append(daily_table)
        story.append(Spacer(1, 0.12*inch))
    
    # ============================================================
    # HALAMAN 3: DETAIL PEMASUKAN & BUDGET (jika ada)
    # ============================================================
    has_income = bool(data['pemasukan'])
    has_budget_page = show_budget and (data['budget'] or data['target'])
    has_page3_content = has_income or has_budget_page
    
    if has_page3_content:
        story.append(PageBreak())
        col_widths_5col = [TABLE_WIDTH*0.08, TABLE_WIDTH*0.17, TABLE_WIDTH*0.17, TABLE_WIDTH*0.33, TABLE_WIDTH*0.25]
        col_widths_budget = [TABLE_WIDTH*0.18, TABLE_WIDTH*0.20, TABLE_WIDTH*0.20, TABLE_WIDTH*0.20, TABLE_WIDTH*0.22]
        col_widths_3col = [TABLE_WIDTH*0.35, TABLE_WIDTH*0.325, TABLE_WIDTH*0.325]
        
        if has_income:
            story.append(Paragraph("Detail Pemasukan", heading_style))
            pemasukan_data = [['#', 'Tanggal', 'Kategori', 'Item', 'Nominal']]
            total_pemasukan = 0
            for i, item in enumerate(data['pemasukan'], 1):
                total_pemasukan += item['nominal']
                pemasukan_data.append([
                    str(i),
                    item['tanggal'],
                    item['kategori'],
                    item['item'][:25],
                    format_rupiah(item['nominal'])
                ])
            pemasukan_data.append(['Total', '', '', '', format_rupiah(total_pemasukan)])
            
            pemasukan_table = Table(pemasukan_data, colWidths=col_widths_5col)
            pemasukan_table.setStyle(_style_table(len(pemasukan_data), body_size=7.5, right_cols=(4,)))
            story.append(pemasukan_table)
            story.append(Spacer(1, 0.1*inch))
        
        # BUDGET & TARGET (HANYA BULANAN)
        if show_budget:
            # Budget
            if data['budget']:
                story.append(Paragraph("Budget & Target", heading_style))
                budget_data = [['Kategori', 'Budget', 'Realisasi', 'Sisa', 'Status']]
                for item in data['budget']:
                    if item['budget'] > 0:  # Tampilkan hanya jika budget diatur
                        status_text = '[OK]' if item['status'] == 'Aman' else '[!]'
                        budget_data.append([
                            item['kategori'],
                            format_rupiah(item['budget']),
                            format_rupiah(item['realisasi']),
                            format_rupiah(item['sisa']),
                            f"{status_text} {item['status']}"
                        ])
                # Jika ada data (tidak cuma header)
                if len(budget_data) > 1:
                    budget_table = Table(budget_data, colWidths=col_widths_budget)
                    budget_table.setStyle(_style_table(len(budget_data), body_size=7.5, right_cols=(1,2,3), total_row=False))
                    story.append(budget_table)
                    story.append(Spacer(1, 0.08*inch))
            
            # Target
            if data['target']:
                story.append(Paragraph("Target", heading_style))
                target_data = [['Target', 'Realisasi', 'Sisa']]
                for item in data['target']:
                    target_data.append([item['target'], item['realisasi'], item['sisa']])
                target_table = Table(target_data, colWidths=col_widths_3col)
                target_table.setStyle(_style_table(len(target_data), body_size=8, right_cols=(1,2), total_row=False))
                story.append(target_table)
    
    # ============================================================
    # DETAIL PENGELUARAN (HALAMAN TERPISAH)
    # ============================================================
    if data['pengeluaran']:
        # Jika tidak ada halaman 3, dan (ada daily atau harian), gabung di halaman yang sama
        should_append_here = (not has_page3_content) and (show_daily and daily_data)
        if not should_append_here:
            story.append(PageBreak())
        
        story.append(Paragraph("Detail Pengeluaran", heading_style))
        col_widths_5col = [TABLE_WIDTH*0.08, TABLE_WIDTH*0.17, TABLE_WIDTH*0.17, TABLE_WIDTH*0.33, TABLE_WIDTH*0.25]
        pengeluaran_data = [['#', 'Tanggal', 'Kategori', 'Item', 'Nominal']]
        total_pengeluaran = 0
        for i, item in enumerate(data['pengeluaran'], 1):
            total_pengeluaran += item['nominal']
            pengeluaran_data.append([
                str(i),
                item['tanggal'],
                item['kategori'],
                item['item'][:25],
                format_rupiah(item['nominal'])
            ])
        pengeluaran_data.append(['Total', '', '', '', format_rupiah(total_pengeluaran)])
        
        pengeluaran_table = Table(pengeluaran_data, colWidths=col_widths_5col)
        pengeluaran_table.setStyle(_style_table(len(pengeluaran_data), body_size=7.5, right_cols=(4,)))
        story.append(pengeluaran_table)
    
    # ============================================================
    # BUILD
    # ============================================================
    doc.build(story)
    return filename
