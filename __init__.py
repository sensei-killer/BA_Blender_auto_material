bl_info = {
    "name": "BA Auto Material Setup",
    "author": "sensei_killer&ChatGPT",
    "version": (0, 1, 1),
    "blender": (4, 5, 0),
    "location": "View3D > Sidebar > BA",
    "description": "Auto setup Body/Face/Hair materials with BA shaders",
    "category": "Material",
}

import bpy
import os
from bpy.props import StringProperty, CollectionProperty
from bpy.types import Operator, Panel, PropertyGroup
from . import ba_shader_controls
from . import ba_outline
from . import ba_props
from . import ba_props_outline
from . import ba_halo
from . import ba_mouth
from . import ba_ch_materials

# ---------------- operator ----------------

class BA_OT_setup_materials(Operator):
    bl_idname = "ba.setup_materials_ch"
    bl_label = "Setup Character Materials"

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
            for slot in obj.material_slots:
                if slot.material and slot.material.use_nodes:
                    mats.add(slot.material)

        for mat in mats:
            name = mat.name
            if name.endswith("_Body"):
                setup_body(mat, images)

            elif name.endswith("_Face"):
                setup_face(mat, images)

            elif name.endswith("_Hair"):
                setup_hair(mat, images)

            elif name.endswith("_EyeMouth"):
                setup_emission_from_images(mat, images, "EyeMouth", strength=1.0)

            elif name.endswith("_Eyebrow"):
                setup_emission_from_images(mat, images, "Eyebrow", strength=1.0)

        ba_shader_controls.ensure_hair_spec_control(context)
        ba_shader_controls.ensure_face_light_dot_control(context)
        
        empty = bpy.data.objects.get("face_light_dot")
        ba_shader_controls.add_face_rotation_drivers(empty, context)

        empty = bpy.data.objects.get("hair_spec_normal")
        ba_shader_controls.add_hair_rotation_drivers(empty, context)

        ba_outline.add_ba_outline(context)

        return {'FINISHED'}


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
            if ba_props.is_alpha_material(mat):
                ba_props.setup_alpha_material(mat, images)
            else:
                ba_props.setup_prop_material(mat, images)

            
        ba_props_outline.add_ba_props_outline(context)

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


# ---------------- register ----------------

classes = (
    ba_ch_materials.BA_OT_setup_materials,
    BA_OT_setup_prop,
    BA_OT_setup_halo,
    BA_OT_setup_mouth,
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

