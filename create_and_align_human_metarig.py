import bpy
from mathutils import Vector

# Create a fresh Rigify Human metarig, remove face bones, then align it to the
# source character skeleton. This script is intended to be run inside Blender.
#
# Select the source armature, then run this script. It creates a fresh Rigify
# Human metarig and aligns it to the selected source.
#
# Updated spine policy:
# - Keep the standard Human spine chain, including spine.001 and spine.002.
# - spine.001 is a very short required transition bone and is not used as a
#   main source-mapped torso segment.
# - spine.002 carries the main lower-to-upper torso mapping.

OUTPUT_NAME_SUFFIX = "_metarig_auto"
BACKUP_EXISTING_OUTPUT = True
INITIAL_METARIG_SCALE = 0.38
HEAD_BONE_LENGTH = 0.25

REMOVE_FACE = True
REMOVE_MISSING_OPTIONAL_FINGERS = True
SPINE_001_HEIGHT_RATIO = 0.003
SPINE_001_MIN_LENGTH = 0.003
MIN_BONE_LENGTH = 0.001

WORLD_Z = Vector((0.0, 0.0, 1.0))
WORLD_X = Vector((1.0, 0.0, 0.0))
WORLD_NEG_Y = Vector((0.0, -1.0, 0.0))

report = {
    "created": [],
    "deleted": [],
    "aligned": [],
    "derived": [],
    "missing_source": [],
    "missing_target": [],
    "warnings": [],
}


def resolve_source_armature():
    selected = [obj for obj in bpy.context.selected_objects if obj.type == "ARMATURE"]
    if len(selected) != 1:
        raise RuntimeError(f"Select exactly one source armature before running. Got {len(selected)} armatures.")
    report["created"].append(f"Using selected source armature: {selected[0].name}")
    return selected[0]


def unique_name(base):
    if bpy.data.objects.get(base) is None:
        return base
    index = 1
    while bpy.data.objects.get(f"{base}.{index:03d}") is not None:
        index += 1
    return f"{base}.{index:03d}"


def output_name_for_source(source):
    return f"{source.name}{OUTPUT_NAME_SUFFIX}"


def archive_existing_output(output_name):
    obj = bpy.data.objects.get(output_name)
    if obj is None:
        return
    if not BACKUP_EXISTING_OUTPUT:
        bpy.data.objects.remove(obj, do_unlink=True)
        report["deleted"].append(f"Removed existing {output_name}")
        return
    new_name = unique_name(f"{output_name}_old")
    obj.name = new_name
    obj.data.name = new_name
    obj.hide_viewport = True
    obj.hide_render = True
    report["created"].append(f"Archived existing output as hidden {new_name}")


def create_human_metarig(source):
    output_name = output_name_for_source(source)
    archive_existing_output(output_name)
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    before = set(bpy.data.objects)
    bpy.ops.object.armature_human_metarig_add()
    after = set(bpy.data.objects)
    new_objects = [obj for obj in after - before if obj.type == "ARMATURE"]
    obj = bpy.context.object if bpy.context.object and bpy.context.object.type == "ARMATURE" else None
    if obj is None and new_objects:
        obj = new_objects[0]
    if obj is None:
        raise RuntimeError("Rigify human metarig operator did not create an armature")
    obj.name = output_name
    obj.data.name = output_name
    obj.scale = (INITIAL_METARIG_SCALE, INITIAL_METARIG_SCALE, INITIAL_METARIG_SCALE)
    bpy.context.view_layer.update()
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bpy.context.view_layer.update()
    report["created"].append(f"Created {output_name} from Rigify Human metarig")
    report["derived"].append(f"Scaled {output_name} uniformly to {INITIAL_METARIG_SCALE} and applied scale")
    return obj


def src_bone(source, name):
    bone = source.data.bones.get(name)
    if bone is None:
        report["missing_source"].append(name)
    return bone


def src_head(source, name):
    bone = src_bone(source, name)
    if bone is None:
        return None
    return source.matrix_world @ bone.head_local


