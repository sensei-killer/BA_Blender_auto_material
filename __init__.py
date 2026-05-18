bl_info = {
    "name": "BA Auto Material Setup",
    "author": "sensei_killer&ChatGPT",
    "version": (0, 1, 1),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > BA",
    "description": "Auto setup Body/Face/Hair materials with BA shaders",
    "category": "Material",
}

import bpy
import os
from bpy.props import StringProperty, CollectionProperty
from bpy.types import Operator, Panel, PropertyGroup
from . import ba_props
from . import ba_props_outline
from . import ba_halo
from . import ba_mouth
from . import ba_ch_materials
from . import ba_rigify
from .ba_utils import refresh_view_layer

# ---------------- operator ----------------


class BA_OT_setup_prop(Operator):
    bl_idname = "ba.setup_materials_prop"
    bl_label = "Setup weapon/props materials"

    files: CollectionProperty(type=PropertyGroup)
    directory: StringProperty(subtype='DIR_PATH')

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        images = []

        for f in self.files:
            path = os.path.join(self.directory, f.name)
            img = bpy.data.images.load(path, check_existing=True)
            images.append(img)

        mats = set()

        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue
            if len(obj.material_slots) == 0:
                mat = bpy.data.materials.new(name="Prop_Material")
                obj.data.materials.append(mat)
            for slot in obj.material_slots:
                if slot.material:
                    mats.add(slot.material)
                    
        for mat in mats:
            if ba_props.is_car_alpha_material(mat):
                ba_props.setup_car_alpha_material(mat, images)
            elif ba_props.is_alpha_material(mat):
                ba_props.setup_alpha_material(mat, images)
            else:
                ba_props.setup_prop_material(mat, images)

            
        ba_props_outline.add_ba_props_outline(context)
        refresh_view_layer(context)

        self.report({'INFO'}, "Setup Prop")
        return {'FINISHED'}



class BA_OT_setup_halo(Operator):
    bl_idname = "ba.setup_materials_halo"
    bl_label = "Setup halo materials"
  
    def execute(self, context):
        ba_halo.setup_halo(context)
        return {'FINISHED'}


class BA_OT_setup_mouth(Operator):
    bl_idname = "ba.setup_mouth"
    bl_label = "Add mouth"

    def execute(self, context):
        ba_mouth.setup_mouth(context)
        return {'FINISHED'}


class BA_OT_set_color_management(Operator):
    bl_idname = "ba.set_color_management"
    bl_label = "Set color management"

    def execute(self, context):
        scene = context.scene
        scene.display_settings.display_device = 'sRGB'
        scene.view_settings.view_transform = 'Standard'
        self.report({'INFO'}, "Color Management set to sRGB / Standard")
        return {'FINISHED'}


class BA_OT_convert_to_rigify(Operator):
    bl_idname = "ba.convert_to_rigify"
    bl_label = "Convert to Rigify"

    def execute(self, context):
        ba_rigify.run_convert_to_rigify()
        self.report({'INFO'}, "Converted selection to Rigify")
        return {'FINISHED'}


# ---------------- panel ----------------

class BA_PT_panel(Panel):
    bl_label = "BA Auto Material"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BA'
        
    def draw(self, context):
        layout = self.layout

        col = layout.column(align=True)
        col.operator("ba.setup_materials_ch", icon='MATERIAL')
        col.operator("ba.setup_materials_prop", icon='MATERIAL')
        col.operator("ba.setup_materials_halo", icon='MATERIAL')

        layout.separator()

        layout.operator("ba.setup_mouth", icon='MATERIAL')
        layout.operator("ba.convert_to_rigify", icon='ARMATURE_DATA')
        layout.operator("ba.set_color_management", icon='COLOR')


# ---------------- register ----------------

classes = (
    ba_ch_materials.BA_OT_setup_materials,
    BA_OT_setup_prop,
    BA_OT_setup_halo,
    BA_OT_setup_mouth,
    BA_OT_convert_to_rigify,
    BA_OT_set_color_management,
    BA_PT_panel,
    ba_halo.BA_OT_halo_pick_image,
)


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)


if __name__ == "__main__":
    register()

