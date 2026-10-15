"""Package project sources, CAD, references and docs without local dependencies."""
from zipfile import ZipFile, ZIP_DEFLATED
from project_paths import ROOT, RELEASE_DIR

archive = RELEASE_DIR / 'QuadrupedRobot_PLA_Prototype.zip'
files = [ROOT / name for name in ('README.md', 'requirements.txt', '.gitignore', '.gitattributes')]
for name in ('scripts', 'hardware', 'cad', 'docs', 'archive'):
    files.extend(p for p in (ROOT / name).rglob('*')
                 if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc')
with ZipFile(archive, 'w', ZIP_DEFLATED) as package:
    for path in sorted(files):
        package.write(path, path.relative_to(ROOT).as_posix())
with ZipFile(archive) as package:
    assert package.testzip() is None
    print(f'{archive.name}: {len(package.namelist())} files, {archive.stat().st_size} bytes')
