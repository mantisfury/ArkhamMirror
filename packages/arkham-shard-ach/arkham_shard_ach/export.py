"""Export ACH matrices to various formats."""

import csv
import json
import logging
from io import StringIO, BytesIO
from datetime import datetime

from .models import ACHMatrix, MatrixExport

logger = logging.getLogger(__name__)


class MatrixExporter:
    """Export ACH matrices to different formats."""

    RATING_DISPLAY = {"++": "CC", "+": "C", "N": "N", "-": "I", "--": "II", "N/A": "N/A"}
    RATING_CSS = {"++": "cc", "+": "c", "N": "n", "-": "i", "--": "ii", "N/A": "na"}

    @staticmethod
    def export_json(matrix: ACHMatrix) -> MatrixExport:
        """Export matrix as JSON."""
        data = {
            "metadata": {
                "id": matrix.id,
                "title": matrix.title,
                "description": matrix.description,
                "status": matrix.status.value,
                "created_at": matrix.created_at.isoformat(),
                "updated_at": matrix.updated_at.isoformat(),
                "created_by": matrix.created_by,
                "project_id": matrix.project_id,
                "tags": matrix.tags,
            },
            "hypotheses": [
                {
                    "id": h.id,
                    "title": h.title,
                    "description": h.description,
                    "column_index": h.column_index,
                    "is_lead": h.is_lead,
                }
                for h in sorted(matrix.hypotheses, key=lambda x: x.column_index)
            ],
            "evidence": [
                {
                    "id": e.id,
                    "description": e.description,
                    "source": e.source,
                    "type": e.evidence_type.value,
                    "credibility": e.credibility,
                    "relevance": e.relevance,
                    "row_index": e.row_index,
                }
                for e in sorted(matrix.evidence, key=lambda x: x.row_index)
            ],
            "ratings": [
                {
                    "evidence_id": r.evidence_id,
                    "hypothesis_id": r.hypothesis_id,
                    "rating": r.rating.value,
                    "reasoning": r.reasoning,
                    "confidence": r.confidence,
                }
                for r in matrix.ratings
            ],
            "scores": [
                {
                    "hypothesis_id": s.hypothesis_id,
                    "consistency_score": s.consistency_score,
                    "inconsistency_count": s.inconsistency_count,
                    "weighted_score": s.weighted_score,
                    "normalized_score": s.normalized_score,
                    "rank": s.rank,
                }
                for s in sorted(matrix.scores, key=lambda x: x.rank)
            ],
        }
        json_str = json.dumps(data, indent=2)
        return MatrixExport(matrix=matrix, format="json", content=json_str)

    @staticmethod
    def export_csv(matrix: ACHMatrix) -> MatrixExport:
        """Export matrix as CSV."""
        output = StringIO()
        writer = csv.writer(output)
        header = ["Evidence"]
        sorted_hypotheses = sorted(matrix.hypotheses, key=lambda x: x.column_index)
        for h in sorted_hypotheses:
            header.append(h.title)
        header.extend(["Source", "Type", "Credibility", "Relevance"])
        writer.writerow(header)
        sorted_evidence = sorted(matrix.evidence, key=lambda x: x.row_index)
        for evidence in sorted_evidence:
            row = [evidence.description]
            for hypothesis in sorted_hypotheses:
                rating = matrix.get_rating(evidence.id, hypothesis.id)
                row.append(rating.rating.value if rating else "N/A")
            row.extend([evidence.source, evidence.evidence_type.value, f"{evidence.credibility:.2f}", f"{evidence.relevance:.2f}"])
            writer.writerow(row)
        writer.writerow([])
        writer.writerow(["Scores"])
        writer.writerow(["Hypothesis", "Rank", "Inconsistencies", "Weighted Score", "Normalized Score"])
        sorted_scores = sorted(matrix.scores, key=lambda x: x.rank)
        for score in sorted_scores:
            hypothesis = matrix.get_hypothesis(score.hypothesis_id)
            if hypothesis:
                writer.writerow([hypothesis.title, score.rank, score.inconsistency_count, f"{score.weighted_score:.3f}", f"{score.normalized_score:.1f}"])
        csv_content = output.getvalue()
        output.close()
        return MatrixExport(matrix=matrix, format="csv", content=csv_content)

    @staticmethod
    def _get_css() -> str:
        return '''
@page { size: letter; margin: 0.75in; }
@media print {
  body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  .no-print { display: none; }
}
body { font-family: Segoe UI, Tahoma, sans-serif; font-size: 11pt; line-height: 1.4; color: #1a1a1a; max-width: 8.5in; margin: 0 auto; padding: 20px; }
.header { text-align: center; border-bottom: 3px solid #1e3a5f; padding-bottom: 15px; margin-bottom: 20px; }
.header h1 { font-size: 22pt; color: #1e3a5f; margin: 0 0 5px 0; }
.header h2 { font-size: 14pt; color: #444; margin: 0; }
.focus { background: #f5f7fa; padding: 12px; border-left: 4px solid #1e3a5f; margin-bottom: 20px; font-style: italic; }
.summary { background: #e8f4e8; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
.summary .lead-name { font-weight: 600; color: #1e5631; }
.section { margin-bottom: 25px; }
.section h3 { color: #1e3a5f; border-bottom: 2px solid #1e3a5f; padding-bottom: 5px; margin-bottom: 10px; }
.hypothesis-item, .evidence-item { background: #f9fafb; padding: 10px 15px; border-left: 3px solid #1e3a5f; margin-bottom: 10px; }
.hypothesis-item h4, .evidence-item h4 { margin: 0 0 5px 0; color: #1e3a5f; }
.hypothesis-item p, .evidence-item p { margin: 0; font-size: 10pt; color: #444; }
.evidence-meta { font-size: 9pt; color: #666; margin-top: 5px; }
table { width: 100%; border-collapse: collapse; font-size: 9pt; margin-bottom: 15px; }
th { background: #1e3a5f; color: white; padding: 8px; text-align: center; font-size: 8pt; }
th:first-child { text-align: left; }
td { padding: 6px; border: 1px solid #ccc; text-align: center; }
td:first-child { text-align: left; font-weight: 500; }
.cc { background: #2e7d32; color: white; font-weight: 600; }
.c { background: #81c784; }
.n { background: #fff; color: #666; }
.i { background: #ffb74d; }
.ii { background: #e53935; color: white; font-weight: 600; }
.na { background: #e0e0e0; color: #666; }
.legend { display: flex; justify-content: center; gap: 15px; font-size: 8pt; margin-bottom: 15px; flex-wrap: wrap; }
.legend span { padding: 2px 8px; border: 1px solid #999; }
.scores { margin-top: 20px; }
.lead-row { background-color: #FFFDE7; }
.disclosure { background: #e3f2fd; padding: 12px 15px; border-radius: 5px; font-size: 9pt; margin-top: 20px; border-left: 4px solid #1976d2; }
.disclosure strong { color: #1565c0; }
.footer { margin-top: 30px; padding-top: 10px; border-top: 1px solid #ccc; font-size: 8pt; color: #666; text-align: center; }
.print-btn { position: fixed; top: 20px; right: 20px; padding: 10px 20px; background: #1e3a5f; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 12pt; }
.print-btn:hover { background: #2d4a6f; }
'''

    @staticmethod
    def export_html(matrix: ACHMatrix) -> MatrixExport:
        """Export matrix as professional HTML report with full descriptions."""
        sorted_hypotheses = sorted(matrix.hypotheses, key=lambda x: x.column_index)
        sorted_evidence = sorted(matrix.evidence, key=lambda x: x.row_index)
        sorted_scores = sorted(matrix.scores, key=lambda x: x.rank) if matrix.scores else []

        lead_hypothesis = lead_score = None
        for score in sorted_scores:
            h = matrix.get_hypothesis(score.hypothesis_id)
            if h and h.is_lead:
                lead_hypothesis, lead_score = h, score
                break
        if not lead_hypothesis and sorted_scores:
            lead_score = sorted_scores[0]
            lead_hypothesis = matrix.get_hypothesis(lead_score.hypothesis_id)

        html = ['<!DOCTYPE html>', '<html>', '<head>', '<meta charset="UTF-8">']
        html.append(f'<title>ACH Analysis Report: {matrix.title}</title>')
        html.append('<style>' + MatrixExporter._get_css() + '</style>')
        html.append('</head><body>')

        # Print button (hidden when printing)
        html.append('<button class="print-btn no-print" onclick="window.print()">Print / Save as PDF</button>')

        html.append('<div class="header">')
        html.append('<h1>ACH Analysis Report</h1>')
        html.append(f'<h2>{matrix.title}</h2>')
        html.append('</div>')

        focus = matrix.description or "No focus question specified"
        html.append(f'<div class="focus"><strong>Focus Question:</strong> {focus}</div>')

        if lead_hypothesis and lead_score:
            html.append('<div class="summary">')
            html.append(f'<p>Based on the analysis, <span class="lead-name">{lead_hypothesis.title}</span> ')
            html.append(f'is the leading hypothesis with {lead_score.inconsistency_count} inconsistencies ')
            html.append(f'and a normalized score of {lead_score.normalized_score:.1f}.</p>')
            html.append('</div>')

        # Hypotheses Section
        html.append('<div class="section">')
        html.append('<h3>Hypotheses</h3>')
        for i, h in enumerate(sorted_hypotheses, 1):
            lead_marker = " (LEAD)" if h.is_lead else ""
            html.append(f'<div class="hypothesis-item">')
            html.append(f'<h4>H{i}: {h.title}{lead_marker}</h4>')
            if h.description:
                html.append(f'<p>{h.description}</p>')
            html.append('</div>')
        html.append('</div>')

        # Evidence Section
        html.append('<div class="section">')
        html.append('<h3>Evidence</h3>')
        for i, ev in enumerate(sorted_evidence, 1):
            html.append(f'<div class="evidence-item">')
            html.append(f'<h4>E{i}: {ev.description[:100]}{"..." if len(ev.description) > 100 else ""}</h4>')
            html.append(f'<p>{ev.description}</p>')
            meta_parts = []
            if ev.source:
                meta_parts.append(f'Source: {ev.source}')
            meta_parts.append(f'Type: {ev.evidence_type.value}')
            meta_parts.append(f'Credibility: {ev.credibility:.1f}')
            html.append(f'<div class="evidence-meta">{" | ".join(meta_parts)}</div>')
            html.append('</div>')
        html.append('</div>')

        # Matrix Section
        html.append('<div class="section">')
        html.append('<h3>Consistency Matrix</h3>')

        html.append('<div class="legend">')
        html.append('<span class="cc">CC=Very Consistent</span>')
        html.append('<span class="c">C=Consistent</span>')
        html.append('<span class="n">N=Neutral</span>')
        html.append('<span class="i">I=Inconsistent</span>')
        html.append('<span class="ii">II=Very Inconsistent</span>')
        html.append('</div>')

        html.append('<table>')
        html.append('<thead><tr><th>Evidence</th>')
        for i, h in enumerate(sorted_hypotheses, 1):
            html.append(f'<th title="{h.title}">H{i}</th>')
        html.append('</tr></thead><tbody>')

        for i, ev in enumerate(sorted_evidence, 1):
            html.append(f'<tr><td>E{i}</td>')
            for h in sorted_hypotheses:
                rating = matrix.get_rating(ev.id, h.id)
                if rating:
                    rv = rating.rating.value
                    disp = MatrixExporter.RATING_DISPLAY.get(rv, rv)
                    css = MatrixExporter.RATING_CSS.get(rv, "n")
                    html.append(f'<td class="{css}">{disp}</td>')
                else:
                    html.append('<td class="na">-</td>')
            html.append('</tr>')
        html.append('</tbody></table>')
        html.append('</div>')

        # Scores Section - list format for better readability
        if sorted_scores:
            html.append('<div class="section scores">')
            html.append('<h3>Hypothesis Scores</h3>')
            html.append('<p style="font-size:10pt;color:#666;margin-bottom:10px;">Ranked by fewest inconsistencies (lower is better):</p>')
            for score in sorted_scores:
                hyp = matrix.get_hypothesis(score.hypothesis_id)
                if hyp:
                    lead_style = 'background:#FFFDE7;' if hyp.is_lead else ''
                    html.append(f'<div style="padding:10px 15px;border-left:4px solid #1e3a5f;margin-bottom:8px;background:#f9fafb;{lead_style}">')
                    html.append(f'<div style="font-weight:600;color:#1e3a5f;margin-bottom:4px;">#{score.rank} — {hyp.title}</div>')
                    html.append(f'<div style="font-size:9pt;color:#666;">Inconsistencies: {score.inconsistency_count} | Score: {score.normalized_score:.1f}</div>')
                    html.append('</div>')
            html.append('</div>')

        # Disclosure
        html.append('<div class="disclosure">')
        html.append('<strong>AI Assistance Disclosure:</strong> This analysis may include AI-assisted ')
        html.append('hypothesis generation, evidence suggestions, and rating recommendations. ')
        html.append('All AI-generated content was reviewed and explicitly accepted by a human analyst ')
        html.append('before inclusion in this report. The final analytical judgments and conclusions ')
        html.append('represent human decision-making informed by AI assistance.')
        html.append('</div>')

        ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        html.append(f'<div class="footer">Generated: {ts} | ID: {matrix.id} | ACH Analysis - SHATTERED Platform</div>')
        html.append('</body></html>')

        return MatrixExport(matrix=matrix, format="html", content="\n".join(html))

    @staticmethod
    def export_pdf(matrix: ACHMatrix) -> MatrixExport:
        """Export matrix as PDF using ReportLab."""
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.platypus import (
                SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                PageBreak, HRFlowable
            )
            from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
        except ImportError:
            logger.error("ReportLab not installed, falling back to HTML")
            return MatrixExporter.export_html(matrix)

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch,
        )

        # Styles
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(
            name='Title_Custom',
            parent=styles['Title'],
            fontSize=22,
            textColor=colors.HexColor('#1e3a5f'),
            spaceAfter=6,
        ))
        styles.add(ParagraphStyle(
            name='Subtitle',
            parent=styles['Normal'],
            fontSize=14,
            textColor=colors.HexColor('#444444'),
            alignment=TA_CENTER,
            spaceAfter=20,
        ))
        styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#1e3a5f'),
            spaceBefore=15,
            spaceAfter=10,
            borderPadding=5,
        ))
        styles.add(ParagraphStyle(
            name='FocusQuestion',
            parent=styles['Normal'],
            fontSize=11,
            fontName='Helvetica-Oblique',
            backColor=colors.HexColor('#f5f7fa'),
            borderPadding=10,
            leftIndent=10,
            spaceAfter=15,
        ))
        styles.add(ParagraphStyle(
            name='ItemTitle',
            parent=styles['Normal'],
            fontSize=11,
            fontName='Helvetica-Bold',
            textColor=colors.HexColor('#1e3a5f'),
            spaceBefore=8,
            spaceAfter=3,
        ))
        styles.add(ParagraphStyle(
            name='ItemBody',
            parent=styles['Normal'],
            fontSize=10,
            alignment=TA_JUSTIFY,
            spaceAfter=5,
        ))
        styles.add(ParagraphStyle(
            name='ItemMeta',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#666666'),
            spaceAfter=10,
        ))
        styles.add(ParagraphStyle(
            name='Disclosure',
            parent=styles['Normal'],
            fontSize=9,
            backColor=colors.HexColor('#e3f2fd'),
            borderPadding=10,
            spaceBefore=20,
            spaceAfter=10,
            alignment=TA_JUSTIFY,
        ))
        styles.add(ParagraphStyle(
            name='Footer',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#666666'),
            alignment=TA_CENTER,
        ))

        story = []

        sorted_hypotheses = sorted(matrix.hypotheses, key=lambda x: x.column_index)
        sorted_evidence = sorted(matrix.evidence, key=lambda x: x.row_index)
        sorted_scores = sorted(matrix.scores, key=lambda x: x.rank) if matrix.scores else []

        # Title
        story.append(Paragraph("ACH Analysis Report", styles['Title_Custom']))
        story.append(Paragraph(matrix.title, styles['Subtitle']))
        story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#1e3a5f')))
        story.append(Spacer(1, 15))

        # Focus Question
        focus = matrix.description or "No focus question specified"
        story.append(Paragraph(f"<b>Focus Question:</b> {focus}", styles['FocusQuestion']))

        # Lead Hypothesis Summary
        lead_hypothesis = lead_score = None
        for score in sorted_scores:
            h = matrix.get_hypothesis(score.hypothesis_id)
            if h and h.is_lead:
                lead_hypothesis, lead_score = h, score
                break
        if not lead_hypothesis and sorted_scores:
            lead_score = sorted_scores[0]
            lead_hypothesis = matrix.get_hypothesis(lead_score.hypothesis_id)

        if lead_hypothesis and lead_score:
            summary_text = (
                f"Based on the analysis, <b>{lead_hypothesis.title}</b> is the leading hypothesis "
                f"with {lead_score.inconsistency_count} inconsistencies and a normalized score "
                f"of {lead_score.normalized_score:.1f}."
            )
            story.append(Paragraph(summary_text, styles['Normal']))
            story.append(Spacer(1, 15))

        # Hypotheses Section
        story.append(Paragraph("Hypotheses", styles['SectionHeader']))
        for i, h in enumerate(sorted_hypotheses, 1):
            lead_marker = " (LEAD)" if h.is_lead else ""
            story.append(Paragraph(f"H{i}: {h.title}{lead_marker}", styles['ItemTitle']))
            if h.description:
                story.append(Paragraph(h.description, styles['ItemBody']))
            story.append(Spacer(1, 5))

        # Evidence Section
        story.append(Paragraph("Evidence", styles['SectionHeader']))
        for i, ev in enumerate(sorted_evidence, 1):
            story.append(Paragraph(f"E{i}: Evidence Item", styles['ItemTitle']))
            story.append(Paragraph(ev.description, styles['ItemBody']))
            meta_parts = []
            if ev.source:
                meta_parts.append(f"Source: {ev.source}")
            meta_parts.append(f"Type: {ev.evidence_type.value}")
            meta_parts.append(f"Credibility: {ev.credibility:.1f}")
            story.append(Paragraph(" | ".join(meta_parts), styles['ItemMeta']))

        # Matrix Section
        story.append(Paragraph("Consistency Matrix", styles['SectionHeader']))

        # Legend
        legend_text = "CC=Very Consistent | C=Consistent | N=Neutral | I=Inconsistent | II=Very Inconsistent"
        story.append(Paragraph(legend_text, styles['ItemMeta']))
        story.append(Spacer(1, 10))

        # Build matrix table
        header_row = ['Evidence'] + [f'H{i+1}' for i in range(len(sorted_hypotheses))]
        table_data = [header_row]

        rating_colors = {
            '++': colors.HexColor('#2e7d32'),
            '+': colors.HexColor('#81c784'),
            'N': colors.white,
            '-': colors.HexColor('#ffb74d'),
            '--': colors.HexColor('#e53935'),
            'N/A': colors.HexColor('#e0e0e0'),
        }
        rating_text_colors = {
            '++': colors.white,
            '--': colors.white,
        }

        cell_styles = []
        for row_idx, ev in enumerate(sorted_evidence, 1):
            row = [f'E{row_idx}']
            for col_idx, h in enumerate(sorted_hypotheses, 1):
                rating = matrix.get_rating(ev.id, h.id)
                if rating:
                    rv = rating.rating.value
                    disp = MatrixExporter.RATING_DISPLAY.get(rv, rv)
                    row.append(disp)
                    bg_color = rating_colors.get(rv, colors.white)
                    txt_color = rating_text_colors.get(rv, colors.black)
                    cell_styles.append(('BACKGROUND', (col_idx, row_idx), (col_idx, row_idx), bg_color))
                    cell_styles.append(('TEXTCOLOR', (col_idx, row_idx), (col_idx, row_idx), txt_color))
                else:
                    row.append('-')
                    cell_styles.append(('BACKGROUND', (col_idx, row_idx), (col_idx, row_idx), colors.HexColor('#e0e0e0')))
            table_data.append(row)

        # Calculate column widths
        available_width = 7 * inch
        first_col_width = 0.8 * inch
        other_col_width = (available_width - first_col_width) / len(sorted_hypotheses) if sorted_hypotheses else 1*inch
        col_widths = [first_col_width] + [other_col_width] * len(sorted_hypotheses)

        matrix_table = Table(table_data, colWidths=col_widths)
        matrix_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a5f')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ] + cell_styles))
        story.append(matrix_table)
        story.append(Spacer(1, 15))

        # Scores Section - use list format for better readability with long titles
        if sorted_scores:
            story.append(Paragraph("Hypothesis Scores", styles['SectionHeader']))
            story.append(Paragraph(
                "Ranked by fewest inconsistencies with the evidence (lower is better):",
                styles['ItemMeta']
            ))
            story.append(Spacer(1, 8))

            for score in sorted_scores:
                hyp = matrix.get_hypothesis(score.hypothesis_id)
                if hyp:
                    # Rank badge and title
                    rank_text = f"<b>#{score.rank}</b> — {hyp.title}"
                    story.append(Paragraph(rank_text, styles['ItemTitle']))

                    # Score details
                    details = (
                        f"Inconsistencies: {score.inconsistency_count} | "
                        f"Score: {score.normalized_score:.1f}"
                    )
                    story.append(Paragraph(details, styles['ItemMeta']))
                    story.append(Spacer(1, 6))

        # Disclosure
        disclosure_text = (
            "<b>AI Assistance Disclosure:</b> This analysis may include AI-assisted hypothesis generation, "
            "evidence suggestions, and rating recommendations. All AI-generated content was reviewed and "
            "explicitly accepted by a human analyst before inclusion in this report. The final analytical "
            "judgments and conclusions represent human decision-making informed by AI assistance."
        )
        story.append(Paragraph(disclosure_text, styles['Disclosure']))

        # Footer
        story.append(Spacer(1, 20))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#cccccc')))
        ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        footer_text = f"Generated: {ts} | ID: {matrix.id} | ACH Analysis - SHATTERED Platform"
        story.append(Paragraph(footer_text, styles['Footer']))

        # Build PDF
        doc.build(story)
        pdf_content = buffer.getvalue()
        buffer.close()

        return MatrixExport(matrix=matrix, format="pdf", content=pdf_content)

    @staticmethod
    def export_markdown(matrix: ACHMatrix) -> MatrixExport:
        """Export matrix as Markdown with full descriptions."""
        md = []
        md.append(f"# {matrix.title}")
        if matrix.description:
            md.append(f"\n**Focus Question:** {matrix.description}")
        md.append(f"\n**Status:** {matrix.status.value}  ")
        md.append(f"**Created:** {matrix.created_at.strftime('%Y-%m-%d %H:%M')}")

        # Hypotheses
        md.append("\n## Hypotheses\n")
        sorted_hypotheses = sorted(matrix.hypotheses, key=lambda x: x.column_index)
        for i, h in enumerate(sorted_hypotheses, 1):
            lead_marker = " **(LEAD)**" if h.is_lead else ""
            md.append(f"### H{i}: {h.title}{lead_marker}\n")
            if h.description:
                md.append(f"{h.description}\n")

        # Evidence
        md.append("\n## Evidence\n")
        sorted_evidence = sorted(matrix.evidence, key=lambda x: x.row_index)
        for i, ev in enumerate(sorted_evidence, 1):
            md.append(f"### E{i}\n")
            md.append(f"{ev.description}\n")
            meta_parts = []
            if ev.source:
                meta_parts.append(f"Source: {ev.source}")
            meta_parts.append(f"Type: {ev.evidence_type.value}")
            meta_parts.append(f"Credibility: {ev.credibility:.1f}")
            md.append(f"*{' | '.join(meta_parts)}*\n")

        # Matrix
        md.append("\n## Consistency Matrix\n")
        header = ["Evidence"]
        for h in sorted_hypotheses:
            lead_marker = " (LEAD)" if h.is_lead else ""
            header.append(f"{h.title}{lead_marker}")
        md.append("| " + " | ".join(header) + " |")
        md.append("| " + " | ".join(["---"] * len(header)) + " |")
        for i, evidence in enumerate(sorted_evidence, 1):
            row = [f"E{i}"]
            for hypothesis in sorted_hypotheses:
                rating = matrix.get_rating(evidence.id, hypothesis.id)
                row.append(rating.rating.value if rating else "N/A")
            md.append("| " + " | ".join(row) + " |")

        # Scores
        if matrix.scores:
            md.append("\n## Hypothesis Scores\n")
            md.append("| Rank | Hypothesis | Inconsistencies | Weighted Score | Normalized Score |")
            md.append("| --- | --- | --- | --- | --- |")
            sorted_scores = sorted(matrix.scores, key=lambda x: x.rank)
            for score in sorted_scores:
                hypothesis = matrix.get_hypothesis(score.hypothesis_id)
                if hypothesis:
                    md.append(f"| {score.rank} | {hypothesis.title} | {score.inconsistency_count} | {score.weighted_score:.3f} | {score.normalized_score:.1f} |")

        # Disclosure
        md.append("\n---\n")
        md.append("**AI Assistance Disclosure:** This analysis may include AI-assisted hypothesis generation, ")
        md.append("evidence suggestions, and rating recommendations. All AI-generated content was reviewed and ")
        md.append("explicitly accepted by a human analyst before inclusion in this report.\n")
        md.append(f"\n*Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC*")

        return MatrixExport(matrix=matrix, format="markdown", content="\n".join(md))

    @staticmethod
    def export(matrix: ACHMatrix, format: str = "json") -> MatrixExport:
        """Export matrix in the specified format."""
        exporters = {
            "json": MatrixExporter.export_json,
            "csv": MatrixExporter.export_csv,
            "html": MatrixExporter.export_html,
            "pdf": MatrixExporter.export_pdf,
            "markdown": MatrixExporter.export_markdown,
            "md": MatrixExporter.export_markdown,
        }
        exporter = exporters.get(format.lower())
        if not exporter:
            logger.warning(f"Unknown export format: {format}, defaulting to JSON")
            exporter = MatrixExporter.export_json
        return exporter(matrix)
