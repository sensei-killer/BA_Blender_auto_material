import bpy


CONTROL_EMPTY_NAME = "hair_spec_normal"
CONTROL_EMPTY_NAME_FACE = "face_light_dot"
SHARED_SHADER_DRIVER_NODE_GROUPS = (
    "ba_face_shader",
    "ba_hair_shader",
    "BA_SPEC",
)

RIGIFY_HEAD_BONE_CANDIDATES = (
    "head",
    "DEF-spine.006",
    "ORG-spine.006",
    "spine.006",
    "Bip001 Head",
)

IGNORED_RIG_NAME_TOKENS = ("mouthre",)


def is_ignored_rig(obj):
    if obj is None or obj.type != "ARMATURE":
        return False
    lowered = obj.name.lower()
    return any(token in lowered for token in IGNORED_RIG_NAME_TOKENS)


def find_rig_from_objects(objs):
    rigs = {rig_for_object(obj) for obj in objs}
    rigs.discard(None)
    return next(iter(rigs)) if len(rigs) == 1 else None


def rig_for_object(obj):
    if obj.type == 'ARMATURE':
        return None if is_ignored_rig(obj) else obj
    rigs = {m.object for m in obj.modifiers if m.type == 'ARMATURE' and m.object and not is_ignored_rig(m.object)}
    if obj.parent and obj.parent.type == 'ARMATURE' and not is_ignored_rig(obj.parent):
        rigs.add(obj.parent)
    return next(iter(rigs)) if len(rigs) == 1 else None


def isolate_character_materials(context):
    """Only split driver-bearing materials that are used by different rigs."""
    copies = {}
    for obj in context.selected_objects:
        if obj.type != 'MESH':
            continue
        rig = rig_for_object(obj)
        if rig is None:
            continue
        for slot in obj.material_slots:
            mat = slot.material
            if mat is None:
                continue
            name = mat.name.rsplit('.', 1)[0] if mat.name[-3:].isdigit() else mat.name
            if not name.endswith(('_Face', '_Hair', '_Hair_Alpha')):
                continue
            other_owners = {
                rig_for_object(other) for other in bpy.data.objects
                if other.type == 'MESH' and other != obj
                and any(s.material == mat for s in other.material_slots)
            }
            if other_owners - {rig}:
                key = (mat, rig)
                if key not in copies:
                    copies[key] = mat.copy()
                if slot.link == 'DATA' and obj.data.users > 1:
                    obj.data = obj.data.copy()
                slot.material = copies[key]


def find_head_bone(rig):
    if rig is None or rig.type != 'ARMATURE':
        return None

    for name in RIGIFY_HEAD_BONE_CANDIDATES:
        if rig.data.bones.get(name):
            return name

    for bone in rig.data.bones:
        if bone.name.endswith("Head"):
            return bone.name
    return None


def configure_rotation_only_child_of(constraint):
    constraint.use_location_x = False
    constraint.use_location_y = False
    constraint.use_location_z = False
    constraint.use_rotation_x = True
    constraint.use_rotation_y = True
    constraint.use_rotation_z = True
    constraint.use_scale_x = False
    constraint.use_scale_y = False
    constraint.use_scale_z = False


def child_of_target_rotation(constraint, depsgraph):
    """World-space, rotation-only target used by BA's head constraint."""
    target = constraint.target
    if target is None:
        return None
    evaluated = target.evaluated_get(depsgraph)
    world = evaluated.matrix_world
    if constraint.subtarget and evaluated.type == 'ARMATURE':
        bone = evaluated.pose.bones.get(constraint.subtarget)
        if bone is None:
            return None
        world = world @ bone.matrix
    return world.to_quaternion().to_matrix().to_4x4()


