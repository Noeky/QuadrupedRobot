"""Explain the supplied horn and the current prototype's axial stack."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'.cad_runtime'))
import cadquery as cq
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from matplotlib.patches import Rectangle
plt.rcParams['font.family']='Microsoft YaHei'
fig,axs=plt.subplots(1,2,figsize=(14,6),gridspec_kw={'width_ratios':[1,1.8]})
horn=cq.importers.importStep(str(ROOT/'舵机转头.STEP')).val()
ax=axs[0]
for face in horn.Faces():
    bb=face.BoundingBox()
    if face.geomType()=='PLANE' and abs(bb.ymin)<1e-6 and abs(bb.ymax)<1e-6:
        verts,tris=face.tessellate(.02,.1)
        points=[(v.x,v.z) for v in verts]
        ax.add_collection(PolyCollection([[points[i] for i in t] for t in tris],facecolor='#ede2c5',edgecolor='none'))
ax.set_xlim(-20,9);ax.set_ylim(-9,9);ax.set_aspect('equal');ax.axis('off')
ax.annotate('圆形根部\n凸台朝向舵机输出轴',xy=(0,2.7),xytext=(-3,6),arrowprops={'arrowstyle':'->'},ha='center')
ax.annotate('单臂轮廓：根部宽、末端窄',xy=(-10,-1.6),xytext=(-8,-5),arrowprops={'arrowstyle':'->'},ha='center')
ax.annotate('6个小孔 Ø0.7\n当前压板方案不使用这些孔',xy=(-8.5,0),xytext=(-14,4.5),arrowprops={'arrowstyle':'->'},ha='center')
ax.set_title('① 附件转头的真实正面轮廓\n由STEP实体绘制')

ax=axs[1]
def rect(x,y,w,h,c):ax.add_patch(Rectangle((x,y),w,h,facecolor=c,edgecolor='#344354',lw=1))
blue='#477bb6';cream='#ede2c5';orange='#de8b3a';gold='#b9ab83'
rect(0,-6,12,25,blue);rect(12,-2.5,4,5,blue)
rect(20,-9,1.5,5.4,gold);rect(20,3.6,1.5,21.4,gold)
# Simplified longitudinal section of the real horn: shaft cup and 1 mm arm.
rect(23,2.5,3,.5,cream);rect(23,-3,3,.5,cream)
rect(26,1,1,15,cream);rect(26,-3,1,2,cream)
# Slot floor and wall at distal end, clipped in the diagram.
rect(32.1,3.6,3.4,22.4,orange);rect(31,16.2,1.1,9.8,orange)
rect(31,-9,4.5,5.4,orange)
ax.plot([10,38],[0,0],'--',color='#6c7b88',lw=1)
for x,label in [(6,'舵机'),(20.75,'打印压板'),(26.5,'原装转头'),(34,'带槽腿件')]:
    ax.text(x,30,label,ha='center',va='center',fontsize=12)
ax.annotate('凸台从压板中心大孔穿过\n套到原舵机输出轴上',xy=(23.2,2.8),xytext=(8,-14),arrowprops={'arrowstyle':'->'},ha='center')
ax.annotate('转头薄臂放进腿件背面的槽\n合拢后由压板封住',xy=(31.7,10),xytext=(29,36),arrowprops={'arrowstyle':'->'},ha='center')
ax.text(20,-20,'沿输出轴分开显示；示意剖面，零件间距不代表实际装配间隙',ha='center',fontsize=10)
ax.text(20,-25,'先装好「压板＋转头＋腿件」，再将转头套到舵机轴上；中心螺钉从腿件大孔穿入',ha='center',fontsize=10)
ax.set_xlim(-2,43);ax.set_ylim(-29,40);ax.axis('off')
ax.set_title('② 当前连接方案的分层关系\n转头是舵机与打印腿件之间的连接件')
fig.suptitle('转头适配说明：当前槽为近似包络，夹持与间隙仍需试装验证',fontsize=15)
fig.tight_layout()
fig.savefig(ROOT/'prototype/转头连接说明.png',dpi=170)
