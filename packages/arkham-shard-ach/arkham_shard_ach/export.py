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

        return MatrixExport(
            matrix=matrix,
            format="json",
            content=json_str,
        )

    @staticmethod
    def export_csv(matrix: ACHMatrix) -> MatrixExport:
        """Export matrix as CSV."""
        output = StringIO()
        writer = csv.writer(output)

        # Header row
        header = ["Evidence"]
        sorted_hypotheses = sorted(matrix.hypotheses, key=lambda x: x.column_index)
        for h in sorted_hypotheses:
            header.append(h.title)
        header.extend(["Source", "Type", "Credibility", "Relevance"])
        writer.writerow(header)

        # Evidence rows
        sorted_evidence = sorted(matrix.evidence, key=lambda x: x.row_index)
        for evidence in sorted_evidence:
            row = [evidence.description]

            # Ratings for each hypothesis
            for hypothesis in sorted_hypotheses:
                rating = matrix.get_rating(evidence.id, hypothesis.id)
                row.append(rating.rating.value if rating else "N/A")

            # Additional evidence info
            row.extend([
                evidence.source,
                evidence.evidence_type.value,
                f"{evidence.credibility:.2f}",
                f"{evidence.relevance:.2f}",
            ])

            writer.writerow(row)

        # Add scores section
        writer.writerow([])
        writer.writerow(["Scores"])
        writer.writerow(["Hypothesis", "Rank", "Inconsistencies", "Weighted Score", "Normalized Score"])

        sorted_scores = sorted(matrix.scores, key=lambda x: x.rank)
        for score in sorted_scores:
            hypothesis = matrix.get_hypothesis(score.hypothesis_id)
            if hypothesis:
                writer.writerow([
                    hypothesis.title,
                    score.rank,
                    score.inconsistency_count,
                    f"{score.weighted_score:.3f}",
                    f"{score.normalized_score:.1f}",
                ])

        csv_content = output.getvalue()
        output.close()

        return MatrixExport(
            matrix=matrix,
            format="csv",
            content=csv_content,
        )

    @staticmethod
    def export_html(matrix: ACHMatrix) -> MatrixExport:
        """Export matrix as HTML table."""
        html_parts = []

        # Header
        html_parts.append('<!DOCTYPE html>')
        html_parts.append('<html>')
        html_parts.append('<head>')
        html_parts.append('<meta charset="UTF-8">')
        html_parts.append(f'<title>ACH Matrix: {matrix.title}</title>')
        html_parts.append('<style>')
        html_parts.append('''
            body { font-family: Arial, sans-serif; margin: 20px; }
            h1 { color: #333; }
            .metadata { margin-bottom: 20px; color: #666; }
            table { border-collapse: collapse; width: 100%; margin-bottom: 30px; }
            th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }
            th { background-color: #4CAF50; color: white; font-weight: bold; }
            tr:nth-child(even) { background-color: #f2f2f2; }
            .rating-pp { background-color: #4CAF50; color: white; font-weight: bold; }
            .rating-p { background-color: #8BC34A; }
            .rating-n { background-color: #FFF; }
            .rating-m { background-color: #FF9800; }
            .rating-mm { background-color: #F44336; color: white; font-weight: bold; }
            .rating-na { background-color: #E0E0E0; }
            .scores { margin-top: 20px; }
            .lead { background-color: #FFEB3B; }
        ''')
        html_parts.append('</style>')
        html_parts.append('</head>')
        html_parts.append('<body>')

        # Title and metadata
        html_parts.append(f'<h1>{matrix.title}</h1>')
        html_parts.append('<div class="metadata">')
        if matrix.description:
            html_parts.append(f'<p>{matrix.description}</p>')
        html_parts.append(f'<p>Status: {matrix.status.value}</p>')
        html_parts.append(f'<p>Created: {matrix.created_at.strftime("%Y-%m-%d %H:%M")}</p>')
        html_parts.append('</div>')

        # Matrix table
        html_parts.append('<table>')
        html_parts.append('<thead>')
        html_parts.append('<tr>')
        html_parts.append('<th>Evidence</th>')

        sorted_hypotheses = sorted(matrix.hypotheses, key=lambda x: x.column_index)
        for h in sorted_hypotheses:
            lead_class = ' class="lead"' if h.is_lead else ''
            html_parts.append(f'<th{lead_class}>{h.title}</th>')

        html_parts.append('</tr>')
        html_parts.append('</thead>')
        html_parts.append('<tbody>')

        # Evidence rows
        sorted_evidence = sorted(matrix.evidence, key=lambda x: x.row_index)
        for evidence in sorted_evidence:
            html_parts.append('<tr>')
            html_parts.append(f'<td>{evidence.description}</td>')

            # Ratings
            for hypothesis in sorted_hypotheses:
                rating = matrix.get_rating(evidence.id, hypothesis.id)
                if rating:
                    rating_value = rating.rating.value
                    # CSS class based on rating
                    css_class = {
                        '++': 'rating-pp',
                        '+': 'rating-p',
                        'N': 'rating-n',
                        '-': 'rating-m',
                        '--': 'rating-mm',
                        'N/A': 'rating-na',
                    }.get(rating_value, 'rating-n')
                    html_parts.append(f'<td class="{css_class}">{rating_value}</td>')
                else:
                    html_parts.append('<td class="rating-na">N/A</td>')

            html_parts.append('</tr>')

        html_parts.append('</tbody>')
        html_parts.append('</table>')

        # Scores table
        if matrix.scores:
            html_parts.append('<div class="scores">')
            html_parts.append('<h2>Hypothesis Scores</h2>')
            html_parts.append('<table>')
            html_parts.append('<thead>')
            html_parts.append('<tr>')
            html_parts.append('<th>Rank</th>')
            html_parts.append('<th>Hypothesis</th>')
            html_parts.append('<th>Inconsistencies</th>')
            html_parts.append('<th>Weighted Score</th>')
            html_parts.append('<th>Normalized Score</th>')
            html_parts.append('</tr>')
            html_parts.append('</thead>')
            html_parts.append('<tbody>')

            sorted_scores = sorted(matrix.scores, key=lambda x: x.rank)
            for score in sorted_scores:
                hypothesis = matrix.get_hypothesis(score.hypothesis_id)
                if hypothesis:
                    lead_class = ' class="lead"' if hypothesis.is_lead else ''
                    html_parts.append(f'<tr{lead_class}>')
                    html_parts.append(f'<td>{score.rank}</td>')
                    html_parts.append(f'<td>{hypothesis.title}</td>')
                    html_parts.append(f'<td>{score.inconsistency_count}</td>')
                    html_parts.append(f'<td>{score.weighted_score:.3f}</td>')
                    html_parts.append(f'<td>{score.normalized_score:.1f}</td>')
                    html_parts.append('</tr>')

            html_parts.append('</tbody>')
            html_parts.append('</table>')
            html_parts.append('</div>')

        # Footer
        html_parts.append(f'<p style="margin-top: 40px; color: #999; font-size: 0.9em;">')
        html_parts.append(f'Generated: {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")} UTC')
        html_parts.append('</p>')
        html_parts.append('</body>')
        html_parts.append('</html>')

        html_content = '\n'.join(html_parts)

        return MatrixExport(
            matrix=matrix,
            format="html",
            content=html_content,
        )

    @staticmethod
    def export_markdown(matrix: ACHMatrix) -> MatrixExport:
        """Export matrix as Markdown."""
        md_parts = []

        # Title and metadata
        md_parts.append(f'# {matrix.title}\n')
        if matrix.description:
            md_parts.append(f'{matrix.description}\n')
        md_parts.append(f'**Status:** {matrix.status.value}  ')
        md_parts.append(f'**Created:** {matrix.created_at.strftime("%Y-%m-%d %H:%M")}\n')

        # Matrix table
        md_parts.append('## Matrix\n')

        sorted_hypotheses = sorted(matrix.hypotheses, key=lambda x: x.column_index)
        sorted_evidence = sorted(matrix.evidence, key=lambda x: x.row_index)

        # Header
        header = ['Evidence']
        for h in sorted_hypotheses:
            lead_marker = ' (LEAD)' if h.is_lead else ''
            header.append(f'{h.title}{lead_marker}')

        md_parts.append('| ' + ' | '.join(header) + ' |')
        md_parts.append('| ' + ' | '.join(['---'] * len(header)) + ' |')

        # Rows
        for evidence in sorted_evidence:
            row = [evidence.description]

            for hypothesis in sorted_hypotheses:
                rating = matrix.get_rating(evidence.id, hypothesis.id)
                row.append(rating.rating.value if rating else 'N/A')

            md_parts.append('| ' + ' | '.join(row) + ' |')

        # Scores
        if matrix.scores:
            md_parts.append('\n## Hypothesis Scores\n')
            md_parts.append('| Rank | Hypothesis | Inconsistencies | Weighted Score | Normalized Score |')
            md_parts.append('| --- | --- | --- | --- | --- |')

            sorted_scores = sorted(matrix.scores, key=lambda x: x.rank)
            for score in sorted_scores:
                hypothesis = matrix.get_hypothesis(score.hypothesis_id)
                if hypothesis:
                    md_parts.append(
                        f'| {score.rank} | {hypothesis.title} | {score.inconsistency_count} | '
                        f'{score.weighted_score:.3f} | {score.normalized_score:.1f} |'
                    )

        # Footer
        md_parts.append(f'\n---\n*Generated: {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")} UTC*')

        markdown_content = '\n'.join(md_parts)

        return MatrixExport(
            matrix=matrix,
            format="markdown",
            content=markdown_content,
        )

    @staticmethod
    def export(matrix: ACHMatrix, format: str = "json") -> MatrixExport:
        """
        Export matrix in specified format.

        Args:
            matrix: ACHMatrix to export
            format: Export format (json, csv, html, markdown)

        Returns:
            MatrixExport object
        """
        format_lower = format.lower()

        exporters = {
            "json": MatrixExporter.export_json,
            "csv": MatrixExporter.export_csv,
            "html": MatrixExporter.export_html,
            "markdown": MatrixExporter.export_markdown,
            "md": MatrixExporter.export_markdown,
        }

        exporter = exporters.get(format_lower)
        if not exporter:
            logger.warning(f"Unknown export format: {format}, defaulting to JSON")
            exporter = MatrixExporter.export_json

        return exporter(matrix)
