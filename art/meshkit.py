"""Small procedural-modelling helpers on top of bmesh (Blender 4.2)."""
import math
import bmesh
import bpy
from mathutils import Matrix, Vector


# ------------------------------------------------------------------ materials
def material(name, color, metallic=0.0, roughness=0.5):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    m.diffuse_color = (*color, 1.0)
    return m


# ------------------------------------------------------------------ part
class Part:
    """Accumulates geometry for one object, with per-face materials."""

    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.mats = []

    def _mi(self, mat):
        if mat not in self.mats:
            self.mats.append(mat)
        return self.mats.index(mat)

    def _merge(self, src, mat, smooth=True, flat_axis=None):
        """Append bmesh `src` into this part."""
        mi = self._mi(mat)
        vmap = {}
        for v in src.verts:
            vmap[v] = self.bm.verts.new(v.co)
        for f in src.faces:
            try:
                nf = self.bm.faces.new([vmap[v] for v in f.verts])
            except ValueError:
                continue
            nf.material_index = mi
            nf.smooth = smooth
            if smooth and flat_axis is not None:
                n = f.normal
                if abs(n.dot(flat_axis)) > 0.95:
                    nf.smooth = False
        src.free()

    # -------------------------------------------------------------- primitives
    def tube(self, p0, p1, r0, r1=None, mat=None, seg=20, sx=1.0, sy=1.0, up=None, caps=True):
        """Cylinder/cone from p0 to p1. sx = lateral scale, sy = in-plane scale."""
        p0, p1 = Vector(p0), Vector(p1)
        r1 = r0 if r1 is None else r1
        d = p1 - p0
        L = d.length
        if L < 1e-6:
            return
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=caps, cap_tris=False, segments=seg,
                              radius1=r0, radius2=r1, depth=L)
        bmesh.ops.scale(bm, vec=(sx, sy, 1.0), verts=bm.verts)
        M = frame_from(d, up)
        bmesh.ops.transform(bm, matrix=Matrix.Translation((p0 + p1) / 2) @ M, verts=bm.verts)
        bm.normal_update()
        self._merge(bm, mat, flat_axis=d.normalized())

    def polytube(self, pts, r, mat, seg=12):
        for a, b in zip(pts, pts[1:]):
            self.tube(a, b, r, mat=mat, seg=seg)
        for p in pts[1:-1]:
            self.sphere(p, r, mat, seg=seg, rings=6)

    def sphere(self, c, r, mat, seg=16, rings=10, scale=(1, 1, 1)):
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=r)
        bmesh.ops.scale(bm, vec=scale, verts=bm.verts)
        bmesh.ops.translate(bm, vec=Vector(c), verts=bm.verts)
        self._merge(bm, mat)

    def box(self, c, size, mat, rot=None, smooth=False):
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=size, verts=bm.verts)
        M = Matrix.Translation(Vector(c))
        if rot is not None:
            M = M @ rot
        bmesh.ops.transform(bm, matrix=M, verts=bm.verts)
        self._merge(bm, mat, smooth=smooth)

    def hull(self, points, mat, smooth=True):
        """Convex hull of a point cloud."""
        bm = bmesh.new()
        for p in points:
            bm.verts.new(Vector(p))
        res = bmesh.ops.convex_hull(bm, input=bm.verts)
        # drop interior verts
        for v in [v for v in bm.verts if not v.link_faces]:
            bm.verts.remove(v)
        bm.normal_update()
        self._merge(bm, mat, smooth=smooth)

    def disc(self, c, axis, r_out, r_in, thick, mat, seg=48):
        """Flat ring (washer) around `axis`."""
        c, axis = Vector(c), Vector(axis).normalized()
        bm = bmesh.new()
        M = Matrix.Translation(c) @ frame_from(axis)
        rings = []
        for z in (-thick / 2, thick / 2):
            for r in (r_out, r_in):
                rings.append([bm.verts.new(M @ Vector((r * math.cos(2 * math.pi * i / seg),
                                                          r * math.sin(2 * math.pi * i / seg), z)))
                              for i in range(seg)])
        lo_out, lo_in, hi_out, hi_in = rings
        def quad(a, b, flip=False):
            for i in range(seg):
                j = (i + 1) % seg
                f = [a[i], a[j], b[j], b[i]]
                bm.faces.new(f[::-1] if flip else f)
        if r_in > 0:
            quad(hi_out, hi_in)
            quad(lo_in, lo_out)
            quad(lo_out, hi_out)
            quad(hi_in, lo_in)
        bm.normal_update()
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        self._merge(bm, mat, smooth=False)

    def torus(self, c, axis, R, r, mat, seg=48, rseg=10, sy=1.0):
        c, axis = Vector(c), Vector(axis).normalized()
        M = Matrix.Translation(c) @ frame_from(axis)
        bm = bmesh.new()
        grid = []
        for i in range(seg):
            a = 2 * math.pi * i / seg
            ring = []
            for j in range(rseg):
                b = 2 * math.pi * j / rseg
                rr = R + r * math.cos(b)
                z = r * math.sin(b) * sy
                ring.append(bm.verts.new(M @ Vector((rr * math.cos(a), rr * math.sin(a), z))))
            grid.append(ring)
        for i in range(seg):
            for j in range(rseg):
                i2, j2 = (i + 1) % seg, (j + 1) % rseg
                bm.faces.new([grid[i][j], grid[i2][j], grid[i2][j2], grid[i][j2]])
        bm.normal_update()
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        self._merge(bm, mat)

    def loft(self, sections, mat, smooth=True, cap=True):
        """Skin a list of closed cross-sections (each a list of points, same
        count) into one continuous tube-like mesh."""
        bm = bmesh.new()
        rings = [[bm.verts.new(Vector(p)) for p in sec] for sec in sections]
        n = len(rings[0])
        for r0, r1 in zip(rings, rings[1:]):
            for i in range(n):
                j = (i + 1) % n
                bm.faces.new([r0[i], r0[j], r1[j], r1[i]])
        if cap:
            bm.faces.new(rings[0][::-1])
            bm.faces.new(rings[-1])
        bm.normal_update()
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        self._merge(bm, mat, smooth=smooth)
        if cap and smooth:
            for f in self.bm.faces[-2:] if hasattr(self.bm.faces, "__getitem__") else []:
                f.smooth = False

    def add_mesh(self, me, mats, matrix=None, smooth=True):
        """Append a Blender mesh (e.g. an evaluated modifier result); its
        material slots map through `mats` (list of materials, by slot)."""
        bm = bmesh.new()
        bm.from_mesh(me)
        if matrix is not None:
            bmesh.ops.transform(bm, matrix=matrix, verts=bm.verts)
        vmap = {v: self.bm.verts.new(v.co) for v in bm.verts}
        for f in bm.faces:
            try:
                nf = self.bm.faces.new([vmap[v] for v in f.verts])
            except ValueError:
                continue
            nf.material_index = self._mi(mats[min(f.material_index, len(mats) - 1)])
            nf.smooth = smooth
        bm.free()

    # -------------------------------------------------------------- output
    def build(self, origin=(0, 0, 0), collection=None):
        origin = Vector(origin)
        bmesh.ops.translate(self.bm, vec=-origin, verts=self.bm.verts)
        me = bpy.data.meshes.new(self.name)
        self.bm.to_mesh(me)
        self.bm.free()
        for m in self.mats:
            me.materials.append(m)
        ob = bpy.data.objects.new(self.name, me)
        ob.location = origin
        (collection or bpy.context.scene.collection).objects.link(ob)
        return ob


def frame_from(z_dir, up=None):
    """Rotation matrix (4x4) whose local Z points along z_dir and local X is as
    close as possible to world X (lateral) unless `up` is given."""
    z = Vector(z_dir).normalized()
    ref = Vector(up) if up is not None else Vector((1, 0, 0))
    if abs(z.dot(ref.normalized())) > 0.95:
        ref = Vector((0, 0, 1)) if abs(z.z) < 0.9 else Vector((0, 1, 0))
    x = (ref - z * ref.dot(z)).normalized()
    y = z.cross(x)
    return Matrix((
        (x.x, y.x, z.x, 0),
        (x.y, y.y, z.y, 0),
        (x.z, y.z, z.z, 0),
        (0, 0, 0, 1),
    ))


def parent_keep(child, parent):
    bpy.context.view_layer.update()
    child.parent = parent
    child.matrix_parent_inverse = parent.matrix_world.inverted()


def clear_scene():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.armatures, bpy.data.actions):
        for d in list(coll):
            coll.remove(d)
