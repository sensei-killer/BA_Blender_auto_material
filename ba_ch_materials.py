import bpy
import os
from bpy.props import StringProperty, CollectionProperty
from bpy.types import Operator, PropertyGroup

from . import ba_shader_controls
from . import ba_outline
from .ba_utils import add_light_color_node, add_lit_alpha_node, clear_nodes, configure_alpha_material, ensure_node_group, ensure_output, link_alpha_to_output, new_tex, refresh_view_layer, safe_link

# -------- utils--------
def build_import_image_map(images):

    image_map = {}

    for img in images:
        if not img.filepath:
            continue

        name = os.path.splitext(
            os.path.basename(bpy.path.abspath(img.filepath))
        )[0]

        image_map[name] = img

    return image_map

def find_image(images, keyword):
    for img in images:
        if not img.filepath:
            continue

        name = os.path.splitext(
            os.path.basename(bpy.path.abspath(img.filepath))
        )[0]

        if name.lower().endswith(keyword.lower()):
            return img
    return None

def detect_material_base_type(mat):
    if not mat or not mat.use_nodes or not mat.node_tree:
        return None

    for node in mat.node_tree.nodes:
        if node.type != 'TEX_IMAGE':
            continue

        img = node.image
        if not img or not img.filepath:
            continue

        name = os.path.splitext(
            os.path.basename(bpy.path.abspath(img.filepath))
        )[0].lower()

        if name.endswith("_body"):
            return "BODY"
        if name.endswith("_face"):
            return "FACE"

    return None

# -------- setup functions --------
def setup_emission(mat, image, strength=1.0):
    if image is None:
        print(f"[BA] Emission image missing for {mat.name}")
        return

    if not mat.use_nodes:
        mat.use_nodes = True

    clear_nodes(mat)
    nt = mat.node_tree

    tex = new_tex(nt, image, False, (-400, 0))

    emission = nt.nodes.new("ShaderNodeEmission")
    emission.location = (-150, 0)
    emission.inputs['Strength'].default_value = strength

    out = ensure_output(mat)

    safe_link(nt, tex.outputs.get('Color'), emission.inputs.get('Color'))
    safe_link(nt, emission.outputs.get('Emission'), out.inputs.get('Surface'))

def setup_eyemouth(mat, images):

    if not mat.use_nodes:
        mat.use_nodes = True

    tex = find_image(images, "EyeMouth")
    if tex is None:
        print(f"[BA] EyeMouth texture missing for {mat.name}")
        return

    clear_nodes(mat)
    nt = mat.node_tree

    tex_node = new_tex(nt, tex, False, (-400, 0))

    no_shadow_node = nt.nodes.new("ShaderNodeGroup")
    no_shadow_node.node_tree = ensure_node_group("ba_no_shadow")
    no_shadow_node.location = (80, 0)

    light_color = add_light_color_node(
        nt,
        tex_node.outputs.get('Color'),
        tex_node.outputs.get('Color'),
        (-180, 0)
    )

    safe_link(nt, light_color.outputs.get('Color'), no_shadow_node.inputs[0])

    out_node = ensure_output(mat)
    safe_link(nt, no_shadow_node.outputs[0], out_node.inputs['Surface'])

    print(f"[BA] EyeMouth setup with ba_no_shadow: {mat.name}")



def setup_body(mat, images):
    clear_nodes(mat)
    nt = mat.node_tree

    tex_body = find_image(images, "Body")
    tex_mask = find_image(images, "Body_Mask")

    if not tex_body:
        print(f"[BA] Body texture missing: {mat.name}")
        return

    body = new_tex(nt, tex_body, False, (-600, 100))
    mask = new_tex(nt, tex_mask, True, (-600, -100)) if tex_mask else None

    shader = nt.nodes.new("ShaderNodeGroup")
    shader.node_tree = ensure_node_group("ba_body_shader")
    shader.location = (-200, 0)

    out = ensure_output(mat)

    safe_link(nt, body.outputs.get('Color'), shader.inputs[0])

    if mask:
        safe_link(nt, mask.outputs.get('Color'), shader.inputs[1])
        safe_link(nt, mask.outputs.get('Alpha'), shader.inputs[2])

    light_color = add_light_color_node(
        nt,
        shader.outputs.get('Result', shader.outputs[0]),
        body.outputs.get('Color'),
        (40, 0)
    )

    safe_link(nt, light_color.outputs.get('Color'), out.inputs['Surface'])


