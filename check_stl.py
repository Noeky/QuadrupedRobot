"""Check binary STL triangle edges after welding coordinates to 1e-5 mm."""
import struct,json
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parent
out={}
for path in list((ROOT/'prototype').glob('*.stl'))+[ROOT/'output/servo_fit_coupon.stl']:
    raw=path.read_bytes();n=struct.unpack_from('<I',raw,80)[0]
    assert len(raw)==84+50*n,path
    edges=Counter();directed=Counter();degenerate=0
    for i in range(n):
        vals=struct.unpack_from('<12fH',raw,84+50*i)
        points=[tuple(round(v,5) for v in vals[j:j+3]) for j in [3,6,9]]
        if len(set(points))<3:degenerate+=1
        for a,b in zip(points,points[1:]+points[:1]):
            edges[tuple(sorted((a,b)))]+=1;directed[(a,b)]+=1
    bad=sum(c!=2 for c in edges.values())
    winding=sum(directed[(a,b)]!=directed[(b,a)] for a,b in edges)
    out[path.name]=dict(triangles=n,nonmanifold_edges=bad,inconsistent_winding_edges=winding,degenerate_triangles=degenerate)
    assert not (bad or winding or degenerate),(path.name,out[path.name])
(ROOT/'prototype/stl_validation.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out,indent=2))
