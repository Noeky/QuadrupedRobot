"""Import the CadQuery STEP export into SOLIDWORKS and produce native CAD documents.

Pipeline
--------
    cad/prototype/step/<part>.step            -> solidworks/parts/<part>.SLDPRT
    cad/prototype/step/quadruped_..._assembly -> solidworks/assembly/*.SLDASM
    parts + assembly                          -> solidworks/drawings/*.SLDDRW
                                              -> solidworks/drawings/pdf/*.pdf

The STEP files carry imported solids, not native feature trees, so the generated
documents are exact "dumb" bodies: geometry is preserved, modelling history is not.
Sheet views are autodimensioned from the imported edges, and each sheet repeats the
design parameters recorded in docs/reports/parameters.json.

Requires SOLIDWORKS (COM automation, tested with 2026) and pywin32. Run from any
directory:

    python scripts/build_solidworks.py probe
    python scripts/build_solidworks.py parts
    python scripts/build_solidworks.py assembly
    python scripts/build_solidworks.py drawings
    python scripts/build_solidworks.py all --quit
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

import pythoncom
import win32com.client.dynamic as swd
from win32com.client import VARIANT

from project_paths import ROOT, STEP_DIR, REPORT_DIR

# --------------------------------------------------------------------------- paths
SW_DIR = ROOT / 'solidworks'
PART_DIR = SW_DIR / 'parts'
ASSY_DIR = SW_DIR / 'assembly'
ASSY_COMPONENT_DIR = ASSY_DIR / 'components'
DRAW_DIR = SW_DIR / 'drawings'
PDF_DIR = DRAW_DIR / 'pdf'
REPORT_PATH = SW_DIR / 'generation_report.json'

ASSEMBLY_STEP = STEP_DIR / 'quadruped_prototype_assembly.step'
ASSEMBLY_BASENAME = 'quadruped_prototype'

TEMPLATE_DIR = Path(r'C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2026\templates')
GB_DRAWING_TEMPLATES = {
    'A2': TEMPLATE_DIR / 'gb_a2.drwdot',
    'A3': TEMPLATE_DIR / 'gb_a3.drwdot',
    'A4': TEMPLATE_DIR / 'gb_a4.drwdot',
}

# ---------------------------------------------------------- SOLIDWORKS enum values
# Values read from the installed swconst.tlb, so they match this SOLIDWORKS build.
swDocPART, swDocASSEMBLY, swDocDRAWING = 1, 2, 3
swOpenDocOptions_Silent = 1
swSaveAsCurrentVersion = 0
swSaveAsOptions_Silent = 1
swCustomInfoText = 30
swAutodimEntitiesBasedOnPreselect, swAutodimEntitiesAll = 0, 1
swAutodimSchemeBaseline = 1
swAutodimSchemeOrdinate = 2
swAutodimHorizontalPlacementAbove = 1
swAutodimVerticalPlacementLeft = -1
swDisplayModeShadedEdges = 7
swBomTypePartsOnly = 1
swBomAnchorTopRight = 2

# swUserPreferenceToggle_e values. 3D Interconnect keeps the imported bodies linked to
# the STEP file and unpacks them into %TEMP% on every open, which leaves an assembly
# that cannot be handed in on its own; the classic importer makes real part documents.
# swImportDissolveTopLevelAssemblyOnOpen drops the extra nesting level the STEP export
# adds, so the assembly has its 34 components directly at the top level.
PREF_ENABLE_3D_INTERCONNECT = 691
PREF_DISSOLVE_TOP_LEVEL_ASSEMBLY = 701
IMPORT_PREFERENCES = {
    'swMultiCAD_Enable3DInterconnect': PREF_ENABLE_3D_INTERCONNECT,
    'swImportDissolveTopLevelAssemblyOnOpen': PREF_DISSOLVE_TOP_LEVEL_ASSEMBLY,
}

DENSITY_PLA_G_PER_MM3 = 0.00124  # PLA filament, 1.24 g/cm^3
NOTE_TEXT_HEIGHT = 0.0035         # 3.5 mm text on the drawing sheet

# Sheet layouts in metres (bottom-left origin). Positions keep every view clear of the
# GB title block (bottom-right 180x56 mm) and the 20 mm 附加栏 strip on the left.
VIEW_LAYOUTS = {
    'A2': {'front': (0.180, 0.300), 'top': (0.180, 0.150),
           'left': (0.400, 0.300), 'iso': (0.400, 0.150)},
    'A3': {'front': (0.155, 0.225), 'top': (0.155, 0.125),
           'left': (0.315, 0.245), 'iso': (0.315, 0.155)},
    'A4': {'front': (0.100, 0.160), 'top': (0.100, 0.100),
           'left': (0.235, 0.160), 'iso': (0.235, 0.100)},
}
# CreateText2 anchors the top-left of the block and flows downwards, so the anchor sits
# high enough for the longest 技术要求 list to stay inside the frame.
NOTE_POSITION = {'A2': (0.028, 0.060), 'A3': (0.028, 0.060), 'A4': (0.026, 0.055)}

# The GB template ships an empty title block (no $PRPSHEET links), so the identifying
# fields are written as notes into the matching cells. Offsets are measured from the
# bottom-left corner of the 180x56 mm block, which sits 5 mm from both sheet edges.
# Bottom-left corner of the 180x56 mm title block. The A2 template keeps a 10 mm frame
# margin while A3 uses 5 mm, so these are measured per sheet size (see the PDF probe).
TITLE_BLOCK_ORIGIN = {
    'A2': (0.404, 0.010),
    'A3': (0.240, 0.005),
    'A4': (0.112, 0.005),
}
TITLE_BLOCK_WIDTH = 0.180
TITLE_BLOCK_HEIGHT = 0.056
TITLE_BLOCK_FIELDS = (
    # (x, y from the bottom of the block, text, text height)
    (0.0780, 0.0520, 'identity', 0.0035),
    (0.0095, 0.0215, '设计', 0.0035),
    (0.0600, 0.0215, 'date', 0.0035),
    (0.1045, 0.0243, 'weight', 0.0025),
)

# ------------------------------------------------------------------ part metadata
@dataclass
class PartSpec:
    key: str
    cn: str
    title: str            # 图纸名称 shown in the GB title block
    qty: str
    scale: tuple[int, int]  # drawing view scale for the main views
    function: str
    reqs: list[str] = field(default_factory=list)


PARTS: list[PartSpec] = [
    PartSpec(
        key='body', cn='主体平台', title='主体平台', qty='1', scale=(1, 1),
        function='主平台与四个髋舵机安装框一体打印；四角长槽用于扎带固定通用托盘。',
        reqs=[
            '主平台 120×80×3，四周安装耳支架与加强肋一体打印，整体打印包络约 126.65×90×27.5。',
            '舵机安装窗口 23.1×13.3，安装孔 ⌀2.2，孔距 27.7；须以实物舵机耳孔对位确认后使用。',
            '髋轴前后位置 ±43，左右位置 ±54。',
            '长槽仅用于扎带/绑带固定，不作电池安装孔使用。',
            '材料 PLA，FDM 打印；层高 0.2，壁厚≥4 圈，填充 30%～40%，孔周围局部 100% 填充。',
            '未注圆角 R2，未注倒角 C0.5。',
            '打印时主平台顶面朝下、安装框朝上；窗口桥接处按切片预览决定局部支撑。',
        ],
    ),
    PartSpec(
        key='thigh_left', cn='左大腿', title='左大腿（髋关节臂）', qty='2', scale=(2, 1),
        function='髋关节臂与膝舵机安装框一体打印，髋端包覆槽配原装转头，膝端安装膝舵机。',
        reqs=[
            '大腿轴距 40，为平行关节轴在 XZ 平面内的垂直距离。',
            '髋端包覆槽为原装转头的近似包络：侧向预留 0.2，轴向预留 0.1，配合松紧以单腿试片确认。',
            '膝舵机输出轴比髋轴向外偏 15，为大腿支架与小腿留出轴向空间。',
            '膝端安装窗口与主体一致：窗口 23.1×13.3，安装孔 ⌀2.2，孔距 27.7。',
            '转头压板孔为 ⌀2.2 通孔两处，距回转中心 8、两孔间距 13，需螺母与垫片。',
            '材料 PLA，FDM 打印；宽面平放，层高 0.2，填充 30%～40%。',
            '未注圆角 R2，未注倒角 C0.5。',
            '左右大腿为镜像件，不得用左件重复打印四件替代右件。',
        ],
    ),
    PartSpec(
        key='thigh_right', cn='右大腿（镜像）', title='右大腿（镜像）', qty='2', scale=(2, 1),
        function='左大腿的镜像件，轴距与接口尺寸与左大腿相同。',
        reqs=[
            '除镜像外尺寸与左大腿一致，可与左件对照检查。',
            '安装时按整机装配 STEP 的镜像关系摆放，不得与左件混用。',
            '材料 PLA，FDM 打印；宽面平放，层高 0.2，填充 30%～40%。',
            '未注圆角 R2，未注倒角 C0.5。',
        ],
    ),
    PartSpec(
        key='shin', cn='小腿', title='小腿', qty='4', scale=(2, 1),
        function='小腿杆件，膝端包覆槽配原装转头，足端为圆弧 PLA 轮廓。',
        reqs=[
            '小腿轴距 45，为平行关节轴在 XZ 平面内的垂直距离。',
            '膝端包覆槽与髋端同规格：侧向间隙 0.2，轴向间隙 0.1，以单腿试片确认。',
            '足端为圆弧轮廓，可在实物调试时加薄橡胶防滑垫。',
            '右侧安装时须绕长向翻面，使槽口朝向原装转头；不得仅按打印床朝向判断安装方向。',
            '材料 PLA，FDM 打印；宽面平放，层高 0.2，填充 30%～40%。',
            '未注圆角 R2，未注倒角 C0.5。',
        ],
    ),
    PartSpec(
        key='hip_horn_clamp', cn='髋转头压板', title='髋转头压板', qty='4', scale=(2, 1),
        function='与大腿包覆槽共同限制原装转头脱出；圆筒凸台穿过中心大孔。',
        reqs=[
            '两处 ⌀2.2 通孔，距回转中心 8、两孔间距 13，需 M2 螺钉/螺母与垫片（试装起点 M2×10）。',
            '中心大孔 ⌀7.2，用于通过原装转头中心螺钉。',
            '与包覆槽侧向预留 0.2、轴向预留 0.1；接触后仍可能留有间隙，主要限制转头脱出，不保证预紧夹持。',
            '材料 PLA，FDM 打印；层高 0.2，孔周围 100% 填充。',
        ],
    ),
    PartSpec(
        key='knee_horn_clamp', cn='膝转头压板', title='膝转头压板', qty='4', scale=(2, 1),
        function='与小膝包覆槽共同限制原装转头脱出。',
        reqs=[
            '几何与髋转头压板相同，绕长轴翻面可互换；分件命名以便装配识别。',
            '两处 ⌀2.2 通孔，距回转中心 8、两孔间距 13；中心大孔 ⌀7.2。',
            '材料 PLA，FDM 打印；层高 0.2，孔周围 100% 填充。',
        ],
    ),
    PartSpec(
        key='universal_tray', cn='通用主板托盘', title='通用主板托盘', qty='0～1', scale=(1, 1),
        function='暂定主板托盘，通过长槽用扎带固定到主体；不含 PCB 专用孔。',
        reqs=[
            '托盘 70×50×2，两处长槽与主体长槽对应，用扎带/绑带固定。',
            '主板实际尺寸未知，PCB 固定孔位暂未确定，托盘可调整或暂不打印。',
            '材料 PLA，FDM 打印；层高 0.2，填充 30%～40%。',
            '本件不作为电池安装结构；电池仅记录为 603040、3.7 V、800 mAh。',
        ],
    ),
]

PART_BY_KEY = {spec.key: spec for spec in PARTS}


# ------------------------------------------------------------------------ helpers
def byref_int():
    return VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)


def byref_double():
    return VARIANT(pythoncom.VT_BYREF | pythoncom.VT_R8, 0.0)


def dbl_array(values):
    return VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [float(v) for v in values])


def out_value(variant):
    value = getattr(variant, 'value', variant)
    if isinstance(value, tuple):
        return value[0]
    return value


def call(obj, name, *args):
    """Call a SOLIDWORKS API member.

    pywin32's late binding hands back zero-argument ``Get*`` members as already
    evaluated property values, so plain ``obj.GetThing()`` raises
    "'str' object is not callable". This wrapper accepts both shapes.
    """
    attribute = getattr(obj, name)
    if args:
        return attribute(*args)
    if callable(attribute):
        return attribute()
    return attribute


def connect(visible=True):
    app = swd.Dispatch('SldWorks.Application')
    try:
        app.Visible = bool(visible)
    except Exception:
        pass
    return app


def get_toggle(app, index):
    try:
        return bool(out_value(call(app, 'GetUserPreferenceToggle', index)))
    except Exception:
        return None


def set_toggle(app, index, value):
    try:
        call(app, 'SetUserPreferenceToggle', index, bool(value))
        return True
    except Exception:
        return False


def apply_import_preferences(app, report):
    """Temporarily switch off 3D Interconnect and flatten the imported assembly.

    The original values are returned so they can be restored, leaving the user's
    SOLIDWORKS settings exactly as they were.
    """
    original = {name: get_toggle(app, index) for name, index in IMPORT_PREFERENCES.items()}
    applied = {
        'swMultiCAD_Enable3DInterconnect': set_toggle(app, PREF_ENABLE_3D_INTERCONNECT, False),
        'swImportDissolveTopLevelAssemblyOnOpen':
            set_toggle(app, PREF_DISSOLVE_TOP_LEVEL_ASSEMBLY,
                       DISSOLVE_TOP_LEVEL_ASSEMBLY),
    }
    report['import_preferences'] = {'original': original, 'changed': applied}
    return original


# Overridden by --keep-hierarchy: dissolving the top level is convenient but the
# importer crashed on this STEP with it enabled.
DISSOLVE_TOP_LEVEL_ASSEMBLY = True


def reset_import_preferences(app, report):
    """Put back the settings this machine shipped with (3D Interconnect on, no dissolve)."""
    report['preferences_reset'] = {
        'swMultiCAD_Enable3DInterconnect': set_toggle(app, PREF_ENABLE_3D_INTERCONNECT, True),
        'swImportDissolveTopLevelAssemblyOnOpen':
            set_toggle(app, PREF_DISSOLVE_TOP_LEVEL_ASSEMBLY, False),
    }
    return report['preferences_reset']


def restore_import_preferences(app, original):
    for name, value in (original or {}).items():
        if value is not None:
            set_toggle(app, IMPORT_PREFERENCES[name], value)


def wait_for_idle(app, timeout=300):
    """Block until SOLIDWORKS reports no command in progress (startup finishes)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if not out_value(app.CommandInProgress):
                return True
        except Exception:
            pass
        time.sleep(1.0)
    return False