def setup_face(mat, images):
    clear_nodes(mat)
    nt = mat.node_tree

    tex_face = find_image(images, "Face")
    tex_mask = find_image(images, "Face_Mask")

    if not tex_face:
        print(f"[BA] Face texture missing: {mat.name}")
        return

    face = new_tex(nt, tex_face, False, (-600, 100))
    mask = new_tex(nt, tex_mask, True, (-600, -100)) if tex_mask else None

    shader = nt.nodes.new("ShaderNodeGroup")
    shader.node_tree = ensure_node_group("ba_face_shader")
    shader.location = (-200, 0)

    out = ensure_output(mat)

    safe_link(nt, face.outputs.get('Color'), shader.inputs[0])

    if mask:
        safe_link(nt, mask.outputs.get('Color'), shader.inputs[1])

    light_color = add_light_color_node(
        nt,
        shader.outputs.get('Result', shader.outputs[0]),
        face.outputs.get('Color'),
        (40, 0)
    )

    safe_link(nt, light_color.outputs.get('Color'), out.inputs['Surface'])


def setup_hair(mat, images):
    clear_nodes(mat)
    nt = mat.node_tree

    tex_hair = find_image(images, "Hair")
    tex_mask = find_image(images, "Hair_Mask")
    tex_spec = find_image(images, "Hair_Spec")

    if not tex_hair:
        print(f"[BA] Hair texture missing: {mat.name}")
        return

    hair = new_tex(nt, tex_hair, False, (-600, 200))
    mask = new_tex(nt, tex_mask, True, (-600, 0)) if tex_mask else None
    spec = new_tex(nt, tex_spec, True, (-600, -200)) if tex_spec else None

    shader = nt.nodes.new("ShaderNodeGroup")
    shader.node_tree = ensure_node_group("ba_hair_shader")
    shader.location = (-200, 0)

    out = ensure_output(mat)

    safe_link(nt, hair.outputs.get('Color'), shader.inputs[0])

    if mask:
        safe_link(nt, mask.outputs.get('Color'), shader.inputs[1])

    if spec:
        safe_link(nt, spec.outputs.get('Color'), shader.inputs[2])
        safe_link(nt, spec.outputs.get('Alpha'), shader.inputs[3])

    light_color = add_light_color_node(
        nt,
        shader.outputs.get('Result', shader.outputs[0]),
        hair.outputs.get('Color'),
        (40, 0)
    )

    safe_link(nt, light_color.outputs.get('Color'), out.inputs['Surface'])

def setup_eyebrow(mat, images):
    if not mat.use_nodes:
        mat.use_nodes = True

    base_type = detect_material_base_type(mat)

    if base_type is None:
        print(f"[BA] no eyebrow texture: {mat.name}")

    if base_type == "BODY":
        tex = find_image(images, "Body")
    elif base_type == "FACE":
        tex = find_image(images, "Face")
    else:
        tex = None

    if tex is None:
        clear_nodes(mat)
        nt = mat.node_tree

        out_node = ensure_output(mat)

        no_shadow_node = nt.nodes.new("ShaderNodeGroup")
        no_shadow_node.node_tree = ensure_node_group("ba_no_shadow")
        no_shadow_node.location = (-150, 0)

        safe_link(
            nt,
            no_shadow_node.outputs.get('Surface', no_shadow_node.outputs[0]),
            out_node.inputs['Surface']
        )

        eyebrow_node_group = nt.nodes.new("ShaderNodeGroup")
        eyebrow_node_group.node_tree = ensure_node_group("eyebrow_in_front")
        eyebrow_node_group.location = (0, -200)

        safe_link(
            nt,
            eyebrow_node_group.outputs.get('Displacement'),
            out_node.inputs.get('Displacement')
        )

        mat.displacement_method = 'BOTH'
        return

    clear_nodes(mat)
    nt = mat.node_tree

    tex_node = new_tex(nt, tex, False, (-400, 0))

    # ba_no_shadow
    no_shadow_node = nt.nodes.new("ShaderNodeGroup")
    no_shadow_node.node_tree = ensure_node_group("ba_no_shadow")
    no_shadow_node.location = (80, 0)

    light_color = add_light_color_node(
        nt,
        tex_node.outputs.get('Color'),
        tex_node.outputs.get('Color'),
        (-180, 0)
    )

    safe_link(nt, light_color.outputs.get('Color'), no_shadow_node.inputs[0])

    out_node = ensure_output(mat)
    safe_link(nt, no_shadow_node.outputs[0], out_node.inputs['Surface'])

    out_node = ensure_output(mat)

    eyebrow_node_group = nt.nodes.new("ShaderNodeGroup")
    eyebrow_node_group.node_tree = ensure_node_group("eyebrow_in_front")
    eyebrow_node_group.location = (0, -200)

    safe_link(nt, eyebrow_node_group.outputs.get('Displacement'), out_node.inputs.get('Displacement'))

    mat.displacement_method = 'BOTH'

