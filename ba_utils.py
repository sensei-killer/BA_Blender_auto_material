import os
import re

import bpy

from .ba_compat import configure_alpha_material, set_image_color_space, set_modifier_input
from .ba_textures import MaterialSetupError


NODE_GROUP_BLEND = "ba_node_groups.blend"
BLENDER_DUPLICATE_SUFFIX_RE = re.compile(r"\.\d{3,}$")
CLOSEST_BASE_COLOR_MATERIAL_PREFIXES = {
    "CH0333",
}


def addon_dir():
    return os.path.dirname(__file__)


def nodegroup_blend_path(log_prefix="[BA]"):
    path = os.path.join(addon_dir(), "shaders", NODE_GROUP_BLEND)

    if not os.path.exists(path):
        print(f"{log_prefix} ERROR: {NODE_GROUP_BLEND} not found:")
        print("   ", path)

    return path


def strip_blender_duplicate_suffix(name):
    return BLENDER_DUPLICATE_SUFFIX_RE.sub("", name or "")


def material_name_key(mat_or_name):
    name = getattr(mat_or_name, "name", mat_or_name)
    return strip_blender_duplicate_suffix(name)


def should_use_closest_base_color(mat_or_name=None):
    name = material_name_key(mat_or_name)
    if not name:
        return False

    return any(
        name.startswith(prefix)
        for prefix in CLOSEST_BASE_COLOR_MATERIAL_PREFIXES
    )


def import_node_group(group_name, log_prefix="[BA]", report_missing=True):
    if group_name in bpy.data.node_groups:
        return bpy.data.node_groups[group_name]

    blend_path = nodegroup_blend_path(log_prefix)
    with bpy.data.libraries.load(blend_path, link=False) as (data_from, data_to):
        if group_name in data_from.node_groups:
            data_to.node_groups = [group_name]
        else:
            if report_missing:
                print(f"{log_prefix} Node group not found: {group_name}")
            return None

    return bpy.data.node_groups.get(group_name)


def ensure_node_group(group_name, log_prefix="[BA]"):
    return import_node_group(group_name, log_prefix)


def import_material(mat_name, log_prefix="[BA]"):
    if mat_name in bpy.data.materials:
        return bpy.data.materials[mat_name]

    blend_path = nodegroup_blend_path(log_prefix)
    with bpy.data.libraries.load(blend_path, link=False) as (data_from, data_to):
        if mat_name not in data_from.materials:
            print(f"{log_prefix} Material not found: {mat_name}")
            return None
        data_to.materials = [mat_name]

    return bpy.data.materials.get(mat_name)


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


def refresh_view_layer(context):
    context.view_layer.update()


def new_tex(nt, img, non_color=False, loc=(0, 0), interpolation=None):
    if img is None:
        return None

    node = nt.nodes.new("ShaderNodeTexImage")
    node.image = img
    if interpolation is not None:
        node.interpolation = interpolation

    if node.image:
        node.image.alpha_mode = 'CHANNEL_PACKED'
        set_image_color_space(node.image, non_color)

    node.location = loc
    return node


def new_base_color_tex(nt, img, loc=(0, 0), interpolation=None, mat=None):
    if interpolation is None and should_use_closest_base_color(mat):
        interpolation = 'Closest'

    return new_tex(nt, img, non_color=False, loc=loc, interpolation=interpolation)


def safe_link(nt, out_socket, in_socket):
    if out_socket and in_socket:
        nt.links.new(out_socket, in_socket)


def set_input_default(node, input_name, value):
    socket = node.inputs.get(input_name)
    if socket is not None and value is not None:
        socket.default_value = value


def add_light_color_node(nt, shaded_color_socket, base_color_socket, loc=(40, 0)):
    node = nt.nodes.new("ShaderNodeGroup")
    node.node_tree = ensure_node_group("ba_light_color")
    node.location = loc

    safe_link(nt, shaded_color_socket, node.inputs.get("Color"))
    safe_link(nt, base_color_socket, node.inputs.get("basecolor"))

    return node


def add_alpha_node(
    nt,
    color_socket=None,
    alpha_socket=None,
    loc=(-100, 0),
    color_default=None,
    alpha_default=None,
):
    node = nt.nodes.new("ShaderNodeGroup")
    node.node_tree = ensure_node_group("ba_alpha")
    node.location = loc

    if not node.node_tree:
        return node

    safe_link(nt, color_socket, node.inputs.get("color"))
    safe_link(nt, alpha_socket, node.inputs.get("alpha"))

    set_input_default(node, "color", color_default)
    set_input_default(node, "alpha", alpha_default)

    return node


def add_lit_alpha_node(
    nt,
    shaded_color_socket,
    base_color_socket,
    alpha_socket=None,
    light_loc=(40, 0),
    alpha_loc=(300, 0),
    color_default=None,
    alpha_default=None,
):
    light_color = add_light_color_node(
        nt,
        shaded_color_socket,
        base_color_socket,
        light_loc,
    )

    alpha_node = add_alpha_node(
        nt,
        light_color.outputs.get("Color"),
        alpha_socket,
        alpha_loc,
        color_default=color_default,
        alpha_default=alpha_default,
    )

    return light_color, alpha_node


def link_alpha_to_output(nt, alpha_node, output_node):
    safe_link(
        nt,
        alpha_node.outputs.get("Shader", alpha_node.outputs[0]),
        output_node.inputs.get("Surface"),
    )


def remove_existing_nodes_modifier(obj, node_group_name):
    for mod in list(obj.modifiers):
        if (
            mod.type == 'NODES'
            and mod.node_group
            and mod.node_group.name == node_group_name
        ):
            obj.modifiers.remove(mod)


def ensure_socket_is_attribute(obj, modifier, socket_identifier):
    set_modifier_input(modifier, socket_identifier, attribute="outline")


def require_node_groups(specifications):
    groups = {}
    for name, (inputs, outputs) in specifications.items():
        try:
            group = ensure_node_group(name)
        except (OSError, RuntimeError) as exc:
            raise MaterialSetupError(f"Cannot load required node group {name}: {exc}") from exc
        if group is None:
            raise MaterialSetupError(f"Required node group missing: {name}")
        if group.bl_idname != 'ShaderNodeTree':
            raise MaterialSetupError(f"{name}: expected a shader node group")
        sockets = {(s.in_out, s.name) for s in group.interface.items_tree if s.item_type == 'SOCKET'}
        for direction, required in (("INPUT", inputs), ("OUTPUT", outputs)):
            for socket in required:
                if (direction, socket) not in sockets:
                    raise MaterialSetupError(f"{name}: required {direction.lower()} '{socket}' missing")
        groups[name] = group
    return groups