def open_doc(app, path, doc_type):
    errors, warnings = byref_int(), byref_int()
    doc = app.OpenDoc6(str(path), doc_type, swOpenDocOptions_Silent, '', errors, warnings)
    if doc is None:
        raise RuntimeError(
            f'OpenDoc6 failed for {path} (errors={out_value(errors)}, warnings={out_value(warnings)})')
    return doc


def import_foreign(app, path):
    """Import a neutral format (STEP) through the foreign-file importer.

    OpenDoc6 rejects these files with swFileRequiresRepairError (2097152); routing them
    through an explicit IImportStepData object is the call that actually imports them.
    """
    path = str(path)
    import_data = call(app, 'GetImportFileData', path)
    errors = byref_int()
    doc = app.LoadFile4(path, 'r', import_data, errors)
    if doc is None:
        raise RuntimeError(
            f'LoadFile4 failed for {path} (errors={out_value(errors)})')
    return doc


def save_as(doc, target):
    """Save (or export) the document to ``target``; the extension picks the format.

    Every overload listed in sldworks.tlb is tried in turn because the working one
    depends on the SOLIDWORKS build; the diagnostics of each attempt are collected so
    a failure reports the real swFileSaveError_e code instead of a bare False.
    """
    target = str(target)
    Path(target).parent.mkdir(parents=True, exist_ok=True)
    extension = doc.Extension

    def attempt(name, fn):
        errors, warnings = byref_int(), byref_int()
        try:
            ok = fn(errors, warnings)
        except Exception as exc:
            return name, False, f'{type(exc).__name__}: {exc}'
        if ok:
            return name, True, f'errors={out_value(errors)} warnings={out_value(warnings)}'
        return name, False, f'False (errors={out_value(errors)} warnings={out_value(warnings)})'

    attempts = (
        # IModelDoc2.SaveAs4 is the overload that works reliably through late binding.
        ('Model.SaveAs4', lambda e, w: doc.SaveAs4(
            target, swSaveAsCurrentVersion, swSaveAsOptions_Silent, e, w)),
        ('Extension.SaveAs', lambda e, w: extension.SaveAs(
            target, swSaveAsCurrentVersion, swSaveAsOptions_Silent, None, e, w)),
        ('Extension.SaveAs3', lambda e, w: extension.SaveAs3(
            target, swSaveAsCurrentVersion, swSaveAsOptions_Silent, None, None, e, w)),
        ('Extension.SaveAs2', lambda e, w: extension.SaveAs2(
            target, swSaveAsCurrentVersion, swSaveAsOptions_Silent, None, '', False, e, w)),
        ('Model.SaveAs2', lambda e, w: doc.SaveAs2(
            target, swSaveAsCurrentVersion, False, True)),
    )
    log = []
    for name, fn in attempts:
        name, ok, detail = attempt(name, fn)
        log.append(f'{name}: {detail}')
        if ok:
            return name, detail, log
    raise RuntimeError(f'could not save {target}\n  ' + '\n  '.join(log))


