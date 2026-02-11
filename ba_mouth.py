# ba_mouth.py
import bpy
import os


def setup_mouth(context):
    """
    Append 'mouth' collection from shaders/ba_node_groups.blend
    Keep armature, material and all drivers intact
    """


    addon_dir = os.path.dirname(__file__)

    # shaders/ba_node_groups.blend
    blend_path = os.path.join(addon_dir, "shaders", "ba_node_groups.blend")

    if not os.path.exists(blend_path):
        print("[BA Mouth] Blend file not found:", blend_path)
        return

    collection_name = "mouth"


    if collection_name in bpy.data.collections:
        mouth_col = bpy.data.collections.get(collection_name)
    else:
        with bpy.data.libraries.load(blend_path, link=False) as (data_from, data_to):
            if collection_name not in data_from.collections:
                print("[BA Mouth] Collection 'mouth' not found in blend")
                return

            data_to.collections = [collection_name]

        mouth_col = bpy.data.collections.get(collection_name)

    if not mouth_col:
        print("[BA Mouth] Failed to load mouth collection")
        return


    scene = context.scene
    if mouth_col.name not in scene.collection.children:
        scene.collection.children.link(mouth_col)

    print("[BA Mouth] Mouth collection appended successfully")
