import os

import bpy


NODE_GROUP_BLEND = "ba_node_groups.blend"


def addon_dir():
    return os.path.dirname(__file__)


def nodegroup_blend_path(log_prefix="[BA]"):
    path = os.path.join(addon_dir(), "shaders", NODE_GROUP_BLEND)

    if not os.path.exists(path):
        print(f"{log_prefix} ERROR: {NODE_GROUP_BLEND} not found:")
        print("   ", path)

    return path


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


def new_tex(nt, img, non_color=False, loc=(0, 0)):
    if img is None:
        return None

    node = nt.nodes.new("ShaderNodeTexImage")
    node.image = img

    if node.image:
        node.image.alpha_mode = 'CHANNEL_PACKED'
        if non_color:
            node.image.colorspace_settings.name = 'Non-Color'

    node.location = loc
    return node


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
    view_layer = bpy.context.view_layer
    view_layer.objects.active = obj

    if obj.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    bpy.ops.object.geometry_nodes_input_attribute_toggle(
        modifier_name=modifier.name,
        input_name=socket_identifier
    )
