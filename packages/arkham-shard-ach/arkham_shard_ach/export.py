"""Export ACH matrices to various formats."""

import csv
import json
import logging
from io import StringIO
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
@media print { body { -webkit-print-color-adjust: exact; } }
body { font-family: Segoe UI, Tahoma, sans-serif; font-size: 11pt; line-height: 1.4; color: #1a1a1a; max-width: 8.5in; margin: 0 auto; padding: 20px; }
.header { text-align: center; border-bottom: 3px solid #1e3a5f; padding-bottom: 15px; margin-bottom: 20px; }
.header h1 { font-size: 22pt; color: #1e3a5f; margin: 0 0 5px 0; }
.header h2 { font-size: 14pt; color: #444; margin: 0; }
.focus { background: #f5f7fa; padding: 12px; border-left: 4px solid #1e3a5f; margin-bottom: 20px; font-style: italic; }
.summary { background: #e8f4e8; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
.summary .lead-name { font-weight: 600; color: #1e5631; }
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
.disclosure { background: #e3f2fd; padding: 10px; border-radius: 5px; font-size: 9pt; margin-top: 20px; }
.footer { margin-top: 30px; padding-top: 10px; border-top: 1px solid #ccc; font-size: 8pt; color: #666; text-align: center; }
'''

    @staticmethod
    def export_html(matrix: ACHMatrix) -> MatrixExport:
        """Export matrix as professional HTML report for PDF generation."""
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
        
        html.append('<div class="legend">')
        html.append('<span class="cc">CC=Consistent</span>')
        html.append('<span class="c">C=Somewhat</span>')
        html.append('<span class="n">N=Neutral</span>')
        html.append('<span class="i">I=Inconsistent</span>')
        html.append('<span class="ii">II=Very Inconsistent</span>')
        html.append('</div>')        
        html.append(chr(60) + "table" + chr(62))
        html.append(chr(60) + "thead" + chr(62) + chr(60) + "tr" + chr(62) + chr(60) + "th" + chr(62) + "Evidence" + chr(60) + "/th" + chr(62))
        for i, h in enumerate(sorted_hypotheses, 1):
            html.append(f"{chr(60)}th title={chr(34)}{h.title}{chr(34)}{chr(62)}H{i}{chr(60)}/th{chr(62)}")
        html.append(chr(60) + "/tr" + chr(62) + chr(60) + "/thead" + chr(62) + chr(60) + "tbody" + chr(62))
        
        for i, ev in enumerate(sorted_evidence, 1):
            html.append(f"{chr(60)}tr{chr(62)}{chr(60)}td{chr(62)}E{i}{chr(60)}/td{chr(62)}")
            for h in sorted_hypotheses:
                rating = matrix.get_rating(ev.id, h.id)
                if rating:
                    rv = rating.rating.value
                    disp = MatrixExporter.RATING_DISPLAY.get(rv, rv)
                    css = MatrixExporter.RATING_CSS.get(rv, "n")
                    html.append(f"{chr(60)}td class={chr(34)}{css}{chr(34)}{chr(62)}{disp}{chr(60)}/td{chr(62)}")
                else:
                    html.append(chr(60) + "td class=" + chr(34) + "na" + chr(34) + chr(62) + "-" + chr(60) + "/td" + chr(62))
            html.append(chr(60) + "/tr" + chr(62))
        html.append(chr(60) + "/tbody" + chr(62) + chr(60) + "/table" + chr(62))        
        if sorted_scores:
            html.append(chr(60) + "div class=" + chr(34) + "scores" + chr(34) + chr(62) + chr(60) + "h3" + chr(62) + "Hypothesis Scores" + chr(60) + "/h3" + chr(62))
            html.append(chr(60) + "table" + chr(62) + chr(60) + "thead" + chr(62) + chr(60) + "tr" + chr(62) + chr(60) + "th" + chr(62) + "Rank" + chr(60) + "/th" + chr(62) + chr(60) + "th" + chr(62) + "Hypothesis" + chr(60) + "/th" + chr(62) + chr(60) + "th" + chr(62) + "Inconsistencies" + chr(60) + "/th" + chr(62) + chr(60) + "th" + chr(62) + "Score" + chr(60) + "/th" + chr(62) + chr(60) + "/tr" + chr(62) + chr(60) + "/thead" + chr(62) + chr(60) + "tbody" + chr(62))
            for score in sorted_scores:
                hyp = matrix.get_hypothesis(score.hypothesis_id)
                if hyp:
                    cls = " class=" + chr(34) + "lead-row" + chr(34) if hyp.is_lead else ""
                    html.append(f"{chr(60)}tr{cls}{chr(62)}{chr(60)}td{chr(62)}{score.rank}{chr(60)}/td{chr(62)}{chr(60)}td{chr(62)}{hyp.title}{chr(60)}/td{chr(62)}")
                    html.append(f"{chr(60)}td{chr(62)}{score.inconsistency_count}{chr(60)}/td{chr(62)}{chr(60)}td{chr(62)}{score.normalized_score:.1f}{chr(60)}/td{chr(62)}{chr(60)}/tr{chr(62)}")
            html.append(chr(60) + "/tbody" + chr(62) + chr(60) + "/table" + chr(62) + chr(60) + "/div" + chr(62))
        
        html.append(chr(60) + "div class=" + chr(34) + "disclosure" + chr(34) + chr(62))
        html.append(chr(60) + "strong" + chr(62) + "AI Disclosure:" + chr(60) + "/strong" + chr(62) + " This analysis may include AI-assisted hypothesis generation and rating suggestions.")
        html.append(chr(60) + "/div" + chr(62))
        
        ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        html.append(f"{chr(60)}div class={chr(34)}footer{chr(34)}{chr(62)}Generated: {ts} | ID: {matrix.id} | ACH - SHATTERED Platform{chr(60)}/div{chr(62)}")
        html.append(chr(60) + "/body" + chr(62) + chr(60) + "/html" + chr(62))
        
        return MatrixExport(matrix=matrix, format="html", content=chr(10).join(html))
    @staticmethod
    def export_markdown(matrix: ACHMatrix) -> MatrixExport:
        md = []
        md.append(f"# {matrix.title}")
        if matrix.description:
            md.append(f"{matrix.description}")
        md.append(f"**Status:** {matrix.status.value}  ")
        md.append(f"**Created:** {matrix.created_at.strftime("%Y-%m-%d %H:%M")}")
        md.append("")
        md.append("## Matrix")
        md.append("")
        sorted_hypotheses = sorted(matrix.hypotheses, key=lambda x: x.column_index)
        sorted_evidence = sorted(matrix.evidence, key=lambda x: x.row_index)
        header = ["Evidence"]
        for h in sorted_hypotheses:
            lead_marker = " (LEAD)" if h.is_lead else ""
            header.append(f"{h.title}{lead_marker}")
        md.append("| " + " | ".join(header) + " |")
        md.append("| " + " | ".join(["---"] * len(header)) + " |")
        for evidence in sorted_evidence:
            row = [evidence.description]
            for hypothesis in sorted_hypotheses:
                rating = matrix.get_rating(evidence.id, hypothesis.id)
                row.append(rating.rating.value if rating else "N/A")
            md.append("| " + " | ".join(row) + " |")
        if matrix.scores:
            md.append("")
            md.append("## Hypothesis Scores")
            md.append("")
            md.append("| Rank | Hypothesis | Inconsistencies | Weighted Score | Normalized Score |")
            md.append("| --- | --- | --- | --- | --- |")
            sorted_scores = sorted(matrix.scores, key=lambda x: x.rank)
            for score in sorted_scores:
                hypothesis = matrix.get_hypothesis(score.hypothesis_id)
                if hypothesis:
                    md.append(f"| {score.rank} | {hypothesis.title} | {score.inconsistency_count} | {score.weighted_score:.3f} | {score.normalized_score:.1f} |")
        md.append("")
        md.append("---")
        md.append(f"*Generated: {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")} UTC*")
        return MatrixExport(matrix=matrix, format="markdown", content=chr(10).join(md))

    @staticmethod
    def export(matrix: ACHMatrix, format: str = "json") -> MatrixExport:
        exporters = {
            "json": MatrixExporter.export_json,
            "csv": MatrixExporter.export_csv,
            "html": MatrixExporter.export_html,
            "markdown": MatrixExporter.export_markdown,
            "md": MatrixExporter.export_markdown,
        }
        exporter = exporters.get(format.lower())
        if not exporter:
            logger.warning(f"Unknown export format: {format}, defaulting to JSON")
            exporter = MatrixExporter.export_json
        return exporter(matrix)