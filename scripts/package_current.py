"""Package only the current, verified printable SolidWorks-derived meshes."""
import hashlib
import json
import zipfile
from pathlib import Path
from verify_current import QUANTITIES, check_mesh

ROOT=Path(__file__).resolve().parents[1]
CURRENT=ROOT/'cad/current'
report=json.loads((CURRENT/'validation.json').read_text(encoding='utf-8'))
assert report.get('revision')=='R3'
assert report.get('assembly_components')==35
assert not report['static_intersections_over_0p05_mm3'], 'Resolve geometry collisions before packaging'
output=ROOT/'releases/QuadrupedRobot_Print_R3.zip'
output.parent.mkdir(exist_ok=True)
files=[]
with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
    for name,qty in QUANTITIES.items():
        p=CURRENT/'print'/f'{name}_x{qty}.stl'
        raw=p.read_bytes();check_mesh(raw)
        assert hashlib.sha256(raw).hexdigest()==report['parts'][name]['sha256']
        z.writestr(p.name,raw);files.append(p)
    z.writestr('打印与修订说明.md',(ROOT/'docs/设计与打印说明.md').read_bytes())
    z.writestr('manifest.json',json.dumps(report['parts'],indent=2))
with zipfile.ZipFile(output) as z:
    assert z.testzip() is None
    assert len([n for n in z.namelist() if n.endswith('.stl')])==8
    for p in files:assert z.read(p.name)==p.read_bytes()
print(str(output))
print('8 STL files, 19 pieces, ZIP CRC and per-file content verified')
