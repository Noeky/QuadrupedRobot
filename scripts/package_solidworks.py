"""Package the SolidWorks deliverables for handing in.

Builds <课程目录>/四足机器人相关图片.zip containing the part drawings, the assembly
drawing, PNG previews of every sheet, the native SolidWorks models and the README.

    python scripts/package_solidworks.py
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pymupdf

from project_paths import ROOT

SW_DIR = ROOT / 'solidworks'
PART_DIR = SW_DIR / 'parts'
ASSY_DIR = SW_DIR / 'assembly'
DRAW_DIR = SW_DIR / 'drawings'
PDF_DIR = DRAW_DIR / 'pdf'
README = SW_DIR / 'README.md'

# The course folder is the repository parent (project/QuadrupedRobot -> 先进制造与机器人实践).
COURSE_DIR = ROOT.parents[1]
ARCHIVE = COURSE_DIR / '四足机器人相关图片.zip'
ARCHIVE_STEM = '四足机器人相关图片'
PREVIEW_DPI = 150


def sparse_part_drawings():
    return sorted(path for path in DRAW_DIR.glob('零件图_*.SLDDRW'))


def build_members():
    """(source path, path inside the archive) pairs, or (None, name) for generated files."""
    members = []
    for drawing in sparse_part_drawings():
        members.append((drawing, f'{ARCHIVE_STEM}/零件图/{drawing.name}'))
        pdf = PDF_DIR / f'{drawing.stem}.pdf'
        if pdf.exists():
            members.append((pdf, f'{ARCHIVE_STEM}/零件图/{pdf.name}'))

    for drawing in sorted(DRAW_DIR.glob('装配图_*.SLDDRW')):
        members.append((drawing, f'{ARCHIVE_STEM}/装配图/{drawing.name}'))
        pdf = PDF_DIR / f'{drawing.stem}.pdf'
        if pdf.exists():
            members.append((pdf, f'{ARCHIVE_STEM}/装配图/{pdf.name}'))

    for drawing in sorted(DRAW_DIR.glob('*.SLDDRW')):
        if drawing.name.startswith('_'):
            continue
        pdf = PDF_DIR / f'{drawing.stem}.pdf'
        if pdf.exists():
            members.append((pdf, f'{ARCHIVE_STEM}/图纸预览PDF/{pdf.name}'))

    for part in sorted(PART_DIR.glob('*.SLDPRT')):
        if part.name.startswith('~$'):
            continue
        members.append((part, f'{ARCHIVE_STEM}/SolidWorks模型/零件/{part.name}'))
    for name in ('quadruped_prototype.SLDASM',):
        path = ASSY_DIR / name
        if path.exists():
            members.append((path, f'{ARCHIVE_STEM}/SolidWorks模型/装配/{name}'))
    for component in sorted((ASSY_DIR / 'components').glob('*.SLD*')):
        if component.name.startswith('~$'):
            continue
        members.append((component,
                        f'{ARCHIVE_STEM}/SolidWorks模型/装配/零部件/{component.name}'))

    for extra in ('generation_report.json', 'drawing_review.json'):
        path = SW_DIR / extra
        if path.exists():
            members.append((path, f'{ARCHIVE_STEM}/生成与审查记录/{extra}'))

    if README.exists():
        members.append((README, f'{ARCHIVE_STEM}/说明.md'))
    return members


def render_preview(pdf, target):
    document = pymupdf.open(pdf)
    pixmap = document[0].get_pixmap(dpi=PREVIEW_DPI)
    target.parent.mkdir(parents=True, exist_ok=True)
    pixmap.save(str(target))
    document.close()
    return target


def main():
    if not PDF_DIR.exists():
        print('no drawings yet - run build_solidworks.py drawings first')
        return 1

    preview_dir = SW_DIR / '_preview'
    previews = []
    for pdf in sorted(PDF_DIR.glob('*.pdf')):
        if pdf.name.startswith('_probe'):
            continue
        previews.append(render_preview(pdf, preview_dir / f'{pdf.stem}.png'))

    members = build_members()
    for preview in previews:
        members.append((preview, f'{ARCHIVE_STEM}/图纸预览图片/{preview.name}'))

    missing = [str(source) for source, _ in members if not source.exists()]
    if missing:
        print('missing sources:')
        for path in missing:
            print('  ', path)
        return 1

    ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ARCHIVE, 'w', zipfile.ZIP_DEFLATED) as archive:
        for source, name in members:
            archive.write(source, name)

    size_mb = ARCHIVE.stat().st_size / 1024 / 1024
    print(f'archive : {ARCHIVE}')
    print(f'files   : {len(members)}  ({size_mb:.1f} MB)')
    folders = {}
    for _, name in members:
        folder = str(Path(name).parent).split('/', 2)[-1]
        folders[folder] = folders.get(folder, 0) + 1
    for folder, count in sorted(folders.items()):
        print(f'  {folder:<24} {count}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