def set_props(doc, props):
    """Write document-level custom properties (feeds the $PRPSHEET links in the title block)."""
    written = {}
    try:
        manager = doc.Extension.CustomPropertyManager('')
    except Exception as exc:
        return {'error': str(exc)}
    for name, value in props.items():
        if value is None:
            continue
        try:
            code = manager.Add3(str(name), swCustomInfoText, str(value), 2)
            written[str(name)] = f'ok({out_value(code)})'
        except Exception as exc:
            written[str(name)] = f'failed({exc})'
    return written


def close_doc(app, doc):
    try:
        app.CloseDoc(str(call(doc, 'GetTitle')))
    except Exception:
        pass


def load_validation():
    """Volume/quantity data from the CadQuery validation report (for weight estimates)."""
    path = REPORT_DIR / 'validation.json'
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return data.get('parts', {})
    except Exception:
        return {}


def part_notes(spec: PartSpec, volume_mm3=None) -> str:
    lines = ['技术要求']
    for index, req in enumerate(spec.reqs, start=1):
        lines.append(f'{index}. {req}')
    lines.append(f'{len(spec.reqs) + 1}. 未注尺寸以三维模型为准；本件来自 STEP 导入实体，'
                 '模型参数见 docs/reports/parameters.json。')
    if volume_mm3:
        lines.append(f'{len(spec.reqs) + 2}. 单件体积约 {volume_mm3:.1f} mm³，'
                     f'PLA 估算质量约 {volume_mm3 * DENSITY_PLA_G_PER_MM3:.2f} g。')
    return '\n'.join(lines)


