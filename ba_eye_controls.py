"""Constraint-based eye controls shared by the standalone and Rigify workflows."""

from math import radians

import bpy
from mathutils import Vector

if __package__:
    from .ba_rigify_state import ConversionRecoveryError, constraint_state, copy_value
else:
    from ba_rigify_state import ConversionRecoveryError, constraint_state, copy_value


EYE_NAMES = {side: "Bip001 Xtra_eye" + side for side in ("L", "R")}
MCH_NAMES = {side: "Eye_mch." + side for side in ("L", "R")}
CTRL_NAMES = {"ALL": "Eye_ctrl_all", "L": "Eye_ctrl.L", "R": "Eye_ctrl.R"}
GENERATED_NAMES = tuple(MCH_NAMES.values()) + tuple(CTRL_NAMES.values())
ROLE_KEY = "_ba_eye_role"
WIDGET_KEY = "_ba_eye_widget"
COLLECTION_KEY = "_ba_eye_collection"
CTRL_OFFSET = 0.40
CTRL_SPACING = 0.15
CONSTRAINTS = tuple(
    (MCH_NAMES[side], name, "TRANSFORM", target)
    for side in ("L", "R")
    for name, target in (("Eye Overall Transform", CTRL_NAMES["ALL"]),
                         ("Eye Individual Transform", CTRL_NAMES[side]))
) + tuple((EYE_NAMES[side], "Eye Control Scale", "COPY_SCALE", CTRL_NAMES[side])
          for side in ("L", "R"))
POSE_PROPERTIES = (
    "rotation_mode", "matrix_basis", "lock_location", "lock_rotation",
    "lock_rotation_w", "lock_rotations_4d", "lock_scale", "custom_shape",
    "use_custom_shape_bone_size", "custom_shape_scale_xyz",
    "custom_shape_rotation_euler", "custom_shape_translation", "custom_shape_wire_width",
)


class EyeControlError(RuntimeError):
    """Eye controls cannot be created without disturbing existing data."""


class EyeControlRecoveryError(ConversionRecoveryError):
    """An interrupted setup must retain the operator's Undo boundary."""


def validate_editable(context, armature):
    if armature is None or armature.type != "ARMATURE":
        raise EyeControlError("Select an armature for eye controls")
    if armature.library or armature.data.library or not armature.is_editable:
        raise EyeControlError("Eye controls require an editable local armature")
    if armature.data.users != 1:
        raise EyeControlError("Make the armature data single-user before adding eye controls")
    if context.mode not in {"OBJECT", "POSE"}:
        raise EyeControlError("Add eye controls in Object or Pose Mode")
    if context.view_layer.objects.get(armature.name) != armature or not armature.visible_get():
        raise EyeControlError("The eye-control armature must be visible in the active view layer")


def validate_eye_bones(armature):
    bones = armature.data.bones
    missing = [name for name in EYE_NAMES.values() if bones.get(name) is None]
    if missing:
        raise EyeControlError("Missing eye bones: " + ", ".join(missing))
    left, right = (bones[EYE_NAMES[side]] for side in ("L", "R"))
    if (right.head_local - left.head_local).length < 1e-6:
        raise EyeControlError("Left and right eye bones must have distinct head positions")


def validate_new_setup(armature):
    validate_eye_bones(armature)
    bones = armature.data.bones
    if any(bones.get(name) is not None for name in GENERATED_NAMES):
        raise EyeControlError("Eye control names already exist; check the existing setup first")
    left, right = (bones[EYE_NAMES[side]] for side in ("L", "R"))
    if left.parent is None or left.parent != right.parent:
        raise EyeControlError("Left and right eye bones must share a valid original parent")
    for side in ("L", "R"):
        if armature.pose.bones[EYE_NAMES[side]].constraints.get("Eye Control Scale"):
            raise EyeControlError("An existing Eye Control Scale constraint would conflict with eye setup")


def validate_hierarchy(armature):
    validate_eye_bones(armature)
    bones = armature.data.bones
    missing = [name for name in GENERATED_NAMES if bones.get(name) is None]
    if missing:
        raise EyeControlError("Incomplete eye controls; missing: " + ", ".join(missing))
    parent = bones[MCH_NAMES["L"]].parent
    if parent is None or bones[MCH_NAMES["R"]].parent != parent or bones[CTRL_NAMES["ALL"]].parent != parent:
        raise EyeControlError("Eye mechanism bones and the overall control must share their original parent")
    for side in ("L", "R"):
        if bones[EYE_NAMES[side]].parent != bones[MCH_NAMES[side]] or bones[CTRL_NAMES[side]].parent != bones[CTRL_NAMES["ALL"]]:
            raise EyeControlError("Existing eye-control parenting is incomplete or incompatible")
    if any(bones[name].use_deform for name in GENERATED_NAMES):
        raise EyeControlError("Eye mechanism and control bones must not deform the mesh")