def src_tail(source, name):
    bone = src_bone(source, name)
    if bone is None:
        return None
    return source.matrix_world @ bone.tail_local


def midpoint(a, b):
    if a is None or b is None:
        return None
    return a.lerp(b, 0.5)


def average(points):
    valid = [p for p in points if p is not None]
    if not valid:
        return None
    total = Vector((0.0, 0.0, 0.0))
    for p in valid:
        total += p
    return total / len(valid)


def normalized_or(vec, fallback):
    if vec is None or vec.length < 1e-8:
        return fallback.normalized()
    return vec.normalized()


def horizontal_direction(vec, fallback=WORLD_NEG_Y):
    if vec is None:
        flat = Vector((fallback.x, fallback.y, 0.0))
        return normalized_or(flat, WORLD_NEG_Y)
    flat = Vector((vec.x, vec.y, 0.0))
    if flat.length < 1e-8:
        fallback_flat = Vector((fallback.x, fallback.y, 0.0))
        return normalized_or(fallback_flat, WORLD_NEG_Y)
    return flat.normalized()


def to_target_local(target, point_world):
    return target.matrix_world.inverted() @ point_world


def safe_tail(head, tail, fallback_dir=WORLD_Z, fallback_len=MIN_BONE_LENGTH):
    if head is None or tail is None:
        return head, tail
    if (tail - head).length >= MIN_BONE_LENGTH:
        return head, tail
    direction = normalized_or(fallback_dir, WORLD_Z)
    return head, head + direction * max(fallback_len, MIN_BONE_LENGTH)


def original_world_bone_points(target):
    points = {}
    mw = target.matrix_world
    for b in target.data.bones:
        head = mw @ b.head_local
        tail = mw @ b.tail_local
        vec = tail - head
        points[b.name] = {
            "head": head,
            "tail": tail,
            "length": max(vec.length, MIN_BONE_LENGTH),
            "direction": normalized_or(vec, WORLD_Z),
        }
    return points


def source_character_height(source):
    points = []
    for bone in source.data.bones:
        points.append(source.matrix_world @ bone.head_local)
        points.append(source.matrix_world @ bone.tail_local)
    if not points:
        return 1.0
    return max(p.z for p in points) - min(p.z for p in points)


def set_edit_bone(edit_bones, target, name, head_world, tail_world, fallback_dir=WORLD_Z):
    eb = edit_bones.get(name)
    if eb is None:
        report["missing_target"].append(name)
        return False
    if head_world is None or tail_world is None:
        report["warnings"].append(f"Skipped {name}: invalid source point")
        return False
    head_world, tail_world = safe_tail(head_world, tail_world, fallback_dir)
    eb.head = to_target_local(target, head_world)
    eb.tail = to_target_local(target, tail_world)
    report["aligned"].append(name)
    return True


def set_edit_bone_by_direction(edit_bones, target, original_points, name, head_world, direction_world=None, length=None):
    original = original_points.get(name, {})
    direction = direction_world if direction_world is not None else original.get("direction", WORLD_Z)
    direction = normalized_or(direction, WORLD_Z)
    bone_len = length if length is not None else original.get("length", MIN_BONE_LENGTH)
    tail_world = head_world + direction * max(bone_len, MIN_BONE_LENGTH) if head_world is not None else None
    return set_edit_bone(edit_bones, target, name, head_world, tail_world, direction)


def align_chain(edit_bones, target, entries):
    for name, head, tail in entries:
        direction = (tail - head) if head is not None and tail is not None else WORLD_Z
        set_edit_bone(edit_bones, target, name, head, tail, direction)


def chain_direction_from_points(points, fallback):
    valid = [p for p in points if p is not None]
    if len(valid) >= 2:
        return normalized_or(valid[-1] - valid[0], fallback)
    return normalized_or(fallback, WORLD_Z)


