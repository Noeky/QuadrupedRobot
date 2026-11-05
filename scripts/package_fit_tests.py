"""R3 horn-slot retest: prioritize one shin and its matching clamp."""
import hashlib
import json
import zipfile
from verify_current import ROOT,CURRENT,check_mesh

report=json.loads((CURRENT/'validation.json').read_text(encoding='utf-8'))
assert report.get('revision')=='R3'
assert not report['static_intersections_over_0p05_mm3']
out=ROOT/'releases/QuadrupedRobot_Fit_Test_R3.zip'
files={}
for folder,names in [('01_RETEST',['shin','knee_horn_clamp']),('02_OPTIONAL',['thigh_left','hip_horn_clamp'])]:
    for name in names:
        qty=report['parts'][name]['quantity']
        raw=(CURRENT/'print'/f'{name}_x{qty}.stl').read_bytes()
        assert hashlib.sha256(raw).hexdigest()==report['parts'][name]['sha256']
        files[f'{folder}/{name}_R3_x1.stl']=raw
manifest={name:{'quantity':1,'triangles':check_mesh(raw),'sha256':hashlib.sha256(raw).hexdigest()} for name,raw in files.items()}
notes='''R3 舵臂槽复测包，每个文件只打印1件。100%比例、毫米，沿用上一轮PLA Basic和0.20mm层高。

先只打01_RETEST：小腿shin和膝压板knee_horn_clamp，各1件。
槽保留缓渐缩，不是等宽槽：根部宽8.4mm，末端圆角从R1.35增到R2.5mm，避免根部过快收束和尖端过细。
槽最远端比R2缩短1mm，距轴心18.65mm；槽深仍2.2mm，根部局部仍3.3mm。
压板接触凸台仍高0.15mm，已缩短并留侧向余量，避免顶住新槽端。通过后可继续用于整机。

02_OPTIONAL：左大腿和髋压板各1件，需要验证完整单腿/大腿槽时再打印。
舵机窗口、耳孔与前一轮相同，不重复打印主板、超声波件，也不需要重打主体。
旧R2压板接触凸台较长，可能顶住缩短后的槽端，先用R3压板复测，避免误判。

打印：4圈墙、5层顶底、35%陀螺填充；压板100%填充。
STL已落床：腿的平整背面朝下、槽口朝上；压板平整背面朝下、凸台朝上。
小腿与压板先关闭支撑并检查切片；可选大腿需检查安装耳台阶的局部支撑。

冷却、清理毛边后，断电试装：
1. 舵臂圆根和臂片能否自然完整落入槽内，圆根到臂片连接处是否还卡。
2. 尖端是否还有一点余量，不能顶住槽端。
3. 再装配套压板和M2紧固件，确认中央螺钉可安装、根部不被顶起。
4. 轻拧紧后检查轴向窜动和槽内转动松量；过松或压板不贴合时反馈厚度/间隙及照片。
小腿压板可备M2×12，以实际螺母、垫片和舵机壳体避让为准，不强拧、不硬塞。

已试装：窗口能穿过、略松，安装耳孔能对齐。尚未实试：M2螺钉、完全入槽后的深度及压板夹持。
这些几何和网格检查不能替代实物配合、承重及运动试验。
'''
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
    for name,raw in files.items():z.writestr(name,raw)
    z.writestr('README_先读我.txt',notes)
    z.writestr('manifest.json',json.dumps(manifest,indent=2))
with zipfile.ZipFile(out) as z:
    assert z.testzip() is None
    for name,raw in files.items():assert z.read(name)==raw
print(str(out));print('Retest shin + knee clamp; optional left thigh + hip clamp; all x1; meshes and ZIP verified')
