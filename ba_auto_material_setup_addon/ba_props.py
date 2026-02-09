import bpy
import os
from bpy.types import Operator, PropertyGroup
from bpy.props import CollectionProperty, StringProperty

# ---------------- utils ----------------

def ensure_node_group(group_name):
    if group_name in bpy.data.node_groups:
        return bpy.data.node_groups[group_name]

    addon_dir = os.path.dirname(__file__)
    blend_path = os.path.join(addon_dir, "shaders", "ba_node_groups.blend")

    with bpy.data.libraries.load(blend_path, link=False) as (data_from, data_to):
        if group_name in data_from.node_groups:
            data_to.node_groups = [group_name]
        else:
            print(f"[BA] Node group not found: {group_name}")
            return None

    return bpy.data.node_groups.get(group_name)

def is_alpha_material(mat):
    return mat.name.lower().endswith("_alpha")

def find_image_node(mat):
    if not mat.use_nodes:
        return None

    for n in mat.node_tree.nodes:
        if n.type == 'TEX_IMAGE' and n.image:
            return n
    return None



def ensure_output(mat):
    nt = mat.node_tree
    out = nt.nodes.get("Material Output")
    if not out:
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        out.location = (400, 0)
    return out


def clear_nodes(mat):
    nt = mat.node_tree
    nt.nodes.clear()


def new_tex(nt, img, non_color=False, loc=(0, 0)):
    if img is None:
        return None    
    n = nt.nodes.new("ShaderNodeTexImage")
    n.image = img
    if n.image:
            n.image.alpha_mode = 'CHANNEL_PACKED'
    if non_color:
        n.image.colorspace_settings.name = 'Non-Color'
    n.location = loc
    return n

def find_base_and_mask(images):
    base = None
    mask = None

    for img in images:
        name = os.path.splitext(os.path.basename(img.name))[0].lower()

        if name.endswith("mask"):
            if mask is None:
                mask = img
        else:
            if base is None:
                base = img

    return base, mask



def setup_prop_material(mat, images):
    if not mat.use_nodes:
        mat.use_nodes = True

    base_img, mask_img = find_base_and_mask(images)

    if base_img is None:
        print(f"[BA] Missing base texture for {mat.name}")
        return

    clear_nodes(mat)
    nt = mat.node_tree

    # ---  Base  ---
    base_node = new_tex(nt, base_img, non_color=False, loc=(-600, 100))

    # --- Mask  ---
    mask_node = None
    if mask_img:
        mask_node = new_tex(nt, mask_img, non_color=True, loc=(-600, -100))

    # --- Shader Group ---
    shader_node = nt.nodes.new("ShaderNodeGroup")
    ng = ensure_node_group("ba_weapon_shader")
    if not ng:
        print(f"[BA] Node group 'ba_weapon_shader' not found for {mat.name}")
        return
    shader_node.node_tree = ng
    shader_node.location = (-200, 0)

    # --- Output ---
    output_node = ensure_output(mat)

    # ---  Base ---
    try:
        if "Base_Color" in shader_node.inputs:
            nt.links.new(base_node.outputs['Color'], shader_node.inputs['Base_Color'])
        else:
            nt.links.new(base_node.outputs['Color'], shader_node.inputs[0])
    except Exception as e:
        print(f"[BA] Failed to link base for {mat.name}: {e}")

    # ---  Mask ---
    if mask_node:
        mask_input = shader_node.inputs.get("Mask")
        if mask_input:
            try:
                nt.links.new(mask_node.outputs['Color'], mask_input)
            except Exception as e:
                print(f"[BA] Failed to link mask for {mat.name}: {e}")

    # --- output ---
    try:
        nt.links.new(shader_node.outputs[0], output_node.inputs['Surface'])
    except Exception as e:
        print(f"[BA] Failed to link shader output for {mat.name}: {e}")



def setup_alpha_material(mat, images):
    if not mat.use_nodes:
        mat.use_nodes = True

    mat.surface_render_method = 'BLENDED'


    old_tex = find_image_node(mat)
    had_texture = old_tex is not None
    old_image = old_tex.image if old_tex else None

    clear_nodes(mat)
    nt = mat.node_tree

    out = ensure_output(mat)

    tex_node = None


    if had_texture:

        base_img, _ = find_base_and_mask(images)

        if base_img is None:
            base_img = old_image

        if base_img:
            tex_node = new_tex(
                nt,
                base_img,
                non_color=False,
                loc=(-400, 0)
            )

    # --------------------------------
    # ba_alpha
    # --------------------------------
    alpha_node = nt.nodes.new("ShaderNodeGroup")
    ng = ensure_node_group("ba_alpha")
    if not ng:
        print(f"[BA] Node group 'ba_alpha' not found for {mat.name}")
        return

    alpha_node.node_tree = ng
    alpha_node.location = (-100, 0)


    if tex_node:
        if "Color" in tex_node.outputs and len(alpha_node.inputs) > 0:
            nt.links.new(tex_node.outputs["Color"], alpha_node.inputs[0])

        if "Alpha" in tex_node.outputs and len(alpha_node.inputs) > 1:
            nt.links.new(tex_node.outputs["Alpha"], alpha_node.inputs[1])

    # --------------------------------
    # output
    # --------------------------------
    nt.links.new(alpha_node.outputs[0], out.inputs["Surface"])