def ensure_head_control(context, empty_name, rig=None):
    if rig is None:
        rig = find_rig_from_objects(context.selected_objects)
    if rig is None:
        return None

    head_bone = find_head_bone(rig)
    if head_bone is None:
        return None

    empty = next((obj for obj in bpy.data.objects if obj.get('_ba_owner_rig') == rig and obj.get('_ba_control_role') == empty_name), None)
    legacy = bpy.data.objects.get(empty_name)
    if empty is None and legacy and not legacy.get('_ba_owner_rig'):
        targets = {c.target for c in legacy.constraints if c.type in {'CHILD_OF', 'COPY_LOCATION'} and c.target}
        if targets == {rig}:
            empty = legacy
            for constraint in empty.constraints:
                if constraint.type == 'COPY_LOCATION' and constraint.target == rig:
                    constraint.name = 'BA_CopyHeadLocation'
                elif constraint.type == 'CHILD_OF' and constraint.target == rig:
                    constraint.name = 'BA_HeadRotation'
    if empty is None:
        empty = bpy.data.objects.new(f'{empty_name}__{rig.name}', None)
        context.collection.objects.link(empty)
    empty['_ba_owner_rig'] = rig
    empty['_ba_control_role'] = empty_name

    copy_location = None
    for c in empty.constraints:
        if c.type == 'COPY_LOCATION' and c.name == 'BA_CopyHeadLocation':
            copy_location = c
            break

    if copy_location is None:
        copy_location = empty.constraints.new(type='COPY_LOCATION')
        copy_location.name = 'BA_CopyHeadLocation'
    copy_location.target = rig
    copy_location.subtarget = head_bone

    child_of = None
    for c in empty.constraints:
        if c.type == 'CHILD_OF' and c.name == 'BA_HeadRotation':
            child_of = c
            break

    previous_rotation = None
    if child_of is not None and (child_of.target != rig or child_of.subtarget != head_bone):
        context.view_layer.update()
        target_rotation = child_of_target_rotation(child_of, context.evaluated_depsgraph_get())
        if target_rotation is not None:
            inverse_rotation = child_of.inverse_matrix.to_quaternion().to_matrix().to_4x4()
            previous_rotation = target_rotation @ inverse_rotation

    if child_of is None:
        child_of = empty.constraints.new(type='CHILD_OF')
        child_of.name = 'BA_HeadRotation'
    child_of.target = rig
    child_of.subtarget = head_bone
    configure_rotation_only_child_of(child_of)
    if previous_rotation is not None:
        # Rigify head axes differ from BA bones; retain the old constraint delta.
        target_rotation = child_of_target_rotation(child_of, context.evaluated_depsgraph_get())
        child_of.inverse_matrix = target_rotation.inverted() @ previous_rotation
        child_of.set_inverse_pending = False

    return empty


def ensure_hair_spec_control(context):
    return ensure_head_control(context, CONTROL_EMPTY_NAME)


def ensure_face_light_dot_control(context):
    return ensure_head_control(context, CONTROL_EMPTY_NAME_FACE)


def retarget_shader_controls_to_rig(context, rig, source=None):
    if source is not None:
        for obj in bpy.data.objects:
            if obj.get('_ba_owner_rig') == source:
                obj['_ba_owner_rig'] = rig
            elif obj.name in (CONTROL_EMPTY_NAME, CONTROL_EMPTY_NAME_FACE) and not obj.get('_ba_owner_rig'):
                if any(c.type == 'CHILD_OF' and c.target == source for c in obj.constraints):
                    obj['_ba_owner_rig'] = rig
                    obj['_ba_control_role'] = obj.name
                    for c in obj.constraints:
                        if c.type == 'COPY_LOCATION' and c.target == source:
                            c.name = 'BA_CopyHeadLocation'
                        elif c.type == 'CHILD_OF' and c.target == source:
                            c.name = 'BA_HeadRotation'
    hair_empty = ensure_head_control(context, CONTROL_EMPTY_NAME, rig=rig)
    face_empty = ensure_head_control(context, CONTROL_EMPTY_NAME_FACE, rig=rig)

    remove_shared_node_group_drivers()
    add_hair_rotation_drivers(hair_empty, context)
    add_face_rotation_drivers(face_empty, context)

    return hair_empty, face_empty


