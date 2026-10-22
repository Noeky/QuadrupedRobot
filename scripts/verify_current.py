"""Inspect SolidWorks-exported geometry and derive printable meshes, not source CAD."""
import csv
import hashlib
import json
import struct
import sys
from collections import Counter
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.cad_runtime'))
import cadquery as cq
from OCP.gp import gp_Trsf

CURRENT = ROOT / 'cad/current'
QUANTITIES = dict(body=1, thigh_left=2, thigh_right=2, shin=4,
                  hip_horn_clamp=4, knee_horn_clamp=4, board_mount=1,
                  ultrasonic_bracket=1)

def check_mesh(raw):
    n=struct.unpack_from('<I',raw,80)[0]
    assert len(raw)==84+50*n
    edges,directed=Counter(),Counter()
    for i in range(n):
        v=struct.unpack_from('<12fH',raw,84+50*i)
        p=[tuple(round(x,5) for x in v[j:j+3]) for j in (3,6,9)]
        assert len(set(p))==3
        for a,b in zip(p,p[1:]+p[:1]):
            edges[tuple(sorted((a,b)))]+=1;directed[(a,b)]+=1
    assert all(v==2 for v in edges.values())
    assert all(directed[(a,b)]==directed[(b,a)] for a,b in edges)
    return n


def main():
    report = {'parts': {}, 'limitations': ['Physical fit and load not tested',
              'Fasteners, wiring and PCB components not fully modelled',
              'Assembly components positioned and fixed; no motion mates']}
    (CURRENT / 'print').mkdir(exist_ok=True)
    for name, qty in QUANTITIES.items():
        path = CURRENT / 'step' / (name + '.step')
        shape = cq.importers.importStep(str(path)).val()
        assert shape.isValid() and len(shape.Solids()) == 1, name
        bb = shape.BoundingBox()
        # Source native CAD follows joint coordinates. Put smooth backs on bed.
        if name in ('thigh_left', 'thigh_right', 'shin'):
            shape = shape.rotate((0, 0, 0), (1, 0, 0), 180)
        bb = shape.BoundingBox()
        shape = shape.translate((-bb.xmin, -bb.ymin, -bb.zmin))
        target = CURRENT / 'print' / f'{name}_x{qty}.stl'
        cq.exporters.export(shape, str(target), tolerance=.025, angularTolerance=.1)
        triangles=check_mesh(target.read_bytes())
        report['parts'][name] = {'quantity': qty, 'valid': True, 'solids': 1,
            'volume_mm3': round(shape.Volume(), 2),
            'triangles':triangles,'mesh_closed_consistent':True,
            'print_bounds_mm': [round(bb.xlen, 3), round(bb.ylen, 3), round(bb.zlen, 3)],
            'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}
    cache, items = {}, []
    manifest = CURRENT / 'assembly_manifest.tsv'
    if manifest.exists():
        for name, file, transform in csv.reader(manifest.open(encoding='utf-8-sig'), delimiter='\t'):
            p = Path(file)
            step = p.with_suffix('.step') if 'hardware' in p.parts else CURRENT/'step'/(p.stem+'.step')
            if step not in cache:
                cache[step] = cq.importers.importStep(str(step)).val()
            d = [float(v) for v in transform.split(',')]
            trsf=gp_Trsf()
            trsf.SetValues(d[0],d[3],d[6],d[9]*1000,d[1],d[4],d[7],d[10]*1000,
                           d[2],d[5],d[8],d[11]*1000)
            shape=cache[step].moved(cq.Location(trsf))
            items.append((name, shape))
        hits = []
        for i, (an, a) in enumerate(items):
            ab = a.BoundingBox()
            for bn, b in items[i+1:]:
                bb = b.BoundingBox()
                if any((ab.xmax <= bb.xmin, bb.xmax <= ab.xmin, ab.ymax <= bb.ymin,
                        bb.ymax <= ab.ymin, ab.zmax <= bb.zmin, bb.zmax <= ab.zmin)):
                    continue
                vol = a.intersect(b).Volume()
                if vol > .05:
                    hits.append(dict(a=an, b=bn, volume_mm3=round(vol, 4)))
        report['assembly_components'] = len(items)
        report['static_intersections_over_0p05_mm3'] = hits
        render(items)
    (CURRENT/'validation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


def render(items):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    fig=plt.figure(figsize=(11,8));ax=fig.add_subplot(111, projection='3d')
    faces,colors=[],[]
    for name, shape in items:
        verts, tris=shape.tessellate(.25, .25)
        xyz=[p.toTuple() for p in verts]
        color='#4682b4' if 'servo' in name else '#ddd2af' if 'horn' in name or 'clamp' in name else '#d88135' if 'thigh' in name or 'shin' in name else '#83ae94' if 'PCB' in name else '#84919b'
        faces.extend([[xyz[k] for k in tri] for tri in tris]);colors.extend([color]*len(tris))
    ax.add_collection3d(Poly3DCollection(faces,facecolors=colors,edgecolor='none'))
    ax.set_xlim(-85,95);ax.set_ylim(-95,95);ax.set_zlim(-90,70);ax.set_box_aspect((180,190,160))
    ax.view_init(25,-48);ax.set_xlabel('X / mm');ax.set_ylabel('Y / mm');ax.set_zlabel('Z / mm')
    ax.set_title('Revision 2 - SolidWorks native model\nLow-profile PCB frame and ultrasonic mounting frame; hardware fit pending')
    fig.tight_layout();fig.savefig(CURRENT/'preview.png',dpi=160);plt.close(fig)


if __name__ == '__main__':
    main()
