"""Parametric PLA mechanical prototype. Physical fit/load validation required."""
import sys, json, math
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'.cad_runtime'))
import cadquery as cq
OUT=ROOT/'prototype'; OUT.mkdir(exist_ok=True)
P=dict(body_length=120.,body_width=80.,thigh=40.,shin=45.,
       hip_x=43.,hip_y=54.,knee_output_offset=15.,
       mounting_hole_spacing=27.7,mount_hole_dia=2.2,
       body_window=[23.1,13.3],horn_pocket_side_clearance=.2,
       horn_pocket_axial_gap=.1,clamp_hole_dia=2.2,
       battery_record_only=dict(voltage=3.7,capacity_mAh=800,model='603040',color='purple',mount_design=False))
(OUT/'parameters.json').write_text(json.dumps(P,indent=2),encoding='utf-8')

def plane(y, origin=(0,0), direction=(1,0)):
    return cq.Workplane(cq.Plane(origin=(origin[0],y,origin[1]),
                                xDir=(direction[0],0,direction[1]),normal=(0,-1,0)))

def capsule(length,width,y0,y1,origin=(0,0),direction=(1,0)):
    def wp(): return plane(y1,origin,direction)
    s=wp().center(length/2,0).rect(length,width).extrude(y1-y0)
    for x in [0,length]: s=s.union(wp().center(x,0).circle(width/2).extrude(y1-y0))
    return s

def cut_clamp_holes(s,y0,y1,origin,direction):
    cutter=plane(y1,origin,direction).pushPoints([(8,-6.5),(8,6.5)]).circle(P['clamp_hole_dia']/2).extrude(y1-y0)
    return s.cut(cutter)

def socket_arm(length,depth,origin,direction):
    # Main plate and walls around the supplied horn. Pocket outline is an envelope;
    # its fit must be checked, as the STEP does not encode actual spline tolerances.
    main=capsule(length,18,1,depth,origin,direction)
    walls=capsule(16,18,0,1,origin,direction)
    main=main.union(walls)
    depth_pocket=1+P['horn_pocket_axial_gap']
    r0=3+P['horn_pocket_side_clearance'];r1=1.5+P['horn_pocket_side_clearance']
    wp=lambda:plane(depth_pocket,origin,direction)
    pocket=wp().polyline([(0,-r0),(14.5,-r1),(14.5,r1),(0,r0)]).close().extrude(depth_pocket+.1)
    for x,r in [(0,r0),(14.5,r1)]: pocket=pocket.union(wp().center(x,0).circle(r).extrude(depth_pocket+.1))
    main=main.cut(pocket)
    main=main.cut(plane(depth+.1,origin,direction).circle(3.6).extrude(depth+.3))
    return cut_clamp_holes(main,-.2,depth+.2,origin,direction)

def clamp(origin,direction):
    s=capsule(16,18,-1.5,0,origin,direction)
    s=s.cut(plane(.1,origin,direction).circle(3.6).extrude(1.7))
    return cut_clamp_holes(s,-1.6,.1,origin,direction)

def mount_frame(origin,y0,y1):
    s=plane(y1,origin).rect(36,20).extrude(y1-y0)
    s=s.cut(plane(y1+.1,origin).rect(*P['body_window']).extrude(y1-y0+.2))
    half_spacing=P['mounting_hole_spacing']/2
    cutter=plane(y1+.1,origin).pushPoints([(-half_spacing,0),(half_spacing,0)]).circle(P['mount_hole_dia']/2).extrude(y1-y0+.2)
    return s.cut(cutter)

u=(.5,-math.sqrt(3)/2); v=(-.5,-math.sqrt(3)/2)
k=(P['thigh']/2,-P['thigh']*math.sqrt(3)/2)
offset=P['knee_output_offset']; thigh_depth=offset-9.2
thigh=socket_arm(P['thigh'],thigh_depth,(0,0),u)
thigh=thigh.union(mount_frame((k[0]-5.65,k[1]),offset-11.7,thigh_depth))
# Open the knee servo body envelope through the connecting arm too.
thigh=thigh.cut(plane(thigh_depth+.2,(k[0]-5.65,k[1])).rect(*P['body_window']).extrude(thigh_depth+.4))
half_spacing=P['mounting_hole_spacing']/2
thigh=thigh.cut(plane(thigh_depth+.2,(k[0]-5.65,k[1])).pushPoints([(-half_spacing,0),(half_spacing,0)]).circle(P['mount_hole_dia']/2).extrude(thigh_depth+.4))
# Relieve the ear band too, with 0.1 mm axial clearance to the front of the ears.
thigh=thigh.cut(plane(offset-11.6,(k[0]-5.65,k[1])).rect(32.6,P['body_window'][1]).extrude(offset-11.4))
hip_clamp=clamp((0,0),u)
shin=socket_arm(P['shin'],4.5,(0,0),v)
knee_clamp=clamp((0,0),v)