def select_view(doc, view):
    doc.ClearSelection2(True)
    try:
        name = call(view, 'GetName2')
    except Exception:
        name = call(view, 'GetName')
    try:
        doc.Extension.SelectByID2(str(name), 'DRAWINGVIEW', 0, 0, 0, False, 0, None, 0)
    except Exception:
        pass
    return view


def autodimension(doc, view, scheme=swAutodimSchemeOrdinate):
    """Autodimension a view; returns the swAutodimStatus_e code.

    swAutodimEntitiesAll is what actually produces dimensions here; the preselect and
    selected modes return swAutodimStatusBadOptionValue on this build. The ordinate
    scheme keeps the stack compact - baseline and chain run off the sheet.
    """
    select_view(doc, view)
    try:
        status = doc.AutoDimension(swAutodimEntitiesAll, scheme,
                                   swAutodimHorizontalPlacementAbove, scheme,
                                   swAutodimVerticalPlacementLeft)
        return out_value(status)
    except Exception as exc:
        return f'error: {exc}'


def add_note(doc, text, x, y, height=NOTE_TEXT_HEIGHT):
    """Place a text block on the sheet.

    InsertNote only works while a view is active, so the explicit
    IDrawingDoc::CreateText2 position/height form is used instead.
    """
    for call_name, args in (
        ('CreateText2', (text, float(x), float(y), 0.0, float(height), 0.0)),
        ('CreateText', (text, float(x), float(y), 0.0, float(height), 0.0)),
    ):
        try:
            note = call(doc, call_name, *args)
        except Exception:
            continue
        if note is not None:
            return call_name
    try:
        note = doc.InsertNote(text)
        if note is not None:
            call(note, 'GetAnnotation').SetPosition2(float(x), float(y), 0.0)
            return 'InsertNote'
    except Exception:
        pass
    return None


def add_title_block_notes(doc, props, template_size, mass_g=None):
    """Write the identifying fields into the (unlinked) GB title block cells."""
    x0, y0 = TITLE_BLOCK_ORIGIN[template_size]
    written = {}
    for dx, dy, key, height in TITLE_BLOCK_FIELDS:
        if key == 'identity':
            text = '\n'.join((
                f"图号  {props.get('Number', '')}",
                f"名称  {props.get('Description', '')}",
                f"材料  {props.get('Material', '')}    数量  {props.get('Quantity', '')}",
            ))
        elif key == '设计':
            text = '第 3 组'
        elif key == 'date':
            text = str(props.get('Date', ''))
        elif key == 'weight':
            text = f'{mass_g:.0f}g' if mass_g else ''
        else:
            text = ''
        if not text:
            continue
        written[key] = add_note(doc, text, x0 + dx, y0 + dy, height)
    return written


def view_scale(view, numerator, denominator):
    try:
        view.ScaleDecimal = float(numerator) / float(denominator)
        return 'ScaleDecimal'
    except Exception:
        pass
    try:
        view.ScaleRatio = dbl_array([float(numerator), float(denominator)])
        return 'ScaleRatio'
    except Exception as exc:
        return f'failed: {exc}'


def view_outline(view):
    try:
        values = call(view, 'GetOutline')
        return [round(float(v), 4) for v in values]
    except Exception:
        return None


