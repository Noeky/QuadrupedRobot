"""Depth-correct CAD preview with VTK; does not change prototype geometry."""
import sys,json
from pathlib import Path
from project_paths import IMAGE_DIR, REPORT_DIR, STEP_DIR

import cadquery as cq
import vtk
from PIL import Image,ImageDraw,ImageFont
OUT=IMAGE_DIR
assy=cq.importers.importStep(str(STEP_DIR/'quadruped_prototype_assembly.step')).val()
bb=assy.BoundingBox()
(REPORT_DIR/'assembly_bounds.json').write_text(json.dumps(dict(size_mm=[round(bb.xlen,2),round(bb.ylen,2),round(bb.zlen,2)],bounds_mm=[round(v,2) for v in [bb.xmin,bb.ymin,bb.zmin,bb.xmax,bb.ymax,bb.zmax]]),indent=2))
renderer=vtk.vtkRenderer();renderer.SetBackground(.97,.98,.99)
for shape in assy.Solids():
    verts,tris=shape.tessellate(.12,.2)
    pts=vtk.vtkPoints()
    for v in verts:pts.InsertNextPoint(v.x,v.y,v.z)
    cells=vtk.vtkCellArray()
    for t in tris:
        cells.InsertNextCell(3)
        for i in t:cells.InsertCellPoint(i)
    data=vtk.vtkPolyData();data.SetPoints(pts);data.SetPolys(cells)
    normals=vtk.vtkPolyDataNormals();normals.SetInputData(data);normals.SetFeatureAngle(35)
    mapper=vtk.vtkPolyDataMapper();mapper.SetInputConnection(normals.GetOutputPort())
    actor=vtk.vtkActor();actor.SetMapper(mapper)
    vol=shape.Volume()
    if vol>30000:color=(.48,.55,.61)
    elif 6000<vol<7000:color=(.40,.68,.49)
    elif vol>5000:color=(.15,.38,.75)
    elif 3000<vol<5000:color=(.90,.49,.18)
    else:color=(.84,.79,.64)
    actor.GetProperty().SetColor(*color);actor.GetProperty().SetSpecular(.25)
    renderer.AddActor(actor)
camera=renderer.GetActiveCamera();camera.SetPosition(210,-300,180);camera.SetFocalPoint(0,0,-25);camera.SetViewUp(0,0,1)
renderer.ResetCamera();camera.Zoom(1.2)
window=vtk.vtkRenderWindow();window.SetOffScreenRendering(1);window.AddRenderer(renderer);window.SetSize(1300,900);window.Render()
grab=vtk.vtkWindowToImageFilter();grab.SetInput(window);grab.Update()
writer=vtk.vtkPNGWriter();writer.SetFileName(str(OUT/'原型装配预览.png'));writer.SetInputConnection(grab.GetOutputPort());writer.Write()
window.Finalize()
im=Image.open(OUT/'原型装配预览.png').convert('RGB');draw=ImageDraw.Draw(im)
font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',23)
draw.rectangle((0,0,1300,97),fill=(248,250,252))
draw.text((25,12),'无传感器四足机器人 · PLA机械原型 · STEP附件适配',font=font,fill=(30,40,50))
draw.text((25,47),'电池安装未设计；紧固件与线缆未显示；需先验证单腿配合与承重',font=font,fill=(65,75,85))
im.save(OUT/'原型装配预览.png')
print('Assembly bounds mm:',bb.xlen,bb.ylen,bb.zlen)
