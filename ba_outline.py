import bpy
import os


NODE_GROUP_BLEND = "ba_node_groups.blend"
GEO_NODE_NAME = "ba_outline"

OUTLINE_MATERIALS = {
    "HairOutline": "hair_outline",
    "FaceOutline": "face_outline",
    "BodyOutline": "body_outline",
}


def _addon_dir():
    return os.path.dirname(__file__)


def _nodegroup_blend_path():
    path = os.path.join(
        os.path.dirname(__file__),
        "shaders",
        "ba_node_groups.blend"
    )

    if not os.path.exists(path):
        print("[BA Outline] ERROR: ba_node_groups.blend not found:")
        print("   ", path)

    return path



# ------------------------------------------------------------
# Import helpers
# ------------------------------------------------------------
def remove_existing_outline_modifier(obj):
    for mod in list(obj.modifiers):
        if (
            mod.type == 'NODES'
            and mod.node_group
            and mod.node_group.name == GEO_NODE_NAME
        ):
            obj.modifiers.remove(mod)



def import_geometry_node_group(group_name):
    if group_name in bpy.data.node_groups:
        return bpy.data.node_groups[group_name]

    blend_path = _nodegroup_blend_path()
    with bpy.data.libraries.load(blend_path, link=False) as (data_from, data_to):
        if group_name not in data_from.node_groups:
            return None
        data_to.node_groups = [group_name]

    return bpy.data.node_groups.get(group_name)


def import_material(mat_name):
    if mat_name in bpy.data.materials:
        return bpy.data.materials[mat_name]

    blend_path = _nodegroup_blend_path()
    with bpy.data.libraries.load(blend_path, link=False) as (data_from, data_to):
        if mat_name not in data_from.materials:
            return None
        data_to.materials = [mat_name]

    return bpy.data.materials.get(mat_name)


# ------------------------------------------------------------
# Vertex group creation
# ------------------------------------------------------------

def build_outline_vertex_group(obj):
    if obj.type != 'MESH':
        return None

    vg = obj.vertex_groups.get("outline")
    if vg is None:
        vg = obj.vertex_groups.new(name="outline")

    mesh = obj.data

    vg.remove(range(len(mesh.vertices)))

    for poly in mesh.polygons:
        mat = obj.material_slots[poly.material_index].material
        if not mat:
            continue

        name = mat.name
        if (
            name.endswith("_Hair")
            or name.endswith("_Face")
            or name.endswith("_Body")
        ):
            vg.add(poly.vertices, 1.0, 'ADD')

    return vg


# ------------------------------------------------------------
# Geometry Nodes setup
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



def setup_outline_geometry_nodes(obj):
    geo_group = import_geometry_node_group(GEO_NODE_NAME)
    if not geo_group:
        print("[BA Outline] Node group not found")
        return False

    outline_mats = {}
    for key, mat_name in OUTLINE_MATERIALS.items():
        mat = import_material(mat_name)
        if not mat:
            return False
        outline_mats[key] = mat
        if mat.name not in obj.data.materials:
            obj.data.materials.append(mat)

    model_mats = {}
    for slot in obj.material_slots:
        mat = slot.material
        if not mat:
            continue
        if mat.name.endswith("_Hair"):
            model_mats["HairMaterial"] = mat
        elif mat.name.endswith("_Face"):
            model_mats["FaceMaterial"] = mat
        elif mat.name.endswith("_Body"):
            model_mats["BodyMaterial"] = mat

    vg = build_outline_vertex_group(obj)
    
    # --- Remove existing outline GN ---
    remove_existing_outline_modifier(obj)


    # --- GN Modifier ---
    mod = obj.modifiers.new("BA_Outline", 'NODES')
    mod.node_group = geo_group

    values = {
        "Group": vg.name if vg else "",
        **model_mats,
        "HairOutline": outline_mats["HairOutline"],
        "FaceOutline": outline_mats["FaceOutline"],
        "BodyOutline": outline_mats["BodyOutline"],
    }

    for item in geo_group.interface.items_tree:
        if item.item_type != 'SOCKET':
            continue
        if item.in_out != 'INPUT':
            continue

        name = item.name
        ident = item.identifier

        if name == "Group" and vg:
            ensure_socket_is_attribute(obj, mod, ident)
            mod[f"{ident}_attribute_name"] = vg.name
            continue

        if name in values and isinstance(values[name], bpy.types.ID):
            mod[ident] = values[name]



    return True



# ------------------------------------------------------------
# Public entry
# ------------------------------------------------------------

def add_ba_outline(context):
    objs = context.selected_objects
    if not objs:
        return {'CANCELLED'}

    for obj in objs:
        if obj.type == 'MESH':
            setup_outline_geometry_nodes(obj)

    return {'FINISHED'}