def setup_body_alpha(mat, images):
    clear_nodes(mat)
    nt = mat.node_tree

    tex_body = find_image(images, "Body")
    tex_mask = find_image(images, "Body_Mask")

    configure_alpha_material(mat)

    if not tex_body:
        print(f"[BA] Body texture missing: {mat.name}")
        return

    body = new_tex(nt, tex_body, False, (-800, 100))
    mask = new_tex(nt, tex_mask, True, (-800, -100)) if tex_mask else None

    body_shader = nt.nodes.new("ShaderNodeGroup")
    body_shader.node_tree = ensure_node_group("ba_body_shader")
    body_shader.location = (-400, 0)

    out = ensure_output(mat)

    safe_link(nt, body.outputs.get('Color'), body_shader.inputs[0])

    if mask:
        safe_link(nt, mask.outputs.get('Color'), body_shader.inputs[1])
        safe_link(nt, mask.outputs.get('Alpha'), body_shader.inputs[2])

    _, alpha_shader = add_lit_alpha_node(
        nt,
        body_shader.outputs.get('Result', body_shader.outputs[0]),
        body.outputs.get('Color'),
        body.outputs.get('Alpha'),
        light_loc=(-180, 0),
        alpha_loc=(80, 0),
    )

    link_alpha_to_output(nt, alpha_shader, out)


def setup_hair_alpha(mat, images):
    clear_nodes(mat)
    nt = mat.node_tree

    tex_hair = find_image(images, "Hair")
    tex_mask = find_image(images, "Hair_Mask")
    tex_spec = find_image(images, "Hair_Spec")

    configure_alpha_material(mat)

    if not tex_hair:
        print(f"[BA] Hair texture missing: {mat.name}")
        return

    hair = new_tex(nt, tex_hair, False, (-800, 200))
    mask = new_tex(nt, tex_mask, True, (-800, 0)) if tex_mask else None
    spec = new_tex(nt, tex_spec, True, (-800, -200)) if tex_spec else None

    hair_shader = nt.nodes.new("ShaderNodeGroup")
    hair_shader.node_tree = ensure_node_group("ba_hair_shader")
    hair_shader.location = (-400, 0)

    out = ensure_output(mat)

    safe_link(nt, hair.outputs.get('Color'), hair_shader.inputs[0])

    if mask:
        safe_link(nt, mask.outputs.get('Color'), hair_shader.inputs[1])

    if spec:
        safe_link(nt, spec.outputs.get('Color'), hair_shader.inputs[2])
        safe_link(nt, spec.outputs.get('Alpha'), hair_shader.inputs[3])

    _, alpha_shader = add_lit_alpha_node(
        nt,
        hair_shader.outputs.get('Result', hair_shader.outputs[0]),
        hair.outputs.get('Color'),
        hair.outputs.get('Alpha'),
        light_loc=(-180, 0),
        alpha_loc=(80, 0),
    )

    link_alpha_to_output(nt, alpha_shader, out)


def setup_frill_alpha(mat, images):
    setup_body_alpha(mat, images)


CHARACTER_MATERIAL_HANDLERS = (
    ("_Body_Arms", setup_body),
    ("_Body", setup_body),
    ("_Hair_Alpha", setup_hair_alpha),
    ("_Frill", setup_frill_alpha),
    ("_Alpha", setup_body_alpha),
    ("_Face", setup_face),
    ("_Hair", setup_hair),
    ("_EyeMouth", setup_eyemouth),
    ("_Eyebrow2", setup_eyebrow),
    ("_Eyebrow", setup_eyebrow),
)


def setup_character_material(mat, images):
    for suffix, handler in CHARACTER_MATERIAL_HANDLERS:
        if mat.name.endswith(suffix):
            handler(mat, images)
            return True

    return False


# -------- Operator --------

class BA_OT_setup_materials(Operator):
    bl_idname = "ba.setup_materials_ch"
    bl_label = "Setup Character Materials"

    files: CollectionProperty(type=PropertyGroup)
    directory: StringProperty(subtype='DIR_PATH')

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        images = []
        for f in self.files:
            path = os.path.join(self.directory, f.name)
            img = bpy.data.images.load(path, check_existing=True)
            images.append(img)

        mats = set()
        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue
            for slot in obj.material_slots:
                if slot.material and slot.material.use_nodes:
                    mats.add(slot.material)

        for mat in mats:
            setup_character_material(mat, images)

        ba_shader_controls.ensure_hair_spec_control(context)
        ba_shader_controls.ensure_face_light_dot_control(context)

        empty = bpy.data.objects.get("face_light_dot")
        ba_shader_controls.add_face_rotation_drivers(empty, context)

        empty = bpy.data.objects.get("hair_spec_normal")
        ba_shader_controls.add_hair_rotation_drivers(empty, context)

        ba_outline.add_ba_outline(context)
        refresh_view_layer(context)

        return {'FINISHED'}