def create_views(doc, model_path, model_doc, scale, template_size,
                 keys=('front', 'top', 'left', 'iso')):
    """Create 主视图/俯视图/左视图/轴测图 using this build's localised view names."""
    layout = VIEW_LAYOUTS[template_size]
    view_names = standard_view_names(model_doc)
    created, objects = {}, {}
    for key in keys:
        name = view_names.get(key)
        if not name:
            created[key] = {'error': f'no standard view for {key} in this SOLIDWORKS locale'}
            continue
        x, y = layout[key]
        try:
            view = doc.CreateDrawViewFromModelView3(str(model_path), name, x, y, 0.0)
        except Exception as exc:
            created[key] = {'error': str(exc)}
            continue
        if view is None:
            created[key] = {'error': f'{name}: no view returned'}
            continue
        if key == 'iso':
            view_scale(view, scale[0], scale[1] * 2)
            try:
                view.DisplayMode = swDisplayModeShadedEdges
            except Exception:
                pass
        else:
            view_scale(view, scale[0], scale[1])
        objects[key] = view
        created[key] = {'solidworks_view': name, 'name': str(call(view, 'GetName2')),
                        'scale': scale if key != 'iso' else (scale[0], scale[1] * 2),
                        'outline': view_outline(view)}
    return created, objects


def sheet_scale(doc, numerator, denominator):
    try:
        sheet = call(doc, 'GetCurrentSheet')
        sheet.SetScale(float(numerator), float(denominator), False, 0.0)
        return True
    except Exception:
        return False


def drawing_views(doc):
    """All views on the active sheet (``GetFirstView`` is not reachable late-bound).

    ``GetViews`` comes back as a tuple wrapping the array of views, so the values are
    flattened before use.
    """
    try:
        views = call(doc, 'GetViews')
    except Exception:
        return []
    if views is None:
        return []
    flat, pending = [], [views]
    while pending:
        item = pending.pop(0)
        if isinstance(item, (list, tuple)):
            pending = list(item) + pending
        elif item is not None:
            if not hasattr(item, '_oleobj_'):
                # GetViews hands back bare PyIDispatch objects; wrap them so the
                # property-style API access works the same as for created views.
                try:
                    item = swd.Dispatch(item)
                except Exception:
                    pass
            flat.append(item)
    return flat


view_list = drawing_views


def standard_view_names(model):
    """Map the localised standard view names of this SOLIDWORKS build.

    A Chinese install names them ``*前视`` / ``*上视`` / ``*左视`` / ``*等轴测``, so the
    English ``*Front`` spellings used by most API samples select nothing here.
    """
    try:
        names = [str(name) for name in (call(model, 'GetModelViewNames') or [])]
    except Exception:
        names = []

    def pick(*candidates):
        for candidate in candidates:
            if candidate in names:
                return candidate
        return None

    return {
        'front': pick('*前视', '*Front'),
        'top': pick('*上视', '*Top'),
        'left': pick('*左视', '*Left'),
        'iso': pick('*等轴测', '*Isometric'),
    }


def build_drawing(app, model_path, spec, template_size, out_stem, title_props, notes_md,
                  autodim=True):
    """Create one drawing sheet, autodimension it and export SLDDRW + PDF."""
    template = GB_DRAWING_TEMPLATES[template_size]
    if not template.exists():
        raise RuntimeError(f'missing drawing template {template}')

    model_doc = open_doc(app, model_path, swDocASSEMBLY if str(model_path).lower().endswith(
        '.sldasm') else swDocPART)
    doc = app.NewDocument(str(template), 0, 0, 0)
    if doc is None:
        doc = app.ActiveDoc
    if doc is None:
        raise RuntimeError('NewDocument returned no document')

    info = {'template': str(template), 'views': {}, 'warnings': []}
    scale = spec.scale
    sheet_scale(doc, scale[0], scale[1])

    # The principal view is created first and dimensioned while it is the only view on
    # the sheet, so the autodimension result covers the main view alone.
    info['views'], view_objects = create_views(doc, model_path, model_doc, scale,
                                               template_size, keys=('front',))
    front = view_objects.get('front')
    if autodim and front is not None:
        try:
            info['autodimension_status'] = autodimension(doc, front)
            info['dimension_count'] = _dimension_count(front)
        except Exception as exc:
            info['warnings'].append(f'autodimension: {exc}')
    doc.ClearSelection2(True)

    more, more_objects = create_views(doc, model_path, model_doc, scale, template_size,
                                      keys=('top', 'left', 'iso'))
    info['views'].update(more)
    view_objects.update(more_objects)

    # Notes: key parameters + part specific technical requirements.
    note_x, note_y = NOTE_POSITION[template_size]
    if notes_md:
        method = add_note(doc, notes_md, note_x, note_y)
        info['note_method'] = method
        if method is None:
            info['warnings'].append('note insertion failed')

    mass_g = None
    try:
        if title_props.get('Weight'):
            mass_g = float(title_props['Weight']) * 1000
    except (TypeError, ValueError):
        mass_g = None
    info['title_block'] = add_title_block_notes(doc, title_props, template_size, mass_g)

    info['props'] = set_props(doc, title_props)
    drw_path = DRAW_DIR / f'{out_stem}.SLDDRW'
    pdf_path = PDF_DIR / f'{out_stem}.pdf'
    info['slddrw'] = save_as(doc, drw_path)[0]
    info['pdf'] = save_as(doc, pdf_path)[0]
    close_doc(app, doc)
    close_doc(app, model_doc)
    return info


def _dimension_count(view):
    for attr in ('GetDimensionCount4', 'GetDimensionCount3', 'GetDimensionCount2',
                 'GetDimensionCount', 'GetDisplayDimensionCount'):
        fn = getattr(view, attr, None)
        if fn is None:
            continue
        try:
            return int(out_value(call(view, attr)))
        except Exception:
            continue
    return None


# ------------------------------------------------------------------------- stages
def stage_probe(app, report):
    info = {'revision': None, 'documents': []}
    for attr in ('RevisionNumber', 'GetBuildNumbers2'):
        fn = getattr(app, attr, None)
        if fn is None:
            continue
        try:
            info[attr] = call(app, attr)
        except Exception as exc:
            info[attr] = f'error: {exc}'
    template = GB_DRAWING_TEMPLATES['A3']
    info['drawing_template'] = str(template)
    info['drawing_template_exists'] = template.exists()
    doc = app.NewDocument(str(template), 0, 0, 0)
    if doc is not None:
        title = str(call(doc, 'GetTitle'))
        info['documents'].append(title)
        probe_pdf = PDF_DIR / '_probe_blank_a3.pdf'
        PDF_DIR.mkdir(parents=True, exist_ok=True)
        try:
            info['probe_pdf'] = save_as(doc, probe_pdf)[0]
        except Exception as exc:
            info['probe_pdf_error'] = str(exc)
        close_doc(app, doc)
    report['probe'] = info
    return info


