import bpy

from .ba_textures import MaterialSetupError, find_prop_images
from .ba_utils import require_node_groups

from .ba_utils import add_alpha_node, add_light_color_node, add_lit_alpha_node, clear_nodes, configure_alpha_material, ensure_node_group, ensure_output, link_alpha_to_output, material_name_key, new_base_color_tex, new_tex, safe_link, set_input_default

# ---------------- utils ----------------

def is_alpha_material(mat):
    return material_name_key(mat).lower().endswith("_alpha")


def is_car_alpha_material(mat):
    return material_name_key(mat).lower().endswith("_car_alpha")

def find_image_node(mat):
    if not mat.use_nodes:
        return None
    nodes = [node for node in mat.node_tree.nodes if node.type == 'TEX_IMAGE' and node.image]
    base, _ = find_prop_images([node.image for node in nodes], mat)
    return next((node for node in nodes if node.image == base), None)

def find_base_and_mask(images, mat):
    return find_prop_images(images, mat)



def setup_prop_material(mat, images):
    base_img, mask_img = find_base_and_mask(images, mat)

    if base_img is None:
        print(f"[BA] Missing base texture for {mat.name}")
        raise MaterialSetupError(f"{mat.name}: base color texture missing")

    require_node_groups({
        "ba_weapon_shader": (("Base_Color", "Mask"), ("Result",)),
        "ba_metallic_shader": (("Color", "Base_Color", "Mask"), ("Result",)),
        "ba_light_color": (("Color", "basecolor"), ("Color",)),
    })

    if not mat.use_nodes:
        mat.use_nodes = True
    clear_nodes(mat)
    nt = mat.node_tree

    # ---  Base  ---
    base_node = new_base_color_tex(nt, base_img, loc=(-600, 100))

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


def setup_car_alpha_material(mat, images):
    setup_prop_alpha_material(mat, images, use_textures=False)


def setup_prop_alpha_material(mat, images, use_textures=True):
    base_img, mask_img = find_base_and_mask(images, mat) if use_textures else (None, None)

    if base_img is None and use_textures:
        old_tex = find_image_node(mat)
        if old_tex:
            base_img = old_tex.image

    require_node_groups({
        "ba_weapon_shader": (("Base_Color", "Mask"), ("Result",)),
        "ba_light_color": (("Color", "basecolor"), ("Color",)),
        "ba_alpha": (("color", "alpha"), ("Shader",)),
    })
    if not mat.use_nodes:
        mat.use_nodes = True
    configure_alpha_material(mat)
    clear_nodes(mat)
    nt = mat.node_tree
    out = ensure_output(mat)

    base_node = None
    mask_node = None

    if base_img:
        base_node = new_base_color_tex(nt, base_img, loc=(-620, 0))

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
        set_input_default(alpha_node, "fresnelcolor_factor", 0.35)
        set_input_default(alpha_node, "Spec", 1)

    if not alpha_node.node_tree:
        print(f"[BA] Node group 'ba_alpha' not found for {mat.name}")
        return

    link_alpha_to_output(nt, alpha_node, out)
