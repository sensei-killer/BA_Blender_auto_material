import bpy

from .ba_utils import (
    ensure_socket_is_attribute,
    import_material,
    import_node_group,
    remove_existing_nodes_modifier,
)

GEO_NODE_NAME = "ba_weapon_outline"
OUTLINE_MATERIAL_NAME = "weapon_outline"


def find_alpha_material(obj):
    for mat in obj.data.materials:
        if mat and mat.name.lower().endswith("_alpha"):
            return mat
    return None


# ------------------------------------------------------------
# vertex group
# ------------------------------------------------------------

def build_outline_vertex_group(obj):
    if obj.type != 'MESH':
        return None

    vg = obj.vertex_groups.get("outline")
    if vg is None:
        vg = obj.vertex_groups.new(name="outline")

    mesh = obj.data


    vg.remove(range(len(mesh.vertices)))


    vg.add(range(len(mesh.vertices)), 1.0, 'ADD')

    return vg


def refresh_modifier_viewport(obj, mod):
    mod.show_viewport = False
    mod.show_viewport = True
    obj.update_tag()


# ------------------------------------------------------------
# geometry nodes helpers
# ------------------------------------------------------------

# ------------------------------------------------------------
# main setup
# ------------------------------------------------------------

def setup_prop_outline_geometry_nodes(obj):
    geo_group = import_node_group(GEO_NODE_NAME, "[BA Props Outline]")
    if not geo_group:
        return False

    outline_mat = import_material(OUTLINE_MATERIAL_NAME, "[BA Props Outline]")
    if not outline_mat:
        return False


    if outline_mat.name not in obj.data.materials:
        obj.data.materials.append(outline_mat)


    vg = build_outline_vertex_group(obj)

    # --- Remove existing outline GN ---
    remove_existing_nodes_modifier(obj, GEO_NODE_NAME)


    # Geometry Nodes Modifier
    mod = obj.modifiers.new("BA_Prop_Outline", 'NODES')
    mod.node_group = geo_group


    for item in geo_group.interface.items_tree:
        if item.item_type != 'SOCKET':
            continue
        if item.in_out != 'INPUT':
            continue

        name = item.name
        ident = item.identifier

        # Group Attribute
        if name == "Group" and vg:
            ensure_socket_is_attribute(obj, mod, ident)
            mod[f"{ident}_attribute_name"] = vg.name
            continue

        # Outline
        if name == "Outline":
            mod[ident] = outline_mat
            continue
            
        # Alpha Material
        if name == "Alpha_Material":
            alpha_mat = find_alpha_material(obj)
            if alpha_mat:
                mod[ident] = alpha_mat
            continue

    refresh_modifier_viewport(obj, mod)
    return True


# ------------------------------------------------------------
# public entry
# ------------------------------------------------------------

def add_ba_props_outline(context):
    objs = context.selected_objects
    if not objs:
        return {'CANCELLED'}

    for obj in objs:
        if obj.type == 'MESH':
            setup_prop_outline_geometry_nodes(obj)

    return {'FINISHED'}