def stage_parts(app, report):
    validation = load_validation()
    report['parts'] = {}
    for spec in PARTS:
        source = STEP_DIR / f'{spec.key}.step'
        target = PART_DIR / f'{spec.key}.SLDPRT'
        entry = {'source': str(source), 'target': str(target), 'exists': source.exists()}
        if not source.exists():
            entry['error'] = 'missing STEP'
            report['parts'][spec.key] = entry
            continue
        try:
            doc = import_foreign(app, source)
        except Exception as exc:
            entry['error'] = str(exc)
            report['parts'][spec.key] = entry
            continue
        try:
            volume = (validation.get(spec.key) or {}).get('volume_mm3')
            entry['volume_mm3'] = volume
            entry['mass_g'] = round(volume * DENSITY_PLA_G_PER_MM3, 2) if volume else None
            entry['props'] = set_props(doc, {
                'Number': f'QR-P-{spec.key}',
                'Description': spec.cn,
                'Title': spec.title,
                'Material': 'PLA',
                'Weight': f'{volume * DENSITY_PLA_G_PER_MM3 / 1000:.4f}' if volume else '',
                'Quantity': spec.qty,
                'Comment': spec.function,
            })
            entry['save'] = save_as(doc, target)[0]
            entry['sldprt'] = target.name
            entry['target_exists'] = target.exists()
        except Exception as exc:
            entry['error'] = str(exc)
            entry['traceback'] = traceback.format_exc()
        finally:
            close_doc(app, doc)
        report['parts'][spec.key] = entry
    return report['parts']


def stage_assembly(app, report):
    entry = {'source': str(ASSEMBLY_STEP), 'exists': ASSEMBLY_STEP.exists()}
    if not ASSEMBLY_STEP.exists():
        entry['error'] = 'missing assembly STEP'
        report['assembly'] = entry
        return entry
    doc = None
    attempts = []
    for label, opener in (('OpenDoc6(assembly)', lambda: open_doc(app, ASSEMBLY_STEP, swDocASSEMBLY)),
                          ('LoadFile4', lambda: import_foreign(app, ASSEMBLY_STEP))):
        try:
            doc = opener()
        except Exception as exc:
            attempts.append(f'{label}: {exc}')
            continue
        if doc is not None:
            attempts.append(f'{label}: ok')
            break
    entry['attempts'] = attempts
    if doc is None:
        entry['error'] = 'no importer worked'
        report['assembly'] = entry
        return entry
    try:
        entry['document_type'] = out_value(call(doc, 'GetType'))
        entry['title'] = str(call(doc, 'GetTitle'))
        entry['components_before'] = _component_names(doc)
        if entry['components_before']:
            entry['component_count'] = len(entry['components_before'])
        entry['props'] = set_props(doc, {
            'Number': 'QR-A-001',
            'Description': '无传感器四足机器人 PLA 机械原型',
            'Title': '四足机器人装配体',
            'Material': 'PLA',
            'Date': time.strftime('%Y-%m-%d'),
        })
        for stale in list(ASSY_COMPONENT_DIR.glob('*.SLDPRT')) + \
                list(ASSY_COMPONENT_DIR.glob('*.SLDASM')):
            try:
                stale.unlink()
            except OSError:
                pass
        entry['externalised'] = externalise_components(app, doc, ASSY_COMPONENT_DIR)
        entry['externalised_count'] = sum(
            1 for item in entry['externalised'] if item.get('target_exists'))
        target = ASSY_DIR / f'{ASSEMBLY_BASENAME}.SLDASM'
        entry['save'] = save_as(doc, target)[0]
        entry['sldasm'] = target.name
    except Exception as exc:
        entry['error'] = str(exc)
        entry['traceback'] = traceback.format_exc()
    finally:
        close_doc(app, doc)
    entry['created_files'] = sorted(p.name for p in ASSY_DIR.glob('*'))
    report['assembly'] = entry
    return entry


def _component_names(doc):
    names = []
    try:
        comps = doc.GetComponents(False)
        for comp in comps:
            names.append(str(comp.Name2))
    except Exception:
        return None
    return names


# Product names written by scripts/build_prototype.py into the assembly STEP. Stripping
# the trailing instance counter gives clean component file names.
ASSEMBLY_PRODUCT_STEMS = (
    'body', 'tray',
    *[f'{pos}_{side}_{part}'
      for pos in ('front', 'rear') for side in ('left', 'right')
      for part in ('hip_servo', 'hip_horn', 'thigh', 'hip_clamp',
                   'knee_servo', 'knee_horn', 'shin', 'knee_clamp')],
)


def component_stem(name):
    """'...\\rear_right_thigh_4.step.SLDPRT' -> 'rear_right_thigh'."""
    leaf = str(name).replace('/', '\\').rsplit('\\', 1)[-1]
    for extension in ('.SLDPRT', '.SLDASM'):
        if leaf.upper().endswith(extension):
            leaf = leaf[: -len(extension)]
    for suffix in ('.step-1', '.stp-1', '.step', '.stp', '.STEP', '.STP'):
        if leaf.lower().endswith(suffix.lower()):
            leaf = leaf[: -len(suffix)]
    for stem in sorted(ASSEMBLY_PRODUCT_STEMS, key=len, reverse=True):
        if leaf == stem:
            return stem
        prefix = stem + '_'
        if leaf.startswith(prefix) and leaf[len(prefix):].isdigit():
            return stem
    return leaf


