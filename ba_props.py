import bpy
import os
from bpy.types import Operator, PropertyGroup
from bpy.props import CollectionProperty, StringProperty

from .ba_utils import add_alpha_node, add_light_color_node, add_lit_alpha_node, clear_nodes, configure_alpha_material, ensure_node_group, ensure_output, link_alpha_to_output, new_tex, safe_link, set_input_default

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
    light_color = add_light_color_node(
        nt,
        weapon_node.outputs.get("Result"),
        base_node.outputs.get("Color"),
        (60, 100)
    )

    metallic_node.location = (320, 100)

    # --- Output ---
    output_node = ensure_output(mat)

    # --- Links ---
    safe_link(nt, base_node.outputs.get("Color"), weapon_node.inputs.get("Base_Color"))
    safe_link(nt, base_node.outputs.get("Color"), metallic_node.inputs.get("Base_Color"))

    if mask_node:
        safe_link(nt, mask_node.outputs.get("Color"), weapon_node.inputs.get("Mask"))
        safe_link(nt, mask_node.outputs.get("Color"), metallic_node.inputs.get("Mask"))

    safe_link(nt, light_color.outputs.get("Color"), metallic_node.inputs.get("Color"))
    safe_link(nt, metallic_node.outputs.get("Result"), output_node.inputs.get("Surface"))



def setup_alpha_material(mat, images):
    setup_prop_alpha_material(mat, images)


def setup_prop_alpha_material(mat, images):
    if not mat.use_nodes:
        mat.use_nodes = True

    configure_alpha_material(mat)

    old_tex = find_image_node(mat)
    had_texture = old_tex is not None
    old_image = old_tex.image if old_tex else None

    clear_nodes(mat)
    nt = mat.node_tree

    out = ensure_output(mat)

    base_img, mask_img = find_base_and_mask(images)

    if base_img is None and had_texture:
        base_img = old_image

    base_node = None
    mask_node = None

    if base_img:
        base_node = new_tex(nt, base_img, non_color=False, loc=(-620, 0))

    if mask_img:
        mask_node = new_tex(nt, mask_img, non_color=True, loc=(-620, -280))

    weapon_node = nt.nodes.new("ShaderNodeGroup")
    weapon_group = ensure_node_group("ba_weapon_shader")
    if not weapon_group:
        print(f"[BA] Node group 'ba_weapon_shader' not found for {mat.name}")
        return

    weapon_node.node_tree = weapon_group
    weapon_node.location = (-280, 0)

    if base_node:
        safe_link(nt, base_node.outputs.get("Color"), weapon_node.inputs.get("Base_Color"))
        if mask_node:
            safe_link(nt, mask_node.outputs.get("Color"), weapon_node.inputs.get("Mask"))

        _, alpha_node = add_lit_alpha_node(
            nt,
            weapon_node.outputs.get("Result"),
            base_node.outputs.get("Color"),
            base_node.outputs.get("Alpha"),
            light_loc=(-90, 0),
            alpha_loc=(90, 0),
        )
    else:
        _, alpha_node = add_lit_alpha_node(
            nt,
            weapon_node.outputs.get("Result"),
            None,
            None,
            light_loc=(-90, 0),
            alpha_loc=(90, 0),
            alpha_default=0.3733333349227905,
        )
        set_input_default(alpha_node, "Fresnel", 1)
        set_input_default(alpha_node, "Spec", 1)

    if not alpha_node.node_tree:
        print(f"[BA] Node group 'ba_alpha' not found for {mat.name}")
        return

    link_alpha_to_output(nt, alpha_node, out)
