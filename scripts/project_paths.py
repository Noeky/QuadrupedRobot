"""Shared repository paths, independent of the shell's working directory."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE_DIR = ROOT / 'hardware' / 'reference'
CAD_DIR = ROOT / 'cad' / 'prototype'
STEP_DIR = CAD_DIR / 'step'
STL_DIR = CAD_DIR / 'stl'
COUPON_DIR = ROOT / 'cad' / 'fit_coupon'
LAYOUT_DIR = ROOT / 'archive' / 'layout'
REPORT_DIR = ROOT / 'docs' / 'reports'
IMAGE_DIR = ROOT / 'docs' / 'images'
RELEASE_DIR = ROOT / 'releases'
sys.path.insert(0, str(ROOT / '.cad_runtime'))

for directory in (STEP_DIR, STL_DIR, COUPON_DIR, LAYOUT_DIR, REPORT_DIR, IMAGE_DIR, RELEASE_DIR):
    directory.mkdir(parents=True, exist_ok=True)