def delete_face_bones(edit_bones):
    if not REMOVE_FACE:
        return
    roots = [edit_bones.get("face")]
    face_roots = [bone for bone in roots if bone is not None]
    if not face_roots:
        report["warnings"].append("No face root found to remove")
        return
    to_delete = set()

    def collect(bone):
        to_delete.add(bone.name)
        for child in bone.children:
            collect(child)

    for root in face_roots:
        collect(root)

    # Delete leaves first.
    for name in sorted(to_delete, key=lambda n: len(edit_bones[n].children) if edit_bones.get(n) else 0, reverse=True):
        bone = edit_bones.get(name)
        if bone is not None:
            edit_bones.remove(bone)
            report["deleted"].append(name)


def remove_bone_subtree(edit_bones, root_name, reason):
    root = edit_bones.get(root_name)
    if root is None:
        return
    to_delete = []

    def collect(bone):
        for child in bone.children:
            collect(child)
        to_delete.append(bone.name)

    collect(root)
    for name in to_delete:
        bone = edit_bones.get(name)
        if bone is not None:
            edit_bones.remove(bone)
            report["deleted"].append(f"{name} ({reason})")


def delete_missing_optional_fingers(source, edit_bones):
    if not REMOVE_MISSING_OPTIONAL_FINGERS:
        return
    optional = [
        ("L", "ring", "Bip001 L Finger3", "f_ring.01.L", "palm.03.L"),
        ("L", "pinky", "Bip001 L Finger4", "f_pinky.01.L", "palm.04.L"),
        ("R", "ring", "Bip001 R Finger3", "f_ring.01.R", "palm.03.R"),
        ("R", "pinky", "Bip001 R Finger4", "f_pinky.01.R", "palm.04.R"),
    ]
    for side, label, source_root, finger_root, palm_root in optional:
        if source.data.bones.get(source_root) is not None:
            continue
        reason = f"missing source {side} {label} finger"
        remove_bone_subtree(edit_bones, finger_root, reason)
        remove_bone_subtree(edit_bones, palm_root, reason)


def align_spine(source, target, edit_bones, original_points):
    pelvis_h = src_head(source, "Bip001 Pelvis")
    lower_h = src_head(source, "Bip001 Spine")
    chest_h = src_head(source, "Bip001 Spine1")
    neck_h = src_head(source, "Bip001 Neck")
    head_h = src_head(source, "Bip001 Head")
    neck_mid = midpoint(neck_h, head_h)

    height = source_character_height(source)
    micro_len = max(height * SPINE_001_HEIGHT_RATIO, SPINE_001_MIN_LENGTH)
    spine_axis = chain_direction_from_points([lower_h, chest_h], WORLD_Z)
    micro_tail = lower_h + spine_axis * micro_len if lower_h is not None else None

    head_len = HEAD_BONE_LENGTH
    head_tail = head_h + WORLD_Z * head_len if head_h is not None else None

    align_chain(edit_bones, target, [
        ("spine", pelvis_h, lower_h),
        ("spine.001", lower_h, micro_tail),
        ("spine.002", micro_tail, chest_h),
        ("spine.003", chest_h, neck_h),
        ("spine.004", neck_h, neck_mid),
        ("spine.005", neck_mid, head_h),
        ("spine.006", head_h, head_tail),
    ])
    report["derived"].append(f"spine.001 kept as micro transition bone length={micro_len:.5f}")


def align_finger_chain(edit_bones, target, original_points, side, rig_prefix, first_head, second_head, second_tail):
    suffix = ".L" if side == "L" else ".R"
    b1 = f"{rig_prefix}.01{suffix}"
    b2 = f"{rig_prefix}.02{suffix}"
    b3 = f"{rig_prefix}.03{suffix}"

    if first_head is None:
        report["warnings"].append(f"Skipped {b1}/{b2}/{b3}: missing first finger head")
        return

    fallback_dir = original_points.get(b1, {}).get("direction", WORLD_Z)
    axis = chain_direction_from_points([first_head, second_head], fallback_dir)

    len1 = original_points.get(b1, {}).get("length", MIN_BONE_LENGTH)
    len2 = original_points.get(b2, {}).get("length", MIN_BONE_LENGTH)
    len3 = original_points.get(b3, {}).get("length", MIN_BONE_LENGTH)

    h1 = first_head
    h2 = second_head if second_head is not None else h1 + axis * len1
    if second_tail is not None and second_head is not None:
        len2 = max((second_tail - second_head).length, len2)
    h3 = h2 + axis * len2

    set_edit_bone(edit_bones, target, b1, h1, h2, axis)
    set_edit_bone(edit_bones, target, b2, h2, h3, axis)
    set_edit_bone(edit_bones, target, b3, h3, h3 + axis * len3, axis)
    report["derived"].append(f"{b1}/{b2}/{b3} use joint axis, not source short-bone tail")


