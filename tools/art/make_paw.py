"""호랑이 손(오른손) — 라운지 호랑이 그림체: 주황 털, 검은 줄무늬, 분홍 젤리, 초록 후드 소매.
블렌더 좌표(Z 위, +Y 손가락 방향, -Y 팔 방향). glTF 로 나가면 Y 위, -Z 손가락 방향이 된다.
본: Arm(소매) → Hand → 손가락 4개 × 2마디 + 엄지 2마디. 부품마다 한 본에 단단히 붙인다(경계는 캡슐 겹침으로 가린다).
동작(1프레임 자세): rest, grip, flat, point, pinch.
"""
import bpy, bmesh, math, sys
from mathutils import Vector, Matrix
out = sys.argv[sys.argv.index('--') + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
S = bpy.context.scene

COL = {'fur': (0.96, 0.52, 0.16, 1), 'stripe': (0.12, 0.08, 0.07, 1), 'pad': (0.95, 0.62, 0.62, 1),
       'cream': (1.0, 0.86, 0.68, 1), 'sleeve': (0.20, 0.34, 0.24, 1), 'cuff': (0.15, 0.27, 0.19, 1)}
parts = []   # (obj, bone, colorkey)

def capsule(name, p0, p1, r, color, bone, seg=12, ring=6, sx=1.0, sz=1.0):
    """p0→p1 축의 캡슐(납작하게 sx,sz)."""
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=ring * 2, radius=r)
    a, b = Vector(p0), Vector(p1); L = (b - a).length
    for v in bm.verts:   # 반구를 늘려 캡슐로
        v.co.x *= sx; v.co.y *= sz
        v.co.z += L / 2 if v.co.z > 0 else -L / 2
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); S.collection.objects.link(ob)
    d = (b - a).normalized()
    rot = Vector((0, 0, 1)).rotation_difference(d).to_matrix().to_4x4()
    ob.matrix_world = Matrix.Translation((a + b) / 2) @ rot
    parts.append((ob, bone, color)); return ob

def box(name, c, size, color, bone, bevel=0.35, rot=None):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts: v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    bmesh.ops.bevel(bm, geom=list(bm.verts) + list(bm.edges), offset=min(size) * bevel, segments=4, affect='EDGES')
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); S.collection.objects.link(ob)
    ob.location = c
    if rot: ob.rotation_euler = rot
    parts.append((ob, bone, color)); return ob

def cyl(name, p0, p1, r0, r1, color, bone, seg=20):
    bm = bmesh.new()
    a, b = Vector(p0), Vector(p1); L = (b - a).length
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r0, radius2=r1, depth=L)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); S.collection.objects.link(ob)
    d = (b - a).normalized()
    ob.matrix_world = Matrix.Translation((a + b) / 2) @ Vector((0, 0, 1)).rotation_difference(d).to_matrix().to_4x4()
    parts.append((ob, bone, color)); return ob

# ---- 치수 (m) ----
PW, PL, PT = 0.080, 0.066, 0.032          # 손바닥 폭·길이·두께 (통통한 앞발)
# 소매: 손목(y=0)에서 팔꿈치 쪽(-y)으로
cyl('sleeve', (0, -0.215, 0.030), (0, -0.030, 0.004), 0.040, 0.037, 'sleeve', 'Arm')
cyl('cuff', (0, -0.034, 0.004), (0, -0.004, 0.003), 0.039, 0.039, 'cuff', 'Arm')
# 손등/손바닥
box('palm', (0, 0.030, 0.0), (PW, PL, PT), 'fur', 'Hand', bevel=0.45)
box('palm_pad', (0, 0.030, -PT * 0.46), (PW * 0.52, PL * 0.45, 0.008), 'pad', 'Hand', bevel=0.5)
# 줄무늬(손등 위 얇은 띠)
for i, (x, w, ang) in enumerate([(-0.022, 0.030, 0.35), (0.004, 0.034, 0.05), (0.026, 0.026, -0.3)]):
    box('stripe%d' % i, (x, 0.020 + 0.006 * (i % 2), PT * 0.5 - 0.0005), (0.008, w, 0.004), 'stripe', 'Hand', bevel=0.5, rot=(0, 0, ang))
# 손가락 4개(검지→새끼, +x→-x 가 오른손 손등 기준 바깥쪽): 오른손이면 엄지는 -x 쪽
FR = 0.0125
fx = [0.027, 0.009, -0.009, -0.026]
names = ['Index', 'Middle', 'Ring', 'Pinky']
lens = [0.020, 0.022, 0.021, 0.017]
for x, n, L in zip(fx, names, lens):
    y0 = 0.030 + PL / 2 - 0.006
    capsule(n + '1', (x, y0, 0), (x, y0 + L, 0), FR, 'fur', n + '1', sz=0.85)
    capsule(n + '2', (x, y0 + L, 0), (x, y0 + L + 0.012, -0.002), FR * 0.92, 'fur', n + '2', sz=0.85)
    box(n + '_bean', (x, y0 + L + 0.006, -FR * 0.72), (0.012, 0.011, 0.004), 'pad', n + '2', bevel=0.5)
