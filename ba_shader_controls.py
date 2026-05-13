import bpy


CONTROL_EMPTY_NAME = "hair_spec_normal"
CONTROL_EMPTY_NAME_FACE = "face_light_dot"


def find_rig_from_objects(objs):
    for obj in objs:
        if obj.type == 'ARMATURE':
            return obj
        if obj.parent and obj.parent.type == 'ARMATURE':
            return obj.parent
    return None


def find_head_bone(rig):
    for bone in rig.data.bones:
        if bone.name.endswith("Head"):
            return bone.name
    return None


def ensure_head_control(context, empty_name):
    rig = find_rig_from_objects(context.selected_objects)
    if rig is None:
        return None

    head_bone = find_head_bone(rig)
    if head_bone is None:
        return None

    empty = bpy.data.objects.get(empty_name)
    if empty is None:
        empty = bpy.data.objects.new(empty_name, None)
        context.collection.objects.link(empty)

    empty.constraints.clear()

    copy_location = None
    for c in empty.constraints:
        if c.type == 'COPY_LOCATION':
            copy_location = c
            break

    if copy_location is None:
        copy_location = empty.constraints.new(type='COPY_LOCATION')
    copy_location.target = rig
    copy_location.subtarget = head_bone

    child_of = None
    for c in empty.constraints:
        if c.type == 'CHILD_OF' and c.target == rig and c.subtarget == head_bone:
            child_of = c
            break

    if child_of is None:
        child_of = empty.constraints.new(type='CHILD_OF')
    child_of.target = rig
    child_of.subtarget = head_bone

    return empty


def ensure_hair_spec_control(context):
    return ensure_head_control(context, CONTROL_EMPTY_NAME)


def ensure_face_light_dot_control(context):
    return ensure_head_control(context, CONTROL_EMPTY_NAME_FACE)


def _find_rotation_shader_node(mat, node_group_name):
    if not mat or not mat.use_nodes:
        return None

    for node in mat.node_tree.nodes:
        if node.type == 'GROUP' and node.node_tree and node.node_tree.name == node_group_name:
            return node
    return None


def _add_rotation_drivers(empty, context, node_group_name, axis_map, invert_map):
    if empty is None:
        return

    for obj in context.selected_objects:
        if obj.type != 'MESH':
            continue

        for slot in obj.material_slots:
            mat = slot.material
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