body=cq.Workplane('XY').box(P['body_length'],P['body_width'],3).translate((0,0,16))
for hx in [-P['hip_x'],P['hip_x']]:
    for sign in [-1,1]:
        front_y=P['hip_y']-11.7
        frame=mount_frame((hx-5.65,0),front_y,front_y+2.5)
        # Rib/tab connections between servo ear frame and deck.
        for x in [hx-5.65-14,hx-5.65+14]:
            rib=cq.Workplane('XY').box(6,2.5,9.5).translate((x,front_y+1.25,12.75))
            tab=cq.Workplane('XY').box(8,7,3).translate((x,front_y-.8,16))
            frame=frame.union(rib).union(tab)
        if sign<0: frame=cq.Workplane('XY').add(frame.val().mirror('XZ'))
        body=body.union(frame)
for x in [-25,25]:
    for y in [-28,28]:
        body=body.cut(cq.Workplane('XY').center(x,y).slot2D(14,3).extrude(30))
tray=cq.Workplane('XY').box(70,50,2).translate((0,0,18.5))
for x in [-25,25]:
    tray=tray.cut(cq.Workplane('XY').center(x,0).slot2D(35,3,90).extrude(25))

parts={'body':(body,1),'thigh_left':(thigh,2),
       'thigh_right':(cq.Workplane('XY').add(thigh.val().mirror('XZ')),2),'shin':(shin,4),
       'hip_horn_clamp':(hip_clamp,4),'knee_horn_clamp':(knee_clamp,4),
       'universal_tray':(tray,1)}
stats={}
for name,(part,qty) in parts.items():
    shape=part.val()
    assert shape.isValid(),name+' invalid'
    assert len(shape.Solids())==1,(name,len(shape.Solids()))
    # Export each printable part in bed orientation and at nonnegative coordinates.
    printable=shape.rotate((0,0,0),(1,0,0),180 if name=='body' else (0 if name=='universal_tray' else 90))
    bb=printable.BoundingBox(); printable=printable.translate((-bb.xmin,-bb.ymin,-bb.zmin))
    cq.exporters.export(printable,str(OUT/(name+'.step')))
    cq.exporters.export(printable,str(OUT/(name+'.stl')),tolerance=.025,angularTolerance=.1)
    stats[name]=dict(quantity=qty,volume_mm3=round(shape.Volume(),2),
                     print_bounds_mm=[round(bb.xlen,2),round(bb.ylen,2),round(bb.zlen,2)])

servo=cq.importers.importStep(str(ROOT/'舵机.STEP')).val().translate((-16.8,-29.8,-6.25))
horn=cq.importers.importStep(str(ROOT/'舵机转头.STEP')).val().rotate((0,0,0),(1,0,0),180).translate((0,1,0))
hip_horn=horn.rotate((0,0,0),(0,1,0),-120)
knee_horn=horn.rotate((0,0,0),(0,1,0),-60)
assy=cq.Assembly(name='PLA_PROTOTYPE_REQUIRES_VALIDATION')
items=[]
def add(name,shape,color):
    items.append((name,shape)); assy.add(shape,name=name,color=cq.Color(*color))
add('body',body.val(),(.45,.5,.55))
add('tray',tray.val(),(.35,.65,.5))
for hx in [-P['hip_x'],P['hip_x']]:
    for sign in [-1,1]:
        prefix=('front' if hx>0 else 'rear')+('_left' if sign>0 else '_right')
        knee_servo=servo.translate((k[0],offset,k[1]))
        local=[('hip_servo',servo,(.1,.35,.8)),('hip_horn',hip_horn,(.9,.9,.85)),
               ('thigh',thigh.val(),(.9,.5,.2)),('hip_clamp',hip_clamp.val(),(.8,.7,.4)),
               ('knee_servo',knee_servo,(.1,.35,.8)),
               ('knee_horn',knee_horn.translate((k[0],offset,k[1])),(.9,.9,.85)),
               ('shin',shin.val().translate((k[0],offset,k[1])),(.9,.5,.2)),
               ('knee_clamp',knee_clamp.val().translate((k[0],offset,k[1])),(.8,.7,.4))]
        for n,s,c in local:
            if sign<0: s=s.mirror('XZ')
            add(prefix+'_'+n,s.translate((hx,sign*P['hip_y'],0)),c)
