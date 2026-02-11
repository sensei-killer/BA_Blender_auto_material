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


def ensure_hair_spec_control(context):
    rig = find_rig_from_objects(context.selected_objects)
    if rig is None:
        return None

    head_bone = find_head_bone(rig)
    if head_bone is None:
        return None

    # Try reuse existing empty
    empty = bpy.data.objects.get(CONTROL_EMPTY_NAME)

    if empty is None:
        empty = bpy.data.objects.new(CONTROL_EMPTY_NAME, None)
        context.collection.objects.link(empty)

    empty.constraints.clear()

    #Child Of
    child = None
    for c in empty.constraints:
        if c.type == 'CHILD_OF' and c.target == rig and c.subtarget == head_bone:
            child = c
            break

    if child is None:
        child = empty.constraints.new(type='CHILD_OF')

    child.target = rig
    child.subtarget = head_bone


    # Ensure copy location constraint
    con = None
    for c in empty.constraints:
        if c.type == 'COPY_LOCATION':
            con = c
            break

    if con is None:
        con = empty.constraints.new(type='COPY_LOCATION')

    con.target = rig
    con.subtarget = head_bone

    return empty

def ensure_face_light_dot_control(context):
    rig = find_rig_from_objects(context.selected_objects)
    if rig is None:
        return None

    head_bone = find_head_bone(rig)
    if head_bone is None:
        return None

    # Try reuse existing empty
    empty = bpy.data.objects.get(CONTROL_EMPTY_NAME_FACE)

    if empty is None:
        empty = bpy.data.objects.new(CONTROL_EMPTY_NAME_FACE, None)
        context.collection.objects.link(empty)

    empty.constraints.clear()


    con = None
    for c in empty.constraints:
        if c.type == 'COPY_LOCATION':
            con = c
            break

    if con is None:
        con = empty.constraints.new(type='COPY_LOCATION')

    con.target = rig
    con.subtarget = head_bone


    child = None
    for c in empty.constraints:
        if c.type == 'CHILD_OF' and c.target == rig and c.subtarget == head_bone:
            child = c
            break

    if child is None:
        child = empty.constraints.new(type='CHILD_OF')

    child.target = rig
    child.subtarget = head_bone

    return empty
    
    
def add_face_rotation_drivers(empty, context):

    for obj in context.selected_objects:
        if obj.type != 'MESH':
            continue
        for slot in obj.material_slots:
            mat = slot.material
            if not mat or not mat.use_nodes:
                continue
            nt = mat.node_tree


            shader_node = None
            for node in nt.nodes:
                if node.type == 'GROUP' and node.node_tree and node.node_tree.name == 'ba_face_shader':
                    shader_node = node
                    break

            if shader_node is None:
                continue


            rotation_input = shader_node.inputs.get("Rotation")
            if rotation_input is None:
                print(f"[Warning] Node Group {shader_node.node_tree.name} has no input named 'Rotation'")
                continue
            if rotation_input.type != 'VECTOR':
                print(f"[Warning] Input 'Rotation' of Node Group {shader_node.node_tree.name} is not VECTOR")
                continue


            for i, axis in enumerate(['X','Y','Z']):
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

                driver.expression = 'rot'
                
def add_hair_rotation_drivers(empty, context):

    axis_map = ['X', 'Z', 'Y']  
    invert_map = [True, True, True]  

    for obj in context.selected_objects:
        if obj.type != 'MESH':
            continue
        for slot in obj.material_slots:
            mat = slot.material
            if not mat or not mat.use_nodes:
                continue
            nt = mat.node_tree


            shader_node = None
            for node in nt.nodes:
                if node.type == 'GROUP' and node.node_tree and node.node_tree.name == 'ba_hair_shader':
                    shader_node = node
                    break

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

