# ba_halo.py
import bpy
import os
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty

def ensure_node_group(group_name):
    if group_name in bpy.data.node_groups:
        return bpy.data.node_groups[group_name]

    addon_dir = os.path.dirname(__file__)
    blend_path = os.path.join(addon_dir, "shaders", "ba_node_groups.blend")

    with bpy.data.libraries.load(blend_path, link=False) as (data_from, data_to):
        if group_name in data_from.node_groups:
            data_to.node_groups = [group_name]
        else:
            print(f"[BA] Node group not found: {group_name}")
            return None

    return bpy.data.node_groups.get(group_name)

class BA_OT_halo_pick_image(bpy.types.Operator, ImportHelper):
    """Pick image and apply emission material"""
    bl_idname = "ba.halo_pick_image"
    bl_label = "Pick Halo Image"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".png;.jpg;.jpeg;.tga;.exr"
    filter_glob: StringProperty(
        default="*.png;*.jpg;*.jpeg;*.tga;*.exr",
        options={'HIDDEN'}
    )

    def execute(self, context):
        obj = context.active_object

        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "Please select a mesh object")
            return {'CANCELLED'}

        image_path = self.filepath
        image_name = os.path.basename(image_path)


        image = bpy.data.images.get(image_name)
        if not image:
            image = bpy.data.images.load(image_path)


        mat = bpy.data.materials.new(name="BA_Halo_Emission")
        mat.use_nodes = True

        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        nodes.clear()

        tex = nodes.new("ShaderNodeTexImage")
        tex.image = image
        tex.location = (-400, 0)

        halo_group = ensure_node_group("ba_halo")
        if not halo_group:
            self.report({'ERROR'}, "ba_halo node group not found")
            return {'CANCELLED'}
            
        halo = nodes.new("ShaderNodeGroup")
        halo.node_tree = halo_group
        halo.location = (-150, 0)

        output = nodes.new("ShaderNodeOutputMaterial")
        output.location = (200, 0)


        links.new(tex.outputs["Color"], halo.inputs[0])
        links.new(halo.outputs[0], output.inputs["Surface"])


        if obj.data.materials:
            obj.data.materials[0] = mat
        else:
            obj.data.materials.append(mat)

        return {'FINISHED'}

def setup_halo(context):
    bpy.ops.ba.halo_pick_image('INVOKE_DEFAULT')
