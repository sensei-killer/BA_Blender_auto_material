import bpy
import os
from bpy.types import Operator, PropertyGroup
from bpy.props import CollectionProperty, StringProperty

from .ba_utils import clear_nodes, ensure_node_group, ensure_output, new_tex, safe_link

# ---------------- utils ----------------

def is_alpha_material(mat):
    return mat.name.lower().endswith("_alpha")

def find_image_node(mat):
    if not mat.use_nodes:
        return None

    for n in mat.node_tree.nodes:
        if n.type == 'TEX_IMAGE' and n.image:
            return n
    return None

def find_base_and_mask(images):
    base = None
    mask = None

    for img in images:
        if img.filepath:
            name = os.path.splitext(os.path.basename(bpy.path.abspath(img.filepath)))[0].lower()
        else:
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

    # --- Shader Groups ---
    weapon_node = nt.nodes.new("ShaderNodeGroup")
    weapon_group = ensure_node_group("ba_weapon_shader")
    if not weapon_group:
        print(f"[BA] Node group 'ba_weapon_shader' not found for {mat.name}")
        return

    metallic_node = nt.nodes.new("ShaderNodeGroup")
    metallic_group = ensure_node_group("ba_metallic_shader")
    if not metallic_group:
        print(f"[BA] Node group 'ba_metallic_shader' not found for {mat.name}")
        return

    weapon_node.node_tree = weapon_group
    weapon_node.location = (-200, 100)

    metallic_node.node_tree = metallic_group
    metallic_node.location = (80, 100)

    # --- Output ---
    output_node = ensure_output(mat)

    # --- Links ---
    safe_link(nt, base_node.outputs.get("Color"), weapon_node.inputs.get("Base_Color"))
    safe_link(nt, base_node.outputs.get("Color"), metallic_node.inputs.get("Base_Color"))

    if mask_node:
        safe_link(nt, mask_node.outputs.get("Color"), weapon_node.inputs.get("Mask"))
        safe_link(nt, mask_node.outputs.get("Color"), metallic_node.inputs.get("Mask"))

    safe_link(nt, weapon_node.outputs.get("Result"), metallic_node.inputs.get("Color"))
    safe_link(nt, metallic_node.outputs.get("Result"), output_node.inputs.get("Surface"))



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