def remove_shared_node_group_drivers():
    removed = 0

    for node_group_name in SHARED_SHADER_DRIVER_NODE_GROUPS:
        node_group = bpy.data.node_groups.get(node_group_name)
        if node_group is None or node_group.animation_data is None:
            continue

        for fcurve in list(node_group.animation_data.drivers):
            if node_group_name != 'BA_SPEC' or fcurve.data_path != 'nodes["Vector Rotate"].inputs[4].default_value':
                continue
            if not any(t.id is None for v in fcurve.driver.variables for t in v.targets):
                continue
            try:
                node_group.driver_remove(fcurve.data_path, fcurve.array_index)
                removed += 1
            except (TypeError, ValueError, RuntimeError) as exc:
                print(
                    f"[Warning] Could not remove driver from node group "
                    f"{node_group.name}: {fcurve.data_path}[{fcurve.array_index}] ({exc})"
                )

    return removed


def _find_rotation_shader_node(mat, node_group_name):
    if not mat or not mat.use_nodes:
        return None

    for node in mat.node_tree.nodes:
        if node.type == 'GROUP' and node.node_tree and node.node_tree.name == node_group_name:
            return node
    return None


def _add_rotation_drivers(empty, context, node_group_name, axis_map, invert_map, materials=None):
    if empty is None:
        return

    if materials is None:
        materials = {s.material for obj in context.selected_objects if obj.type == 'MESH' for s in obj.material_slots if s.material}
    for mat in materials:
        if mat:
            shader_node = _find_rotation_shader_node(mat, node_group_name)
            if shader_node is None:
                continue

            rotation_input = shader_node.inputs.get("Rotation")
            if rotation_input is None:
                print(f"[Warning] Node Group {shader_node.node_tree.name} has no input named 'Rotation'")
                continue
            if rotation_input.type != 'VECTOR':
                print(f"[Warning] Input 'Rotation' of Node Group {shader_node.node_tree.name} is not VECTOR")
                continue

            for i, (axis, invert) in enumerate(zip(axis_map, invert_map)):
                try:
                    rotation_input.driver_remove("default_value", i)
                except TypeError:
                    pass

                fcurve = rotation_input.driver_add("default_value", i)
                driver = fcurve.driver
                driver.type = 'SCRIPTED'

                var = driver.variables.new()
                var.name = 'rot'
                var.type = 'TRANSFORMS'

                target = var.targets[0]
                target.id = empty
                target.transform_type = f'ROT_{axis}'
                target.transform_space = 'WORLD_SPACE'

                driver.expression = '-rot' if invert else 'rot'


def add_face_rotation_drivers(empty, context):
    _add_rotation_drivers(empty, context, 'ba_face_shader', ['X', 'Y', 'Z'], [False, False, False])


def add_hair_rotation_drivers(empty, context):
    _add_rotation_drivers(empty, context, 'ba_hair_shader', ['X', 'Z', 'Y'], [True, True, True])


def bind_character_controls(context, materials):
    for rig in {rig_for_object(obj) for obj in context.selected_objects if obj.type == 'MESH'} - {None}:
        owned = {s.material for obj in context.selected_objects if obj.type == 'MESH' and rig_for_object(obj) == rig for s in obj.material_slots if s.material in materials}
        hair = ensure_head_control(context, CONTROL_EMPTY_NAME, rig)
        face = ensure_head_control(context, CONTROL_EMPTY_NAME_FACE, rig)
        _add_rotation_drivers(hair, context, 'ba_hair_shader', ['X', 'Z', 'Y'], [True, True, True], owned)
        _add_rotation_drivers(face, context, 'ba_face_shader', ['X', 'Y', 'Z'], [False, False, False], owned)
