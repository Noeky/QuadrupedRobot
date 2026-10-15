"""Read supplied STEP solids and report exact bounds and cylindrical faces (mm)."""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / '.cad_runtime'))
import cadquery as cq
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder

out = {}
for path in ROOT.glob('*.STEP'):
    model = cq.importers.importStep(str(path))
    shape = model.val()
    bb = shape.BoundingBox()
    cylinders = []
    for face in shape.Faces():
        surf = BRepAdaptor_Surface(face.wrapped)
        if surf.GetType() == GeomAbs_Cylinder:
            cyl = surf.Cylinder()
            p, d = cyl.Location(), cyl.Axis().Direction()
            fb = face.BoundingBox()
            cylinders.append(dict(radius=round(cyl.Radius(), 5), origin=[round(v,5) for v in (p.X(),p.Y(),p.Z())], axis=[round(v,5) for v in (d.X(),d.Y(),d.Z())], bounds=[round(v,5) for v in (fb.xmin,fb.ymin,fb.zmin,fb.xmax,fb.ymax,fb.zmax)], area=round(face.Area(),5)))
    out[path.name] = dict(valid=shape.isValid(), solids=len(shape.Solids()), bounds=[round(v,5) for v in (bb.xmin,bb.ymin,bb.zmin,bb.xmax,bb.ymax,bb.zmax)], size=[round(v,5) for v in (bb.xlen,bb.ylen,bb.zlen)], cylinders=cylinders)
    cq.exporters.export(model, str(ROOT / (path.stem + '_reference.stl')))
(ROOT / '零件几何.json').write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
for name, data in out.items():
    print(name, json.dumps(data, ensure_ascii=False))