def capture_setup(armature):
    """Recognize complete plugin controls, or the exact original script's structure."""
    if not any(armature.data.bones.get(name) is not None for name in GENERATED_NAMES):
        return None
    validate_hierarchy(armature)
    constraints = []
    for owner, name, kind, target in CONSTRAINTS:
        constraint = armature.pose.bones[owner].constraints.get(name)
        if constraint is None or constraint.type != kind or constraint.target != armature or constraint.subtarget != target:
            raise EyeControlError("Existing eye controls have conflicting or missing constraints: " + name)
        constraints.append((owner, kind, constraint_state(constraint)[1]))
    for name in CTRL_NAMES.values():
        shape = armature.pose.bones[name].custom_shape
        if shape is None or shape.type != "MESH":
            raise EyeControlError("Existing eye controls have missing or incompatible custom shapes")
    return {
        "source": armature,
        "constraints": constraints,
        "pose": {name: {prop: copy_value(getattr(armature.pose.bones[name], prop))
                        for prop in POSE_PROPERTIES}
                 for name in GENERATED_NAMES + tuple(EYE_NAMES.values())},
    }


def activate(context, armature, mode="OBJECT"):
    if context.object and context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    armature.select_set(True)
    context.view_layer.objects.active = armature
    if mode != "OBJECT":
        bpy.ops.object.mode_set(mode=mode)


class EyeBuildState:
    def __init__(self, context, armature):
        self.context, self.armature = context, armature
        self.selected = list(context.selected_objects)
        self.active = context.view_layer.objects.active
        self.mode = self.active.mode if self.active else "OBJECT"
        self.parents = {name: (armature.data.bones[name].parent.name, armature.data.bones[name].use_connect)
                        for name in EYE_NAMES.values()}
        self.bones, self.constraints = [], []
        self.objects, self.meshes, self.collections, self.bone_collections = [], [], [], []

    def restore_context(self):
        if self.context.object and self.context.object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.select_all(action="DESELECT")
        for obj in self.selected:
            obj.select_set(True)
        self.context.view_layer.objects.active = self.active
        if self.active and self.mode != "OBJECT":
            bpy.ops.object.mode_set(mode=self.mode)
        self.context.view_layer.update()

    def rollback(self):
        activate(self.context, self.armature)
        for owner, name in reversed(self.constraints):
            constraint = self.armature.pose.bones[owner].constraints.get(name)
            if constraint:
                self.armature.pose.bones[owner].constraints.remove(constraint)
        activate(self.context, self.armature, "EDIT")
        for name, (parent, connected) in self.parents.items():
            bone = self.armature.data.edit_bones[name]
            bone.use_connect = False
            bone.parent = self.armature.data.edit_bones.get(parent)
            bone.use_connect = connected
        for name in reversed(self.bones):
            bone = self.armature.data.edit_bones.get(name)
            if bone:
                self.armature.data.edit_bones.remove(bone)
        bpy.ops.object.mode_set(mode="OBJECT")
        for name in self.bone_collections:
            collection = self.armature.data.collections.get(name)
            if collection and len(collection.bones) == 0:
                self.armature.data.collections.remove(collection)
        for obj in self.objects:
            bpy.data.objects.remove(obj, do_unlink=True)
        for mesh in self.meshes:
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)
        for collection in self.collections:
            if not collection.objects and not collection.children:
                bpy.data.collections.remove(collection)


def new_bone(armature, state, name, head, length, parent):
    bone = armature.data.edit_bones.new(name)
    state.bones.append(bone.name)
    bone.head = head
    bone.tail = head + Vector((0.0, 0.0, max(length, 0.0001)))
    bone.roll = 0.0
    bone.use_connect = False
    bone.parent = armature.data.edit_bones[parent]
    bone.use_deform = False


def ensure_shape(context, state):
    shape = next((obj for obj in bpy.data.objects if obj.get(WIDGET_KEY) and obj.type == "MESH" and not obj.library), None)
    if shape:
        return shape
    collection = next((col for col in context.scene.collection.children if col.get(WIDGET_KEY)), None)
    if collection is None:
        collection = bpy.data.collections.new("BA Eye Widgets")
        state.collections.append(collection)
        collection[WIDGET_KEY] = True
        context.scene.collection.children.link(collection)
    mesh = bpy.data.meshes.new("WGT-BA-Eye_Mesh")
    state.meshes.append(mesh)
    mesh.from_pydata([(-.25, -.25, 0), (.25, -.25, 0), (.25, .25, 0), (-.25, .25, 0)],
                     [(0, 1), (1, 2), (2, 3), (3, 0)], [])
    mesh.update()
    shape = bpy.data.objects.new("WGT-BA-Eye", mesh)
    state.objects.append(shape)
    shape[WIDGET_KEY] = True
    collection.objects.link(shape)
    shape.hide_viewport = True
    shape.hide_render = True
    shape.hide_set(True)
    shape.display_type = "WIRE"
    return shape


def organize_bones(armature, state=None):
    for role, title, names in (("controls", "BA Eye Controls", tuple(CTRL_NAMES.values())),
                               ("mechanism", "BA Eye Mechanism", tuple(MCH_NAMES.values()))):
        collection = next((col for col in armature.data.collections if col.get(COLLECTION_KEY) == role), None)
        if collection is None:
            collection = armature.data.collections.new(title)
            if state:
                state.bone_collections.append(collection.name)
            collection[COLLECTION_KEY] = role
            collection.is_visible = role == "controls"
        for name in names:
            bone = armature.data.bones[name]
            bone[ROLE_KEY] = name
            for old in list(bone.collections):
                old.unassign(bone)
            collection.assign(bone)


