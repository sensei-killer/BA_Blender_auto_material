# ba_halo.py
import bpy
import os
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty
from types import SimpleNamespace

from .ba_textures import MaterialSetupError, load_selected_images
from .ba_utils import require_node_groups, safe_link

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
        try:
            image = load_selected_images(
                os.path.dirname(image_path),
                [SimpleNamespace(name=os.path.basename(image_path))],
            )[0]
        except MaterialSetupError as exc:
            self.report({'WARNING'}, str(exc))
            return {'CANCELLED'}

        try:
            halo_group = require_node_groups({'ba_halo': ((), ())})['ba_halo']
            sockets = [s for s in halo_group.interface.items_tree if s.item_type == 'SOCKET']
            if not any(s.in_out == 'INPUT' for s in sockets) or not any(s.in_out == 'OUTPUT' for s in sockets):
                raise MaterialSetupError('ba_halo must have input and output sockets')
        except MaterialSetupError as exc:
            self.report({'WARNING'}, f'{exc}; use Undo to restore prepared data')
            return {'FINISHED'}

        mat = bpy.data.materials.new(name="BA_Halo_Emission")
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        nodes.clear()

        tex = nodes.new("ShaderNodeTexImage")
        tex.image = image
        tex.location = (-400, 0)

        halo = nodes.new("ShaderNodeGroup")
        halo.node_tree = halo_group
        halo.location = (-150, 0)

        output = nodes.new("ShaderNodeOutputMaterial")
        output.location = (200, 0)


        safe_link(mat.node_tree, tex.outputs.get("Color"), halo.inputs[0])
        safe_link(mat.node_tree, halo.outputs[0], output.inputs.get("Surface"))


        if obj.data.materials:
            obj.data.materials[0] = mat
        else:
            obj.data.materials.append(mat)

        return {'FINISHED'}

def setup_halo(context):
    bpy.ops.ba.halo_pick_image('INVOKE_DEFAULT', True)
