"""Provisional envelope assembly, NOT printable mechanical parts or checked design."""
import sys, json, math
from pathlib import Path
from project_paths import LAYOUT_DIR, REFERENCE_DIR

import cadquery as cq
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

folder=LAYOUT_DIR; folder.mkdir(exist_ok=True)
p=dict(body_length=120,body_width=80,deck_thickness=3,
       hip_x=43,hip_y=54,thigh_length=40,shin_length=45,
       standing_thigh_angle_from_down_deg=30,
       standing_shin_angle_from_down_deg=-30,
       provisional_electronics_envelope=[70,50,30])
(folder/'layout_parameters.json').write_text(json.dumps(p,indent=2),encoding='utf-8')
servo=cq.importers.importStep(str(REFERENCE_DIR/'舵机.STEP')).val()
horn=cq.importers.importStep(str(REFERENCE_DIR/'舵机转头.STEP')).val()
assy=cq.Assembly(name='UNVERIFIED_LAYOUT_ONLY')
deck=cq.Workplane('XY').box(120,80,3).translate((0,0,16)).val()
assy.add(deck,name='deck_envelope',color=cq.Color(0.45,0.5,0.55,0.5))
electronics=cq.Workplane('XY').box(70,50,30).translate((0,0,32.5)).val()
assy.add(electronics,name='unknown_electronics_envelope',color=cq.Color(0.3,0.7,0.5,0.3))

def rod(a,b,r=1.2):
    vec=cq.Vector(*b).sub(cq.Vector(*a))
    return cq.Solid.makeCylinder(r,vec.Length,cq.Vector(*a),vec.normalized())

points=[]
for fore,hx in [('front',43),('rear',-43)]:
    for side,sign in [('left',1),('right',-1)]:
        hy=sign*54
        hip=(hx,hy,0)
        knee=(hx+20,hy,-40*math.cos(math.radians(30)))
        foot=(knee[0]-22.5,hy,knee[2]-45*math.cos(math.radians(30)))
        points.append((fore,side,hip,knee,foot))
        for joint,pt in [('hip',hip),('knee',knee)]:
            # align actual source output shaft end (16.8,29.8,6.25) with joint
            s=servo.translate((-16.8,-29.8,-6.25))
            h=horn
            if sign<0:
                s=s.mirror('XZ'); h=h.mirror('XZ')
            assy.add(s.translate(pt),name=f'{fore}_{side}_{joint}_servo',color=cq.Color(0.15,0.4,0.8,0.8))
            # source horn bore spans Y 1..4. Seating not verified: envelope placement only.
            assy.add(h.translate(pt),name=f'{fore}_{side}_{joint}_horn_envelope',color=cq.Color(0.85,0.85,0.8))
        assy.add(rod(hip,knee),name=f'{fore}_{side}_thigh_axis_placeholder',color=cq.Color(0.9,0.5,0.2))
        assy.add(rod(knee,foot),name=f'{fore}_{side}_shin_axis_placeholder',color=cq.Color(0.9,0.5,0.2))
assy.export(str(folder/'quadruped_LAYOUT_ONLY.step'))

plt.rcParams['font.family']='Microsoft YaHei'
fig,axs=plt.subplots(1,2,figsize=(12,5))
ax=axs[0]
ax.add_patch(Rectangle((-60,-40),120,80,facecolor='#dce3eb',edgecolor='#485466'))
ax.add_patch(Rectangle((-35,-25),70,50,facecolor='#a2cfb0',edgecolor='#367149',alpha=.7))
for fore,side,h,k,f in points:
    ax.plot([h[0],k[0],f[0]],[h[1],k[1],f[1]],'o-',color='#d4862e')
ax.set_title('俯视布局 · 主体 120×80 暂定'); ax.set_xlabel('前后方向 X / mm');ax.set_ylabel('左右方向 Y / mm')
ax.set_aspect('equal');ax.autoscale();ax.margins(.15);ax.grid(alpha=.2)
ax=axs[1]
ax.add_patch(Rectangle((-60,14.5),120,3,facecolor='#dce3eb',edgecolor='#485466'))
for fore,side,h,k,f in points:
    if side=='left':
        ax.plot([h[0],k[0],f[0]],[h[2],k[2],f[2]],'o-',color='#d4862e',lw=3)
ax.set_title('侧视 · 大腿40 / 小腿45 mm 暂定'); ax.set_xlabel('X / mm');ax.set_ylabel('Z / mm')
ax.set_aspect('equal');ax.autoscale();ax.margins(.15);ax.grid(alpha=.2)
fig.suptitle('布局草案：线段表示关节连线；支架、转头安装姿态、干涉和承重尚未验证')
fig.tight_layout();fig.savefig(folder/'布局草案.png',dpi=160)
print('Wrote provisional layout, 8 reference servos; no printable robot STL.')