# 엄지(오른손: -x 쪽, 앞·아래로)
capsule('Thumb1', (-0.040, 0.020, -0.004), (-0.050, 0.038, -0.006), FR, 'fur', 'Thumb1', sz=0.85)
capsule('Thumb2', (-0.050, 0.038, -0.006), (-0.054, 0.050, -0.008), FR * 0.9, 'fur', 'Thumb2', sz=0.85)

# ---- 아마추어 ----
arm = bpy.data.armatures.new('PawRig'); rig = bpy.data.objects.new('TigerPawR', arm)
S.collection.objects.link(rig); bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode='EDIT')
def eb(name, h, t, parent=None):
    b = arm.edit_bones.new(name); b.head = h; b.tail = t
    if parent: b.parent = arm.edit_bones[parent]; b.use_connect = False
    return b
eb('Arm', (0, -0.215, 0.005), (0, -0.002, 0.004))
eb('Hand', (0, 0.0, 0.0), (0, 0.058, 0.0), 'Arm')
for x, n, L in zip(fx, names, lens):
    y0 = 0.030 + PL / 2 - 0.006
    eb(n + '1', (x, y0, 0), (x, y0 + L, 0), 'Hand')
    eb(n + '2', (x, y0 + L, 0), (x, y0 + L + 0.012, -0.002), n + '1')
eb('Thumb1', (-0.040, 0.020, -0.004), (-0.050, 0.038, -0.006), 'Hand')
eb('Thumb2', (-0.050, 0.038, -0.006), (-0.054, 0.050, -0.008), 'Thumb1')
bpy.ops.object.mode_set(mode='OBJECT')

# ---- 부품 → 한 메시, 꼭짓점 색, 정점 그룹 ----
for ob, bone, ck in parts:
    me = ob.data
    ca = me.color_attributes.new('Col', 'BYTE_COLOR', 'CORNER')
    for d in ca.data: d.color_srgb = COL[ck]
    vg = ob.vertex_groups.new(name=bone)
    vg.add(list(range(len(me.vertices))), 1.0, 'REPLACE')
    for p in me.polygons: p.use_smooth = True
bpy.ops.object.select_all(action='DESELECT')
for ob, _, _ in parts: ob.select_set(True)
bpy.context.view_layer.objects.active = parts[0][0]
bpy.ops.object.join()
paw = bpy.context.view_layer.objects.active; paw.name = 'TigerPawMesh'
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
paw.parent = rig
mod = paw.modifiers.new('Armature', 'ARMATURE'); mod.object = rig
mat = bpy.data.materials.new('Paw'); mat.use_nodes = True
# 꼭짓점 색을 기본 색으로 쓰게 연결(glTF 가 COLOR_0 를 내보낸다. three 쪽에서 툰 재질로 바꾼다)
nt = mat.node_tree; bsdf = nt.nodes['Principled BSDF']
vc = nt.nodes.new('ShaderNodeVertexColor'); vc.layer_name = 'Col'
nt.links.new(vc.outputs['Color'], bsdf.inputs['Base Color'])
paw.data.materials.append(mat)

# ---- 자세(동작) ----
R = math.radians
POSES = {
  # 본: (x회전 = 굽힘, z회전)   굽힘은 손바닥 쪽(-x 축 회전)
  'rest':  {'Index1': -15, 'Index2': -20, 'Middle1': -18, 'Middle2': -22, 'Ring1': -20, 'Ring2': -24, 'Pinky1': -22, 'Pinky2': -26, 'Thumb1': -10, 'Thumb2': -10},
  'grip':  {'Index1': -70, 'Index2': -80, 'Middle1': -75, 'Middle2': -85, 'Ring1': -75, 'Ring2': -85, 'Pinky1': -72, 'Pinky2': -80, 'Thumb1': -35, 'Thumb2': -40},
  'flat':  {'Index1': 5, 'Index2': 0, 'Middle1': 5, 'Middle2': 0, 'Ring1': 5, 'Ring2': 0, 'Pinky1': 5, 'Pinky2': 0, 'Thumb1': 10, 'Thumb2': 0},
  'point': {'Index1': 0, 'Index2': -5, 'Middle1': -80, 'Middle2': -85, 'Ring1': -80, 'Ring2': -85, 'Pinky1': -78, 'Pinky2': -82, 'Thumb1': -40, 'Thumb2': -35},
  'pinch': {'Index1': -40, 'Index2': -45, 'Middle1': -35, 'Middle2': -30, 'Ring1': -40, 'Ring2': -40, 'Pinky1': -45, 'Pinky2': -45, 'Thumb1': -30, 'Thumb2': -25},
}
rig.animation_data_create()
for pname, pose in POSES.items():
    act = bpy.data.actions.new(pname); act.use_fake_user = True
    rig.animation_data.action = act
    for pb in rig.pose.bones:
        pb.rotation_mode = 'XYZ'
        pb.rotation_euler = (R(pose.get(pb.name, 0)), 0, 0)
        for f in (1, 2):
            pb.keyframe_insert('rotation_euler', frame=f)
    tr = rig.animation_data.nla_tracks.new(); tr.name = pname
    tr.strips.new(pname, 1, act)
rig.animation_data.action = None
bpy.ops.export_scene.gltf(filepath=out, export_format='GLB', export_animations=True,
                          export_animation_mode='NLA_TRACKS', export_vertex_color='ACTIVE',
                          export_yup=True, export_apply=False)
print('verts', len(paw.data.vertices), 'polys', len(paw.data.polygons))
