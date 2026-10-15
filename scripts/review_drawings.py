"""Screen the exported drawing PDFs for overlapping text.

The engineering-drawing skill only accepts vector text bounds from the exported PDF as
a *risk screen* - it cannot prove a dimension chain is correct, but it does catch the
classic failure of stacked autodimensions colliding with each other or with the title
block. Results land in solidworks/drawing_review.json and are summarised on stdout.

    python scripts/review_drawings.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pymupdf

from project_paths import ROOT

PDF_DIR = ROOT / 'solidworks' / 'drawings' / 'pdf'
REPORT_PATH = ROOT / 'solidworks' / 'drawing_review.json'

# Tolerance in points: touching corners are not a collision.
OVERLAP_TOLERANCE = 0.6


def span_boxes(page):
    """One box per logical text line.

    PyMuPDF splits a line into several spans whenever the font or digit run changes,
    and those spans legitimately overlap; comparing raw spans produces false collisions
    inside a single line of a note. Line rectangles are the meaningful unit.
    """
    boxes = []
    for block in page.get_text('dict')['blocks']:
        for line in block.get('lines', []):
            text = ''.join(span['text'] for span in line.get('spans', [])).strip()
            if not text:
                continue
            x0 = min(span['bbox'][0] for span in line['spans'])
            y0 = min(span['bbox'][1] for span in line['spans'])
            x1 = max(span['bbox'][2] for span in line['spans'])
            y1 = max(span['bbox'][3] for span in line['spans'])
            boxes.append({'text': text, 'bbox': [x0, y0, x1, y1]})
    return boxes


def overlaps(first, second):
    ax0, ay0, ax1, ay1 = first
    bx0, by0, bx1, by1 = second
    dx = min(ax1, bx1) - max(ax0, bx0)
    dy = min(ay1, by1) - max(ay0, by0)
    if dx <= OVERLAP_TOLERANCE or dy <= OVERLAP_TOLERANCE:
        return 0.0
    return dx * dy


def review_pdf(path):
    document = pymupdf.open(path)
    page = document[0]
    boxes = span_boxes(page)
    collisions = []
    for index, first in enumerate(boxes):
        for second in boxes[index + 1:]:
            area = overlaps(first['bbox'], second['bbox'])
            if area > 0:
                collisions.append({
                    'area_pt2': round(area, 2),
                    'a': first['text'][:40],
                    'b': second['text'][:40],
                    'where': [round(v, 1) for v in first['bbox']],
                })
    collisions.sort(key=lambda item: -item['area_pt2'])
    return {
        'file': path.name,
        'page_mm': [round(page.rect.width / 72 * 25.4, 1),
                    round(page.rect.height / 72 * 25.4, 1)],
        'text_spans': len(boxes),
        'collisions': len(collisions),
        'worst': collisions[:8],
    }


def main():
    if not PDF_DIR.exists():
        print(f'no PDF directory at {PDF_DIR}')
        return 1
    pdfs = sorted(path for path in PDF_DIR.glob('*.pdf')
                  if not path.name.startswith('_probe'))
    if not pdfs:
        print('no drawing PDFs found')
        return 1

    report = {'pdf_count': len(pdfs), 'tolerance_pt': OVERLAP_TOLERANCE, 'files': []}
    for path in pdfs:
        entry = review_pdf(path)
        report['files'].append(entry)
        print(f"{entry['file']:34s} spans={entry['text_spans']:4d} "
              f"collisions={entry['collisions']}")
        for worst in entry['worst'][:3]:
            print(f"      {worst['area_pt2']:7.2f} pt2  '{worst['a']}' vs '{worst['b']}'")
    report['clean'] = all(entry['collisions'] == 0 for entry in report['files'])
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                           encoding='utf-8')
    print(f"\nreport -> {REPORT_PATH}")
    print('clean:', report['clean'])
    return 0 if report['clean'] else 2


if __name__ == '__main__':
    sys.exit(main())
