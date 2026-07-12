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
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# ============ IMPORT UTILS & DATABASE ============
from utils import format_rupiah, format_date
from database import (
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
COLOR_GRAY_LIGHT = colors.HexColor('#ECF0F1')
COLOR_GRAY_TEXT = colors.HexColor('#7F8C8D')
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

# ============ GENERATE PDF REPORT ============
def generate_pdf_report(user_id, start_date, end_date, period, label, date_str):
    """
    Generate PDF laporan keuangan dengan desain final dan konten dinamis.
    label: 'Harian', 'Mingguan', 'Bulanan', 'BulanIni'
    """
    data = get_report_data_optimized(user_id, start_date.isoformat(), end_date.isoformat())
    
    if not data['pemasukan'] and not data['investasi'] and not data['pengeluaran']:
        return None
    
    # ===== PERBANDINGAN =====
    perbandingan_data = None
    if label == 'Harian':
        perbandingan_data = None
    elif label in ['Mingguan', 'Bulanan', 'BulanIni']:
        if label in ['Bulanan', 'BulanIni']:
            prev_summary = get_previous_month_summary(user_id)
            label_periode = 'Bulan Lalu'
        else:  # Mingguan
            prev_summary = get_previous_week_summary(user_id, start_date)
            label_periode = 'Minggu Lalu'
        
        if prev_summary:
            perbandingan_data = {
                'label': label_periode,
                'pemasukan': prev_summary.get('total_income', 0),
                'pengeluaran': prev_summary.get('total_expense', 0),
                'investasi': prev_summary.get('total_investment', 0),
                'saldo': prev_summary.get('balance', 0)
            }
    
    # ===== TOTAL PENGELUARAN HARIAN =====
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
        bottomMargin=50
    )
    story = []
    styles = getSampleStyleSheet()
    
    # ===== STYLE =====
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=22, textColor=COLOR_NAVY, alignment=TA_LEFT, fontName='Helvetica-Bold', spaceAfter=4)
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=12, textColor=COLOR_GRAY_TEXT, spaceAfter=8)
    heading_style = ParagraphStyle('Heading', parent=styles['Heading2'], fontSize=12, textColor=COLOR_NAVY, fontName='Helvetica-Bold', spaceAfter=6)
    insight_style = ParagraphStyle('Insight', parent=styles['Normal'], fontSize=9, textColor=COLOR_BLACK, fontName='Helvetica-Bold', spaceAfter=3)
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=9, textColor=COLOR_BLACK)
    ringkasan_style = ParagraphStyle(
        'Ringkasan',
        parent=styles['Normal'],
        fontSize=11,
        textColor=COLOR_NAVY,
        fontName='Helvetica-Bold',
        spaceAfter=2,
        alignment=TA_CENTER
    )
    
    # ============================================================
    # HALAMAN 1 (selalu ada)
    # ============================================================
    label_upper = label.upper()
    story.append(Paragraph(f"- LAPORAN KEUANGAN {label_upper}", title_style))
    story.append(Paragraph(data['periode'], subtitle_style))
    story.append(Spacer(1, 0.1*inch))
    
    # RINGKASAN
    story.append(Paragraph(f"- Pemasukan = {format_rupiah(data['ringkasan']['pemasukan'])}", ringkasan_style))
    story.append(Paragraph(f"- Investasi = {format_rupiah(data['ringkasan']['investasi'])}", ringkasan_style))
    story.append(Paragraph(f"- Pengeluaran = {format_rupiah(data['ringkasan']['pengeluaran'])}", ringkasan_style))
    story.append(Paragraph(f"- Saldo = {format_rupiah(data['ringkasan']['saldo'])}", ringkasan_style))
    story.append(Spacer(1, 0.08*inch))
    
    # INSIGHT
    if data['insight']:
        story.append(Paragraph("- Insight", heading_style))
        for insight in data['insight']:
            story.append(Paragraph(f"- {insight}", insight_style))
        story.append(Spacer(1, 0.08*inch))
    
    # PERBANDINGAN
    if perbandingan_data:
        story.append(Paragraph(f"- Perbandingan {perbandingan_data['label']}", heading_style))
        comp_data = [
            ['', 'Periode Ini', perbandingan_data['label']],
            ['Pemasukan', format_rupiah(data['ringkasan']['pemasukan']), format_rupiah(perbandingan_data['pemasukan'])],
            ['Pengeluaran', format_rupiah(data['ringkasan']['pengeluaran']), format_rupiah(perbandingan_data['pengeluaran'])],
            ['Investasi', format_rupiah(data['ringkasan']['investasi']), format_rupiah(perbandingan_data['investasi'])],
            ['Saldo', format_rupiah(data['ringkasan']['saldo']), format_rupiah(perbandingan_data['saldo'])]
        ]
        comp_table = Table(comp_data, colWidths=[TABLE_WIDTH*0.35, TABLE_WIDTH*0.325, TABLE_WIDTH*0.325])
        comp_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), COLOR_NAVY),
            ('TEXTCOLOR', (0,0), (-1,0), COLOR_WHITE),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 9),
            ('ALIGN', (0,0), (-1,0), 'CENTER'),
            ('BOX', (0,0), (-1,-1), 0.5, COLOR_BLACK),
            ('LINEBELOW', (0,0), (-1,0), 0.5, COLOR_BLACK),
            ('FONTSIZE', (0,1), (-1,-1), 9),
            ('ALIGN', (0,1), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BACKGROUND', (0,1), (-1,-1), COLOR_WHITE),
            ('BACKGROUND', (0,2), (0,2), COLOR_GRAY_LIGHT),
            ('BACKGROUND', (0,4), (0,4), COLOR_GRAY_LIGHT),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        story.append(comp_table)
        story.append(Spacer(1, 0.08*inch))
    
    # PENGELUARAN PER KATEGORI
    if data['pie_chart']:
        story.append(Paragraph("- Pengeluaran per Kategori", heading_style))
        kategori_data = [['Kategori', 'Nominal']]
        for item in data['pie_chart']:
            kategori_data.append([item['kategori'], format_rupiah(item['nominal'])])
        total_kategori = sum(item['nominal'] for item in data['pie_chart'])
        kategori_data.append(['Total', format_rupiah(total_kategori)])
        
        kategori_table = Table(kategori_data, colWidths=[TABLE_WIDTH*0.6, TABLE_WIDTH*0.4])
        kategori_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), COLOR_NAVY),
            ('TEXTCOLOR', (0,0), (-1,0), COLOR_WHITE),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('ALIGN', (0,0), (-1,0), 'CENTER'),
            ('ALIGN', (1,1), (1,-1), 'RIGHT'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BACKGROUND', (0,1), (-1,-1), COLOR_WHITE),
            ('GRID', (0,0), (-1,-1), 0.3, COLOR_BLACK),
            ('FONTSIZE', (0,1), (-1,-1), 9),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('FONTNAME', (0, len(kategori_data)-1), (-1, len(kategori_data)-1), 'Helvetica-Bold'),
            ('BACKGROUND', (0, len(kategori_data)-1), (-1, len(kategori_data)-1), COLOR_GRAY_LIGHT),
        ]))
        story.append(kategori_table)
    
    # ============================================================
    # HALAMAN 2: TOTAL PENGELUARAN HARIAN (jika ada)
    # ============================================================
    if show_daily and daily_data:
        story.append(PageBreak())
        story.append(Paragraph("- Total Pengeluaran Harian", heading_style))
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
        daily_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), COLOR_NAVY),
            ('TEXTCOLOR', (0,0), (-1,0), COLOR_WHITE),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BACKGROUND', (0,1), (-1,-1), COLOR_WHITE),
            ('GRID', (0,0), (-1,-1), 0.3, COLOR_BLACK),
            ('FONTSIZE', (0,1), (-1,-1), 8),
            ('BACKGROUND', (0,2), (0,2), COLOR_GRAY_LIGHT),
            ('BACKGROUND', (0,4), (0,4), COLOR_GRAY_LIGHT),
            ('FONTNAME', (0, len(daily_table_data)-1), (-1, len(daily_table_data)-1), 'Helvetica-Bold'),
            ('BACKGROUND', (0, len(daily_table_data)-1), (-1, len(daily_table_data)-1), COLOR_GRAY_LIGHT),
        ]))
        story.append(daily_table)
        story.append(Spacer(1, 0.12*inch))  # Spacer sebelum detail pengeluaran (jika digabung)
    
    # ============================================================
    # DETEKSI ADA ATAU TIDAK DATA PEMASUKAN / INVESTASI / BUDGET (halaman 3)
    # ============================================================
    has_income = bool(data['pemasukan'])
    has_invest = bool(data['investasi'])
    has_budget_page = show_budget and (data['budget'] or data['target'])
    has_page3_content = has_income or has_invest or has_budget_page
    
    # ============================================================
    # HALAMAN 3: DETAIL PEMASUKAN / INVESTASI / BUDGET (hanya jika ada konten)
    # ============================================================
    if has_page3_content:
        story.append(PageBreak())
        col_widths_5col = [TABLE_WIDTH*0.08, TABLE_WIDTH*0.17, TABLE_WIDTH*0.17, TABLE_WIDTH*0.33, TABLE_WIDTH*0.25]
        col_widths_budget = [TABLE_WIDTH*0.18, TABLE_WIDTH*0.20, TABLE_WIDTH*0.20, TABLE_WIDTH*0.20, TABLE_WIDTH*0.22]
        col_widths_3col = [TABLE_WIDTH*0.35, TABLE_WIDTH*0.325, TABLE_WIDTH*0.325]
        
        # DETAIL PEMASUKAN
        if has_income:
            story.append(Paragraph("- Detail Pemasukan", heading_style))
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
            pemasukan_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), COLOR_NAVY),
                ('TEXTCOLOR', (0,0), (-1,0), COLOR_WHITE),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 7),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('BACKGROUND', (0,1), (-1,-1), COLOR_WHITE),
                ('GRID', (0,0), (-1,-1), 0.3, COLOR_BLACK),
                ('FONTSIZE', (0,1), (-1,-1), 7),
                ('ALIGN', (4,1), (4,-1), 'RIGHT'),
                ('FONTNAME', (0, len(pemasukan_data)-1), (-1, len(pemasukan_data)-1), 'Helvetica-Bold'),
                ('BACKGROUND', (0, len(pemasukan_data)-1), (-1, len(pemasukan_data)-1), COLOR_GRAY_LIGHT),
            ]))
            story.append(pemasukan_table)
            story.append(Spacer(1, 0.1*inch))
        
        # DETAIL INVESTASI
        if has_invest:
            story.append(Paragraph("- Detail Investasi", heading_style))
            investasi_data = [['#', 'Tanggal', 'Kategori', 'Item', 'Nominal']]
            total_investasi = 0
            for i, item in enumerate(data['investasi'], 1):
                total_investasi += item['nominal']
                investasi_data.append([
                    str(i),
                    item['tanggal'],
                    item['kategori'],
                    item['item'][:25],
                    format_rupiah(item['nominal'])
                ])
            investasi_data.append(['Total', '', '', '', format_rupiah(total_investasi)])
            
            investasi_table = Table(investasi_data, colWidths=col_widths_5col)
            investasi_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), COLOR_NAVY),
                ('TEXTCOLOR', (0,0), (-1,0), COLOR_WHITE),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 7),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('BACKGROUND', (0,1), (-1,-1), COLOR_WHITE),
                ('GRID', (0,0), (-1,-1), 0.3, COLOR_BLACK),
                ('FONTSIZE', (0,1), (-1,-1), 7),
                ('ALIGN', (4,1), (4,-1), 'RIGHT'),
                ('FONTNAME', (0, len(investasi_data)-1), (-1, len(investasi_data)-1), 'Helvetica-Bold'),
                ('BACKGROUND', (0, len(investasi_data)-1), (-1, len(investasi_data)-1), COLOR_GRAY_LIGHT),
            ]))
            story.append(investasi_table)
            story.append(Spacer(1, 0.1*inch))





        
        
        # BUDGET & TARGET (hanya bulanan)
        if data['budget']:
    budget_data = [['Kategori', 'Budget', 'Realisasi', 'Sisa', 'Status']]
    for item in data['budget']:
        if item['budget'] > 0:  # ← hanya tampilkan jika budget > 0
            status_text = '[OK]' if item['status'] == 'Aman' else '[!]'
            budget_data.append([
                item['kategori'],
                format_rupiah(item['budget']),
                format_rupiah(item['realisasi']),
                format_rupiah(item['sisa']),
                f"{status_text} {item['status']}"
            ])
    # Kalau cuma header doang (tidak ada data), skip
    if len(budget_data) > 1:
    # tampilkan tabel
    budget_table = Table(budget_data, colWidths=col_widths_budget)
    budget_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), COLOR_NAVY),
        ('TEXTCOLOR', (0,0), (-1,0), COLOR_WHITE),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 7),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BACKGROUND', (0,1), (-1,-1), COLOR_WHITE),
        ('GRID', (0,0), (-1,-1), 0.3, COLOR_BLACK),
        ('FONTSIZE', (0,1), (-1,-1), 7),
    ]))
    story.append(budget_table)
    story.append(Spacer(1, 0.08*inch))
            
            if data['target']:
                story.append(Paragraph("- Target", heading_style))
                target_data = [['Target', 'Realisasi', 'Sisa']]
                for item in data['target']:
                    target_data.append([item['target'], item['realisasi'], item['sisa']])
                target_table = Table(target_data, colWidths=col_widths_3col)
                target_table.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), COLOR_NAVY),
                    ('TEXTCOLOR', (0,0), (-1,0), COLOR_WHITE),
                    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0,0), (-1,-1), 8),
                    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                    ('BACKGROUND', (0,1), (-1,-1), COLOR_WHITE),
                    ('GRID', (0,0), (-1,-1), 0.3, COLOR_BLACK),
                    ('FONTSIZE', (0,1), (-1,-1), 8),
                ]))
                story.append(target_table)
    
    # ============================================================
    # DETAIL PENGELUARAN (DITARUH SESUAI KONDISI)
    # ============================================================
    if data['pengeluaran']:
        # Jika tidak ada konten halaman 3, dan (ada daily data atau ini harian),
        # maka Detail Pengeluaran ditaruh di halaman yang sama (tanpa PageBreak)
        should_append_here = (not has_page3_content) and (show_daily and daily_data)
        
        if not should_append_here:
            # Kondisi lain: tambahkan PageBreak (karena ada halaman 3 atau tidak ada daily)
            story.append(PageBreak())
        
        story.append(Paragraph("- Detail Pengeluaran", heading_style))
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
        pengeluaran_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), COLOR_NAVY),
            ('TEXTCOLOR', (0,0), (-1,0), COLOR_WHITE),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 7),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BACKGROUND', (0,1), (-1,-1), COLOR_WHITE),
            ('GRID', (0,0), (-1,-1), 0.3, COLOR_BLACK),
            ('FONTSIZE', (0,1), (-1,-1), 7),
            ('ALIGN', (4,1), (4,-1), 'RIGHT'),
            ('FONTNAME', (0, len(pengeluaran_data)-1), (-1, len(pengeluaran_data)-1), 'Helvetica-Bold'),
            ('BACKGROUND', (0, len(pengeluaran_data)-1), (-1, len(pengeluaran_data)-1), COLOR_GRAY_LIGHT),
        ]))
        story.append(pengeluaran_table)
    
    # ============================================================
    # BUILD
    # ============================================================
    doc.build(story)
    return filename