def add_constraint(armature, state, owner, name, kind):
    constraint = armature.pose.bones[owner].constraints.new(kind)
    if state:
        state.constraints.append((owner, constraint.name))
    constraint.name = name
    if state:
        state.constraints[-1] = (owner, constraint.name)
    return constraint


def configure_constraints(armature, state):
    for owner, name, kind, target in CONSTRAINTS:
        constraint = add_constraint(armature, state, owner, name, kind)
        constraint.target, constraint.subtarget = armature, target
        if kind == "COPY_SCALE":
            constraint.owner_space = constraint.target_space = "WORLD"
            continue
        constraint.owner_space = constraint.target_space = "LOCAL"
        constraint.map_from, constraint.map_to = "LOCATION", "ROTATION"
        constraint.map_to_x_from, constraint.map_to_y_from, constraint.map_to_z_from = "Y", "X", "Y"
        constraint.mix_mode_rot = "ADD"
        constraint.use_motion_extrapolate = False
        for axis in ("x", "y", "z"):
            setattr(constraint, "from_min_" + axis, -.4)
            setattr(constraint, "from_max_" + axis, .4)
        constraint.to_min_x_rot, constraint.to_max_x_rot = radians(90), radians(-90)
        constraint.to_min_y_rot, constraint.to_max_y_rot = radians(-90), radians(90)
        constraint.to_min_z_rot = constraint.to_max_z_rot = 0.0


def generate_eye_controls(context, armature):
    validate_editable(context, armature)
    if capture_setup(armature) is not None:
        return False
    validate_new_setup(armature)
    bones = armature.data.bones
    parent = bones[EYE_NAMES["L"]].parent.name
    heads = {side: bones[EYE_NAMES[side]].head_local.copy() for side in ("L", "R")}
    lengths = {side: max(bones[EYE_NAMES[side]].length, .0001) for side in ("L", "R")}
    del bones
    midpoint = (heads["L"] + heads["R"]) * .5
    eye_axis = (heads["R"] - heads["L"]).normalized()
    offset = Vector((0.0, -CTRL_OFFSET, 0.0))
    state = EyeBuildState(context, armature)
    try:
        activate(context, armature, "EDIT")
        for side in ("L", "R"):
            new_bone(armature, state, MCH_NAMES[side], heads[side], lengths[side], parent)
            eye = armature.data.edit_bones[EYE_NAMES[side]]
            eye.use_connect = False
            eye.parent = armature.data.edit_bones[MCH_NAMES[side]]
            del eye
        new_bone(armature, state, CTRL_NAMES["ALL"], midpoint + offset, max(lengths.values()), parent)
        for side, sign in (("L", -1), ("R", 1)):
            new_bone(armature, state, CTRL_NAMES[side], midpoint + offset + eye_axis * (sign * CTRL_SPACING * .5),
                     lengths[side] * .5, CTRL_NAMES["ALL"])
        bpy.ops.object.mode_set(mode="OBJECT")
        shape = ensure_shape(context, state)
        configure_constraints(armature, state)
        for name in GENERATED_NAMES:
            armature.pose.bones[name].rotation_mode = "XYZ"
        for role, name in CTRL_NAMES.items():
            bone = armature.pose.bones[name]
            bone.custom_shape = shape
            bone.use_custom_shape_bone_size = True
            bone.custom_shape_wire_width = 1.0
            bone.custom_shape_scale_xyz = (3.0, 1.0, 1.0) if role == "ALL" else (1.0, 1.0, 1.0)
            bone.lock_location = (False, False, True)
            bone.lock_rotation = (True, True, True)
        organize_bones(armature, state)
        context.view_layer.update()
        capture_setup(armature)
        state.restore_context()
    except Exception as exc:
        errors = []
        for recover in (state.rollback, state.restore_context):
            try:
                recover()
            except Exception as recovery_exc:
                errors.append(str(recovery_exc))
        if errors:
            raise EyeControlRecoveryError("Eye setup recovery incomplete: " + "; ".join(errors)) from exc
        raise EyeControlError(f"Eye setup failed: {exc}; original data restored") from exc
    return True


def restore_migrated_controls(context, armature, setup):
    """Extra-bone migration copies structure only; restore this feature's pose data."""
    validate_hierarchy(armature)
    for name, properties in setup["pose"].items():
        for prop, value in properties.items():
            setattr(armature.pose.bones[name], prop, value)
    for owner, kind, values in setup["constraints"]:
        if armature.pose.bones[owner].constraints.get(values["name"]):
            raise EyeControlError("Migrated eye constraint already exists: " + values["name"])
        constraint = add_constraint(armature, None, owner, values["name"], kind)
        for prop, value in values.items():
            if prop == "target" and value == setup["source"]:
                value = armature
            setattr(constraint, prop, value)
    organize_bones(armature)
    context.view_layer.update()
    capture_setup(armature)