def align_toe(edit_bones, target, original_points, side, toe_head, foot_head):
    suffix = ".L" if side == "L" else ".R"
    name = f"toe{suffix}"
    fallback_dir = original_points.get(name, {}).get("direction", WORLD_NEG_Y)
    axis = horizontal_direction((toe_head - foot_head) if toe_head is not None and foot_head is not None else None, fallback_dir)
    length = original_points.get(name, {}).get("length", 0.026)
    set_edit_bone(edit_bones, target, name, toe_head, toe_head + axis * length, axis)
    report["derived"].append(f"{name} derived from horizontal foot-to-toe axis")


def derive_heel(source, target, edit_bones, side, foot_name, toe_name):
    suffix = ".L" if side == "L" else ".R"
    name = f"heel.02{suffix}"
    eb = edit_bones.get(name)
    if eb is None:
        report["missing_target"].append(name)
        return

    foot_head = src_head(source, foot_name)
    toe_head = src_head(source, toe_name)
    toe_tail = src_tail(source, toe_name)
    if foot_head is None or toe_head is None:
        report["warnings"].append(f"Skipped {name}: missing foot/toe source")
        return

    foot_dir = horizontal_direction(toe_head - foot_head, WORLD_NEG_Y)
    center = foot_head - foot_dir * 0.035
    center.z = min([p.z for p in [foot_head, toe_head, toe_tail] if p is not None])

    half_len = max(eb.length, 0.02) * 0.5
    side_dir = WORLD_X if side == "L" else -WORLD_X
    head = center - side_dir * half_len
    tail = center + side_dir * half_len
    set_edit_bone(edit_bones, target, name, head, tail, side_dir)
    report["derived"].append(f"{name} derived from foot/toe contact")


