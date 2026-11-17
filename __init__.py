bl_info = {
    "name": "BA Auto Material Setup",
    "author": "sensei_killer&ChatGPT",
    "version": (0, 2, 4),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > BA",
    "description": "Auto setup Body/Face/Hair materials with BA shaders",
    "category": "Material",
}

import bpy
from bpy.props import BoolProperty, StringProperty, CollectionProperty
from bpy.types import Operator, Panel, OperatorFileListElement
from . import ba_props
from . import ba_props_outline
from . import ba_halo
from . import ba_mouth
from . import ba_ch_materials
from . import ba_rigify
from . import ba_eye_controls
from .ba_utils import refresh_view_layer
from .ba_textures import MaterialSetupError, load_selected_images

# ---------------- operator ----------------


class BA_OT_setup_prop(Operator):
    bl_idname = "ba.setup_materials_prop"
    bl_label = "Setup weapon/props materials"
    bl_options = {'REGISTER', 'UNDO'}

    files: CollectionProperty(type=OperatorFileListElement, options={'HIDDEN', 'SKIP_SAVE'})
    directory: StringProperty(subtype='DIR_PATH')
    filter_glob: StringProperty(default='*.png;*.jpg;*.jpeg;*.tga;*.bmp;*.tif;*.tiff;*.dds;*.exr;*.hdr;*.webp', options={'HIDDEN'})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        try:
            images = load_selected_images(self.directory, self.files)
        except MaterialSetupError as exc:
            self.report({'WARNING'}, str(exc))
            return {'CANCELLED'}

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
                    
        successful = set()
        for mat in mats:
            try:
                if ba_props.is_car_alpha_material(mat):
                    ba_props.setup_car_alpha_material(mat, images)
                elif ba_props.is_alpha_material(mat):
                    ba_props.setup_alpha_material(mat, images)
                else:
                    ba_props.setup_prop_material(mat, images)
                successful.add(mat)
            except MaterialSetupError as exc:
                self.report({'WARNING'}, str(exc))
        if not successful:
            # Images, resource groups or a default material may already exist.
            self.report({'WARNING'}, "No prop materials were set; use Undo to restore prepared data")
            return {'FINISHED'}

            
        ba_props_outline.add_ba_props_outline(context)
        refresh_view_layer(context)

        self.report({'INFO'}, "Setup Prop")
        return {'FINISHED'}



class BA_OT_setup_halo(Operator):
    bl_idname = "ba.setup_materials_halo"
    bl_label = "Setup halo materials"

    # This launcher edits no data; the file-selector operator owns the undo step.
  
    def execute(self, context):
        ba_halo.setup_halo(context)
        return {'FINISHED'}


class BA_OT_setup_mouth(Operator):
    bl_idname = "ba.setup_mouth"
    bl_label = "Add mouth"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ba_mouth.setup_mouth(context)
        return {'FINISHED'}


class BA_OT_set_color_management(Operator):
    bl_idname = "ba.set_color_management"
    bl_label = "Set color management"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        scene.display_settings.display_device = 'sRGB'
        scene.view_settings.view_transform = 'Standard'
        self.report({'INFO'}, "Color Management set to sRGB / Standard")
        return {'FINISHED'}


class BA_OT_convert_to_rigify(Operator):
    bl_idname = "ba.convert_to_rigify"
    bl_label = "Convert to Rigify"
    # Keep nested Rigify/mode operators and the final data migration in one step.
    bl_options = {'REGISTER', 'UNDO'}

    include_eye_controls: BoolProperty(name="Include Eye Controls", default=True)

    def execute(self, context):
        if not self.properties.is_property_set("include_eye_controls"):
            self.include_eye_controls = context.scene.ba_include_eye_controls
        warnings = []
        try:
            ba_rigify.run_convert_to_rigify(self.include_eye_controls, warnings)
        except ba_rigify.ConversionRecoveryError as exc:
            self.report({'WARNING'}, f'{exc}; use Undo to restore the previous state')
            return {'FINISHED'}
        except RuntimeError as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        if warnings:
            self.report({'WARNING'}, "Converted to Rigify; " + "; ".join(warnings))
        else:
            self.report({'INFO'}, "Converted selection to Rigify")
        return {'FINISHED'}


class BA_OT_generate_eye_controls(Operator):
    bl_idname = "ba.generate_eye_controls"
    bl_label = "Generate Eye Controls"
    bl_description = "Add overall and individual eye controls to the selected armature"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        armatures = [obj for obj in context.selected_objects if obj.type == 'ARMATURE']
        valid = len(armatures) == 1 and context.active_object == armatures[0] and context.mode in {'OBJECT', 'POSE'}
        if not valid:
            cls.poll_message_set("Select one active armature in Object or Pose Mode")
        return valid

    def execute(self, context):
        try:
            created = ba_eye_controls.generate_eye_controls(context, context.active_object)
        except ba_eye_controls.EyeControlRecoveryError as exc:
            self.report({'WARNING'}, f'{exc}; use Undo to restore the previous state')
            return {'FINISHED'}
        except ba_eye_controls.EyeControlError as exc:
            self.report({'WARNING'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'}, "Eye controls generated" if created else "Eye controls already exist")
        return {'FINISHED'} if created else {'CANCELLED'}


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
        rigify = layout.column(align=True)
        operator = rigify.operator("ba.convert_to_rigify", icon='ARMATURE_DATA')
        operator.include_eye_controls = context.scene.ba_include_eye_controls
        rigify.prop(context.scene, "ba_include_eye_controls")
        rigify.operator("ba.generate_eye_controls", icon='HIDE_OFF')
        layout.operator("ba.set_color_management", icon='COLOR')


# ---------------- register ----------------

classes = (
    ba_ch_materials.BA_OT_setup_materials,
    BA_OT_setup_prop,
    BA_OT_setup_halo,
    BA_OT_setup_mouth,
    BA_OT_convert_to_rigify,
    BA_OT_generate_eye_controls,
    BA_OT_set_color_management,
    BA_PT_panel,
    ba_halo.BA_OT_halo_pick_image,
)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.ba_include_eye_controls = BoolProperty(
        name="Include Eye Controls", default=True,
        description="Add eye controls during Rigify conversion when compatible eye bones are available",
    )


def unregister():
    del bpy.types.Scene.ba_include_eye_controls
    for c in reversed(classes):
        bpy.utils.unregister_class(c)


if __name__ == "__main__":
    register()