def externalise_components(app, doc, out_dir):
    """Move the STEP importer's scratch documents into the project folder.

    The importer parks every component in ``%TEMP%\\swx*\\IC~~``; those files are
    deleted with the session, so the assembly would lose its references. Saving each
    scratch document into ``out_dir`` re-points the open assembly at the new paths.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for model in imported_scratch_documents(app, doc):
        entry = {}
        try:
            source = str(call(model, 'GetPathName') or '')
        except Exception as exc:
            entry['error'] = f'GetPathName: {exc}'
            results.append(entry)
            continue
        entry['source'] = source
        stem = component_stem(source.rsplit('\\', 1)[-1])
        suffix = '.SLDASM' if source.lower().endswith('.sldasm') else '.SLDPRT'
        target = out_dir / f'{stem}{suffix}'
        try:
            entry['save'] = save_as(model, target)[0]
            entry['target'] = str(target)
            entry['target_exists'] = target.exists()
            entry['target_kb'] = round(target.stat().st_size / 1024, 1) if target.exists() else 0
        except Exception as exc:
            entry['error'] = str(exc)
        results.append(entry)
    return results


def iter_documents(app):
    """Every document currently loaded in the SOLIDWORKS session."""
    documents = []
    try:
        value = call(app, 'GetDocuments')
    except Exception:
        value = None
    if value:
        documents = list(value)
    if documents:
        return documents
    try:
        enum = call(app, 'EnumDocuments2')
    except Exception:
        return documents
    while enum is not None:
        try:
            chunk = enum.Next(1)
        except Exception:
            break
        if not chunk:
            break
        if isinstance(chunk, (list, tuple)):
            documents.extend(chunk)
        else:
            documents.append(chunk)
    return documents


def imported_scratch_documents(app, assembly_doc):
    """Scratch documents referenced by this import, inside %TEMP%\\swx*\\IC~~.

    The scratch folder is shared by earlier imports, so the component paths of the
    current assembly decide which documents belong to this run.
    """
    try:
        own_path = str(call(assembly_doc, 'GetPathName') or '')
    except Exception:
        own_path = ''
    referenced = set()
    try:
        for comp in assembly_doc.GetComponents(False) or []:
            path = str(call(comp, 'GetPathName') or '')
            if path:
                referenced.add(path.lower())
    except Exception:
        pass
    scratch = []
    for model in iter_documents(app):
        try:
            path = str(call(model, 'GetPathName') or '')
        except Exception:
            continue
        if not path or path == own_path:
            continue
        lowered = path.lower()
        if 'ic~~' not in lowered or '\\temp\\swx' not in lowered:
            continue
        if referenced and lowered not in referenced:
            continue
        scratch.append(model)
    scratch.sort(key=lambda m: str(call(m, 'GetPathName')))
    return scratch


def stage_drawings(app, report):
    report['drawings'] = {}
    PDF_DIR.mkdir(parents=True, exist_ok=True)

    for spec in PARTS:
        model = PART_DIR / f'{spec.key}.SLDPRT'
        entry = {'model': str(model)}
        if not model.exists():
            entry['error'] = 'missing part; run the parts stage first'
            report['drawings'][spec.key] = entry
            continue
        volume = (load_validation().get(spec.key) or {}).get('volume_mm3')
        props = {
            'Number': f'QR-P-{spec.key}',
            'Description': spec.cn,
            'Title': spec.title,
            'Material': 'PLA',
            'Quantity': spec.qty,
            'Weight': f'{volume * DENSITY_PLA_G_PER_MM3 / 1000:.4f}' if volume else '',
            'Scale': f'{spec.scale[0]}:{spec.scale[1]}',
            'Designer': '第 3 组',
            'DrawnBy': '第 3 组',
            'Date': time.strftime('%Y-%m-%d'),
            'CompanyName': '北京大学《先进制造与机器人实践》',
        }
        try:
            entry.update(build_drawing(app, model, spec, 'A3', f'零件图_{spec.key}',
                                       props, part_notes(spec, volume)))
        except Exception as exc:
            entry['error'] = str(exc)
            entry['traceback'] = traceback.format_exc()
        report['drawings'][spec.key] = entry

    assembly = ASSY_DIR / f'{ASSEMBLY_BASENAME}.SLDASM'
    entry = {'model': str(assembly)}
    if not assembly.exists():
        entry['error'] = 'missing assembly; run the assembly stage first'
        report['drawings']['assembly'] = entry
        return report['drawings']
    assembly_spec = PartSpec(
        key='assembly', cn='四足机器人装配体', title='无传感器四足机器人装配图',
        qty='1', scale=(1, 1), function='整机装配',
        reqs=[
            '装配包络约 142×147×102.11（含腿的圆弧足端），不含紧固件与线缆。',
            '髋轴 ±43 / ±54，大腿轴距 40，小腿轴距 45；四条腿在平行平面内运动，无侧摆关节。',
            '膝舵机输出轴较髋轴外偏 15；右腿按镜像装配，小腿与压板绕长向翻面使槽口朝向转头。',
            '每腿：髋/膝舵机各 1、原装转头 2、大腿 1、小腿 1、转头压板 2；整机 8 舵机 8 转头。',
            '紧固件：压板 2 套/处共 16 套，舵机安装耳 2 套/处共 16 套；试装起点 M2×10 与 M2×8。',
            '本图为静态装配检查模型，未经实物试装、承重、连续运动与行走验证。',
            '零件明细见 solidworks/README.md；模型参数见 docs/reports/parameters.json。',
        ],
    )
    try:
        entry.update(build_drawing(app, assembly, assembly_spec, 'A2',
                                   '装配图_quadruped_prototype',
                                   {
                                       'Number': 'QR-A-001',
                                       'Description': '无传感器四足机器人 PLA 机械原型',
                                       'Title': '四足机器人装配图',
                                       'Material': 'PLA',
                                       'Quantity': '1',
                                       'Weight': '0.147',
                                       'Scale': '1:1',
                                       'Designer': '第 3 组',
                                       'DrawnBy': '第 3 组',
                                       'Date': time.strftime('%Y-%m-%d'),
                                       'CompanyName': '北京大学《先进制造与机器人实践》',
                                   },
                                   part_notes(assembly_spec, None),
                                   autodim=False))
    except Exception as exc:
        entry['error'] = str(exc)
        entry['traceback'] = traceback.format_exc()
    report['drawings']['assembly'] = entry
    return report['drawings']


def stage_verify(app, report):
    """Reopen the generated documents from disk and check every reference resolves.

    Run this in a fresh SOLIDWORKS session: the STEP importer's scratch folder is
    deleted when the previous session exits, so anything still pointing there shows
    up as a missing reference.
    """
    info = {'part_checks': [], 'missing_references': []}

    for spec in PARTS:
        path = PART_DIR / f'{spec.key}.SLDPRT'
        entry = {'key': spec.key, 'path': str(path), 'exists': path.exists()}
        if path.exists():
            entry['size_kb'] = round(path.stat().st_size / 1024, 1)
            try:
                doc = open_doc(app, path, swDocPART)
                entry['opened'] = True
                try:
                    entry['bodies'] = len(doc.GetBodies2(0, True) or [])
                except Exception:
                    entry['bodies'] = None
                close_doc(app, doc)
            except Exception as exc:
                entry['opened'] = False
                entry['error'] = str(exc)
        info['part_checks'].append(entry)

    assembly = ASSY_DIR / f'{ASSEMBLY_BASENAME}.SLDASM'
    info['assembly'] = {'path': str(assembly), 'exists': assembly.exists()}
    if not assembly.exists():
        report['verify'] = info
        return info

    doc = open_doc(app, assembly, swDocASSEMBLY)
    try:
        info['assembly']['opened'] = True
        components = doc.GetComponents(False) or []
        info['assembly']['component_count'] = len(components)
        top_level = []
        for comp in doc.GetComponents(True) or []:
            top_level.append({
                'name': str(comp.Name2),
                'path': str(call(comp, 'GetPathName') or ''),
            })
        info['assembly']['top_level'] = top_level
        referenced = []
        for comp in components:
            path = str(call(comp, 'GetPathName') or '')
            referenced.append(path)
            if not path or not Path(path).exists():
                info['missing_references'].append(path or '<empty>')
            elif str(APP_ROOT) not in path:
                info['missing_references'].append(f'outside project: {path}')
        info['assembly']['distinct_referenced_files'] = len(set(referenced))
        try:
            props = call(doc.Extension, 'CreateMassProperty')
            info['assembly']['mass_kg'] = round(float(props.Mass), 4)
            info['assembly']['volume_mm3'] = round(float(props.Volume) * 1e9, 1)
        except Exception as exc:
            info['assembly']['mass_error'] = str(exc)
    finally:
        close_doc(app, doc)
    report['verify'] = info
    return info


# Root prefix used to prove that no reference still points at a scratch folder.
APP_ROOT = SW_DIR


STAGES = {
    'probe': stage_probe,
    'parts': stage_parts,
    'assembly': stage_assembly,
    'drawings': stage_drawings,
    'verify': stage_verify,
}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stages', nargs='*', default=['all'], metavar='STAGE',
                        help=f"any of: all, {', '.join(STAGES)}")
    parser.add_argument('--quit', action='store_true', help='close SOLIDWORKS when done')
    parser.add_argument('--invisible', action='store_true', help='start SOLIDWORKS hidden')
    parser.add_argument('--keep-hierarchy', action='store_true',
                        help='do not dissolve the top-level sub-assembly on STEP import')
    parser.add_argument('--reset-preferences', action='store_true',
                        help='restore 3D Interconnect / dissolve preferences and stop')
    args = parser.parse_args(argv)

    unknown = [name for name in args.stages if name != 'all' and name not in STAGES]
    if unknown:
        parser.error(f'unknown stage(s): {", ".join(unknown)}; '
                     f'choose from {", ".join(["all", *STAGES])}')

    global DISSOLVE_TOP_LEVEL_ASSEMBLY
    DISSOLVE_TOP_LEVEL_ASSEMBLY = not args.keep_hierarchy

    if args.reset_preferences:
        app = connect(visible=not args.invisible)
        report = {'stages': ['reset-preferences']}
        reset_import_preferences(app, report)
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                               encoding='utf-8')
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    if 'all' in args.stages:
        requested = list(STAGES)
    else:
        requested = [name for name in STAGES if name in args.stages]

    for directory in (SW_DIR, PART_DIR, ASSY_DIR, ASSY_COMPONENT_DIR, DRAW_DIR, PDF_DIR):
        directory.mkdir(parents=True, exist_ok=True)

    report = {'started': time.strftime('%Y-%m-%d %H:%M:%S'), 'stages': requested}
    app = connect(visible=not args.invisible)
    wait_for_idle(app)
    original_preferences = None
    try:
        if any(name in ('parts', 'assembly') for name in requested):
            original_preferences = apply_import_preferences(app, report)
        for name in requested:
            fn = STAGES[name]
            print(f'--- stage {name} ---', flush=True)
            fn(app, report)
            report[f'{name}_finished'] = time.strftime('%H:%M:%S')
    finally:
        if original_preferences:
            restore_import_preferences(app, original_preferences)
            report['import_preferences_after'] = {
                name: get_toggle(app, index) for name, index in IMPORT_PREFERENCES.items()}
        report['finished'] = time.strftime('%Y-%m-%d %H:%M:%S')
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                               encoding='utf-8')
        print(json.dumps(report, ensure_ascii=False, indent=2)[:4000], flush=True)
        if args.quit:
            try:
                app.ExitApp()
            except Exception:
                pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