assy.export(str(OUT/'quadruped_prototype_assembly.step'))

# Exact static solid intersection report, excluding zero-volume face contact.
intersections=[]
for i,(an,a) in enumerate(items):
    ab=a.BoundingBox()
    for bn,b in items[i+1:]:
        bb=b.BoundingBox()
        if any([ab.xmax<=bb.xmin,bb.xmax<=ab.xmin,ab.ymax<=bb.ymin,bb.ymax<=ab.ymin,ab.zmax<=bb.zmin,bb.zmax<=ab.zmin]): continue
        vol=a.intersect(b).Volume()
        if vol>.01: intersections.append(dict(a=an,b=bn,volume_mm3=round(vol,4)))
motion_hits=[]
motion_states=[]
moving_prefix='front_left_'
stationary=[(n,s) for n,s in items if not n.startswith(moving_prefix) or n.endswith('_hip_servo')]
for alpha in [-15,0,15]:
    for beta in [-20,0,20]:
        state=list(stationary)
        for n,s in items:
            if not n.startswith(moving_prefix) or n.endswith('_hip_servo'): continue
            if n.endswith(('_shin','_knee_clamp','_knee_horn')):
                s=s.rotate((P['hip_x']+k[0],P['hip_y']+offset,k[1]),(P['hip_x']+k[0],P['hip_y']+offset+1,k[1]),beta)
            s=s.rotate((P['hip_x'],P['hip_y'],0),(P['hip_x'],P['hip_y']+1,0),alpha)
            state.append((n,s))
        count=0
        for i,(an,a) in enumerate(state):
            ab=a.BoundingBox()
            for bn,b in state[i+1:]:
                if not (an.startswith(moving_prefix) or bn.startswith(moving_prefix)): continue
                bb=b.BoundingBox()
                if any([ab.xmax<=bb.xmin,bb.xmax<=ab.xmin,ab.ymax<=bb.ymin,bb.ymax<=ab.ymin,ab.zmax<=bb.zmin,bb.zmax<=ab.zmin]): continue
                vol=a.intersect(b).Volume()
                if vol>.01:
                    count+=1;motion_hits.append(dict(hip_delta=alpha,knee_delta=beta,a=an,b=bn,volume_mm3=round(vol,4)))
        motion_states.append(dict(hip_delta=alpha,knee_delta=beta,intersections=count))
report=dict(parts=stats,static_intersections=intersections,
            sampled_motion_front_left=motion_states,motion_intersections=motion_hits,
            total_printed_volume_mm3=round(sum(s['volume_mm3']*s['quantity'] for s in stats.values()),2),
            limitations=['No physical load/fit verification','Battery recorded; mounting excluded','Fasteners and wiring not modeled','Motion: front-left leg sampled at 9 states; not a continuous sweep or gait verification'])
(OUT/'validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
plt.rcParams['font.family']='Microsoft YaHei'
fig=plt.figure(figsize=(12,7));ax=fig.add_subplot(111,projection='3d')
for name,shape in items:
    verts,tris=shape.tessellate(.15,.2)
    xyz=[(q.x,q.y,q.z) for q in verts]
    color=('#3772bd' if 'servo' in name else '#ded8c7' if 'horn' in name or 'clamp' in name else '#d98535' if 'thigh' in name or 'shin' in name else '#93b99b' if name=='tray' else '#8998a5')
    mesh=Poly3DCollection([[xyz[j] for j in tri] for tri in tris],facecolor=color,edgecolor='none',alpha=1)
    ax.add_collection3d(mesh)
ax.set_xlim(-80,90);ax.set_ylim(-85,85);ax.set_zlim(-85,30);ax.set_box_aspect((170,170,115))
ax.view_init(elev=22,azim=-55);ax.set_xlabel('X / mm');ax.set_ylabel('Y / mm');ax.set_zlabel('Z / mm')
ax.set_title('无传感器四足机器人 · PLA原型\n蓝色：附件舵机；橙色：腿；灰色：主体；绿色：通用主板托盘\n电池安装未设计；紧固件/线缆未显示；需单腿试装验证')
fig.tight_layout();fig.savefig(OUT/'原型装配预览.png',dpi=170)
