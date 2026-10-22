"""Small R2 fit-test set: real reusable leg parts, optional PCB and sensor gauges."""
import hashlib
import json
import zipfile
from pathlib import Path
from verify_current import ROOT,CURRENT,cq,check_mesh

out=ROOT/'releases/QuadrupedRobot_Fit_Test_R2.zip'
files={}
for name,qty in [('thigh_left',2),('shin',4),('hip_horn_clamp',4),('knee_horn_clamp',4)]:
    files[f'01_LEG/{name}_x1.stl']=(CURRENT/'print'/f'{name}_x{qty}.stl').read_bytes()
files['02_OPTIONAL/board_mount_x1.stl']=(CURRENT/'print/board_mount_x1.stl').read_bytes()
shape=cq.importers.importStep(str(ROOT/'cad/fit_tests/ultrasonic_hole_gauge.step')).val()
assert shape.isValid() and len(shape.Solids())==1
bb=shape.BoundingBox();shape=shape.translate((-bb.xmin,-bb.ymin,-bb.zmin))
temp=ROOT/'.cad_runtime/tmp/ultrasonic_hole_gauge.stl'
temp.parent.mkdir(parents=True,exist_ok=True)
cq.exporters.export(shape,str(temp),tolerance=.025,angularTolerance=.1)
files['02_OPTIONAL/ultrasonic_hole_gauge_x1.stl']=temp.read_bytes()
manifest={}
for name,raw in files.items():
    manifest[name]={'quantity':1,'triangles':check_mesh(raw),'sha256':hashlib.sha256(raw).hexdigest()}
notes='''R2 小批试装包（无额外主板支撑柱版本）

每个STL只含1件，每个文件只打1件，毫米、100%比例。使用实际整机准备采用的PLA Basic、喷嘴和参数。

优先打印 01_LEG 的4件：
1. thigh_left_x1：真实左大腿，验证舵机壳体能通过窗口、安装耳落座、螺钉孔对齐。
2. shin_x1：真实小腿，验证原装舵臂能完整放入凹槽、根部凸起与中央孔不顶住。
3. hip_horn_clamp_x1：配左大腿的髋压板。
4. knee_horn_clamp_x1：配小腿的膝压板。
这4件均直接复制自当前整机打印件，配合通过后可继续用于整机，不是废弃试片。
检查左大腿上的膝舵机安装窗口，即可先验证这版24×13.2mm窗口和安装耳调节孔；它不能替代最终主体的打印方向与装配检查。

02_OPTIONAL 按需打印：
- board_mount_x1：当前实际3mm厚主板固定框，没有额外立柱。可直接核对整套已装配主板的四孔、下方接口和固定框是否干涉；通过后可继续装到整机。
- ultrasonic_hole_gauge_x1：2mm厚平面孔距规，孔中心距42×17mm、孔为4.2×3.6mm，与实际立板一致。
  只测安装孔和螺钉/垫片是否对齐，不验证立板高度、杜邦线空间或安装刚度，不是整机零件。
  从模块背面或使用间隔垫片对孔，避免让量规压住背面电子元件。

建议0.4mm喷嘴、0.20mm层高、4圈墙、5层顶底、35%陀螺填充；两种压板100%填充。
保持STL方向：腿件平整背面朝下，舵臂槽朝上。大腿可用普通自动支撑，切片检查悬空台阶，避免填满配合槽；小腿、压板及两个平面件先关闭支撑并检查预览。

打印后先冷却、去掉毛边再试合。不要用强压硬塞或强拧螺钉掩盖尺寸问题。
先验证舵臂+腿+压板的组合，再装舵机中央螺钉；使用原装舵臂和原装中心螺钉。
压板固定用M2螺钉、螺母及小垫片。大腿组合可备M2×16，小腿组合可备M2×12；这是试装起点，以实际垫片/螺母厚度和干涉情况为准。
主板孔仅Ø2.4mm，使用M2紧固件，不能强穿M3。超声波也用M2和小垫片。

验收：窗口能自然插入且耳部平贴；孔能对齐；舵臂根部不顶住；中央螺钉可安装；压板夹持后无明显轴向或转动松动；螺钉端部不碰舵机。
发现问题时记录具体文件名、过紧/过松的位置，配合照片和卡尺尺寸反馈。通过试装不等于完成承重或步态验证。
'''
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
    for name,raw in files.items():z.writestr(name,raw)
    z.writestr('README_先读我.txt',notes)
    z.writestr('manifest.json',json.dumps(manifest,indent=2))
with zipfile.ZipFile(out) as z:
    assert z.testzip() is None
    for name,raw in files.items():assert z.read(name)==raw
print(str(out));print('4 reusable leg parts + 2 optional pieces; all x1; meshes and ZIP verified')
