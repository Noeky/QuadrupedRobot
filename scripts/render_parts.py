"""Generate dimension reference views from the actual STEP tessellation."""
import sys
from pathlib import Path
from project_paths import IMAGE_DIR, REFERENCE_DIR

import cadquery as cq
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
plt.rcParams['font.family'] = 'Microsoft YaHei'
fig, axs = plt.subplots(2, 3, figsize=(13, 7))
for row, path in enumerate(REFERENCE_DIR.glob('*.STEP')):
    shape = cq.importers.importStep(str(path)).val()
    verts, tris = shape.tessellate(0.08)
    coords = [(v.x,v.y,v.z) for v in verts]
    for col,(a,b,label) in enumerate([(0,1,'XY'),(0,2,'XZ（沿输出轴观察）'),(2,1,'ZY')]):
        ax = axs[row,col]
        polygons = [[(coords[i][a],coords[i][b]) for i in tri] for tri in tris]
        ax.add_collection(PolyCollection(polygons, facecolor='#9dbbd0', edgecolor='#40586b',linewidth=0.15,alpha=0.7))
        ax.autoscale(); ax.set_aspect('equal'); ax.margins(0.15)
        ax.set_title(path.stem+' · '+label)
        ax.set_xlabel('XYZ'[a]+' / mm'); ax.set_ylabel('XYZ'[b]+' / mm'); ax.grid(alpha=0.2)
fig.suptitle('附件几何参考 · 毫米 · 原始坐标系（非机器人装配姿态）')
fig.tight_layout()
fig.savefig(IMAGE_DIR / '零件尺寸参考.png', dpi=160)
