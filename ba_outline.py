import bpy

from .ba_utils import (
    ensure_socket_is_attribute,
    import_material,
    import_node_group,
    remove_existing_nodes_modifier,
)

GEO_NODE_NAME = "ba_outline"

OUTLINE_MATERIALS = {
    "HairOutline": "hair_outline",
    "FaceOutline": "face_outline",
    "BodyOutline": "body_outline",
}

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
            or name.endswith("_Body_Arms")
        ):
            vg.add(poly.vertices, 1.0, 'ADD')

    return vg


# ------------------------------------------------------------
# Geometry Nodes setup
# ------------------------------------------------------------
def setup_outline_geometry_nodes(obj):
    geo_group = import_node_group(GEO_NODE_NAME, "[BA Outline]", report_missing=False)
    if not geo_group:
        print("[BA Outline] Node group not found")
        return False

    outline_mats = {}
    for key, mat_name in OUTLINE_MATERIALS.items():
        mat = import_material(mat_name, "[BA Outline]")
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
    remove_existing_nodes_modifier(obj, GEO_NODE_NAME)


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