def align_side(source, target, edit_bones, original_points, side):
    src_side = "L" if side == "L" else "R"
    suffix = ".L" if side == "L" else ".R"

    clav = f"Bip001 {src_side} Clavicle"
    upper = f"Bip001 {src_side} UpperArm"
    fore = f"Bip001 {src_side} Forearm"
    hand = f"Bip001 {src_side} Hand"
    finger1 = f"Bip001 {src_side} Finger1"
    finger2 = f"Bip001 {src_side} Finger2"
    finger3 = f"Bip001 {src_side} Finger3"

    hand_tail = average([
        src_head(source, finger1),
        src_head(source, finger2),
        src_head(source, finger3),
    ])

    align_chain(edit_bones, target, [
        (f"shoulder{suffix}", src_head(source, clav), src_head(source, upper)),
        (f"upper_arm{suffix}", src_head(source, upper), src_head(source, fore)),
        (f"forearm{suffix}", src_head(source, fore), src_head(source, hand)),
        (f"hand{suffix}", src_head(source, hand), hand_tail),
    ])

    thigh = f"Bip001 {src_side} Thigh"
    calf = f"Bip001 {src_side} Calf"
    foot = f"Bip001 {src_side} Foot"
    toe = f"Bip001 {src_side} Toe0"

    align_chain(edit_bones, target, [
        (f"thigh{suffix}", src_head(source, thigh), src_head(source, calf)),
        (f"shin{suffix}", src_head(source, calf), src_head(source, foot)),
        (f"foot{suffix}", src_head(source, foot), src_head(source, toe)),
    ])
    align_toe(edit_bones, target, original_points, side, src_head(source, toe), src_head(source, foot))
    derive_heel(source, target, edit_bones, side, foot, toe)

    pelvis_head = src_head(source, "Bip001 Pelvis")
    thigh_head = src_head(source, thigh)
    set_edit_bone(edit_bones, target, f"pelvis{suffix}", pelvis_head, thigh_head, WORLD_Z)

    hand_head = src_head(source, hand)
    palm_sources = {
        "palm.01": src_head(source, finger1),
        "palm.02": src_head(source, finger2),
        "palm.03": src_head(source, finger3),
        "palm.04": src_head(source, f"Bip001 {src_side} Finger4"),
    }
    old_hand_head = original_points.get(f"hand{suffix}", {}).get("head")
    for palm_name, finger_root in palm_sources.items():
        name = f"{palm_name}{suffix}"
        if edit_bones.get(name) is None:
            continue
        old_head = original_points.get(name, {}).get("head")
        offset = (old_head - old_hand_head) if old_head is not None and old_hand_head is not None else Vector((0.0, 0.0, 0.0))
        if hand_head is not None and finger_root is not None:
            head = (hand_head + offset).lerp(finger_root, 0.35)
        else:
            head = finger_root or hand_head
        set_edit_bone_by_direction(edit_bones, target, original_points, name, head)
        report["derived"].append(f"{name} keeps metarig palm direction")

    finger_specs = {
        "thumb": ("thumb", "Finger0", "Finger01"),
        "index": ("f_index", "Finger1", "Finger11"),
        "middle": ("f_middle", "Finger2", "Finger21"),
        "ring": ("f_ring", "Finger3", "Finger31"),
        "pinky": ("f_pinky", "Finger4", "Finger41"),
    }
    for label, (rig_prefix, src_first_short, src_second_short) in finger_specs.items():
        first = f"Bip001 {src_side} {src_first_short}"
        second = f"Bip001 {src_side} {src_second_short}"
        if edit_bones.get(f"{rig_prefix}.01{suffix}") is None:
            continue
        align_finger_chain(
            edit_bones,
            target,
            original_points,
            side,
            rig_prefix,
            src_head(source, first),
            src_head(source, second),
            src_tail(source, second),
        )


def align_breast_optional(source, target, edit_bones, original_points):
    optional = [
        ("breast.L", "Bone_Breast_L_01"),
        ("breast.R", "Bone_Breast_R_01"),
    ]
    for target_name, source_name in optional:
        if source.data.bones.get(source_name):
            set_edit_bone_by_direction(
                edit_bones,
                target,
                original_points,
                target_name,
                src_head(source, source_name),
            )
            report["derived"].append(f"{target_name} keeps metarig breast direction")
        else:
            report["warnings"].append(f"Optional source missing: {source_name}")


def align_metarig(source, target):
    original_points = original_world_bone_points(target)
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    target.select_set(True)
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.mode_set(mode="EDIT")

    edit_bones = target.data.edit_bones
    delete_face_bones(edit_bones)
    delete_missing_optional_fingers(source, edit_bones)
    align_spine(source, target, edit_bones, original_points)
    align_breast_optional(source, target, edit_bones, original_points)
    align_side(source, target, edit_bones, original_points, "L")
    align_side(source, target, edit_bones, original_points, "R")

    bpy.ops.object.mode_set(mode="OBJECT")


def dedupe_report():
    for key in ("created", "deleted", "aligned", "derived", "missing_source", "missing_target", "warnings"):
        seen = set()
        unique = []
        for item in report[key]:
            if item not in seen:
                unique.append(item)
                seen.add(item)
        report[key] = unique


def print_report():
    dedupe_report()
    print("\n=== Create and align Human metarig report ===")
    for key in ("created", "deleted", "aligned", "derived", "missing_source", "missing_target", "warnings"):
        values = report[key]
        print(f"{key}: {len(values)}")
        if key != "aligned":
            for value in values:
                print(f"  - {value}")
    print("=== End report ===\n")


def main():
    source = resolve_source_armature()
    target = create_human_metarig(source)
    align_metarig(source, target)
    print_report()
    return report


main()
