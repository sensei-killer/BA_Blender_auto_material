import bpy
import os


NODE_GROUP_BLEND = "ba_node_groups.blend"
GEO_NODE_NAME = "ba_weapeon_ouline"
OUTLINE_MATERIAL_NAME = "weapon_outline"


# ------------------------------------------------------------
# paths
# ------------------------------------------------------------

def _addon_dir():
    return os.path.dirname(__file__)


def _nodegroup_blend_path():
    path = os.path.join(
        os.path.dirname(__file__),
        "shaders",
        NODE_GROUP_BLEND
    )

    if not os.path.exists(path):
        print("[BA Props Outline] ERROR: ba_node_groups.blend not found:")
        print("   ", path)

    return path


# ------------------------------------------------------------
# import helpers
# ------------------------------------------------------------
def remove_existing_outline_modifier(obj):
    for mod in list(obj.modifiers):
        if (
            mod.type == 'NODES'
            and mod.node_group
            and mod.node_group.name == GEO_NODE_NAME
        ):
            obj.modifiers.remove(mod)
            
def find_alpha_material(obj):
    for mat in obj.data.materials:
        if mat and mat.name.lower().endswith("_alpha"):
            return mat
    return None


def import_geometry_node_group(group_name):
    if group_name in bpy.data.node_groups:
        return bpy.data.node_groups[group_name]

    blend_path = _nodegroup_blend_path()
    with bpy.data.libraries.load(blend_path, link=False) as (data_from, data_to):
        if group_name not in data_from.node_groups:
            print(f"[BA Props Outline] Node group not found: {group_name}")
            return None
        data_to.node_groups = [group_name]

    return bpy.data.node_groups.get(group_name)


def import_material(mat_name):
    if mat_name in bpy.data.materials:
        return bpy.data.materials[mat_name]

    blend_path = _nodegroup_blend_path()
    with bpy.data.libraries.load(blend_path, link=False) as (data_from, data_to):
        if mat_name not in data_from.materials:
            print(f"[BA Props Outline] Material not found: {mat_name}")
            return None
        data_to.materials = [mat_name]

    return bpy.data.materials.get(mat_name)


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


# ------------------------------------------------------------
# geometry nodes helpers
# ------------------------------------------------------------

def ensure_socket_is_attribute(obj, modifier, socket_identifier):
    view_layer = bpy.context.view_layer
    view_layer.objects.active = obj

    if obj.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    bpy.ops.object.geometry_nodes_input_attribute_toggle(
        modifier_name=modifier.name,
        input_name=socket_identifier
    )


# ------------------------------------------------------------
# main setup
# ------------------------------------------------------------

def setup_prop_outline_geometry_nodes(obj):
    geo_group = import_geometry_node_group(GEO_NODE_NAME)
    if not geo_group:
        return False

    outline_mat = import_material(OUTLINE_MATERIAL_NAME)
    if not outline_mat:
        return False


    if outline_mat.name not in obj.data.materials:
        obj.data.materials.append(outline_mat)


    vg = build_outline_vertex_group(obj)

    # --- Remove existing outline GN ---
    remove_existing_outline_modifier(obj)


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

        # Group → Attribute
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
