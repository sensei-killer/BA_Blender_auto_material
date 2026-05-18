import bpy
import importlib.util
from pathlib import Path
from mathutils import Matrix

def load_ba_shader_controls_module():
    try:
        from . import ba_shader_controls
        return ba_shader_controls, None
    except Exception as package_error:
        module_path = Path(__file__).resolve().parent / "ba_shader_controls.py"
        try:
            spec = importlib.util.spec_from_file_location("ba_shader_controls", module_path)
            if spec is None or spec.loader is None:
                return None, f"Could not create import spec for {module_path}"
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module, None
        except Exception as file_error:
            return None, f"package import failed: {package_error}; file import failed: {file_error}"


ba_shader_controls, BA_SHADER_CONTROLS_LOAD_ERROR = load_ba_shader_controls_module()

# Migrate the selected body mesh from the selected original armature to the
# selected generated Rigify armature.
#
# Policy:
# - Body/control weights are renamed or merged into target DEF-* groups on the
#   inferred body mesh only.
# - Other selected meshes, such as weapons or props, keep their vertex groups
#   unchanged and only have parents/Armature modifiers retargeted.
# - Hair, skirt, face, weapon, prop, sleeves, pouches, and other extra weights
#   keep their original vertex group names.
# - Extra old bones are copied into the target rig with the same names, so those
#   unchanged vertex groups still have deform bones to bind to.
# - Extra bones whose old parent was Bip001 are parented to the target rig's root.
# - Copied extra bones are organized into Face, Hair, Skirt, and Other bone
#   collections by name.
# - Body bones are not copied; Rigify owns those via its generated DEF bones.

REMOVE_OLD_ARMATURE_MODIFIERS = False
PARENT_BODY_TO_TARGET_ARMATURE = True
NORMALIZE_AFTER_MIGRATION = False
CREATE_BACKUP_VERTEX_GROUPS = False
BODY_MESH_SCORE_TIE_MARGIN = 0

BODY_BONE_TO_DEF = {
    "Bip001 Pelvis": "DEF-spine",
    "Bip001 Spine": "DEF-spine.002",
    "Bip001 Spine1": "DEF-spine.003",
    "Bip001 Neck": "DEF-spine.005",
    "Bip001 Head": "DEF-spine.006",

    "Bip001 L Clavicle": "DEF-shoulder.L",
    "Bip001 L UpperArm": "DEF-upper_arm.L",
    "Bip001 L Forearm": "DEF-forearm.L",
    "Bip001 L Hand": "DEF-hand.L",
    "Bip001 R Clavicle": "DEF-shoulder.R",
    "Bip001 R UpperArm": "DEF-upper_arm.R",
    "Bip001 R Forearm": "DEF-forearm.R",
    "Bip001 R Hand": "DEF-hand.R",

    "Bip001 L Thigh": "DEF-thigh.L",
    "Bip001 L Calf": "DEF-shin.L",
    "Bip001 L Foot": "DEF-foot.L",
    "Bip001 L Toe0": "DEF-toe.L",
    "Bip001 R Thigh": "DEF-thigh.R",
    "Bip001 R Calf": "DEF-shin.R",
    "Bip001 R Foot": "DEF-foot.R",
    "Bip001 R Toe0": "DEF-toe.R",

    "Bip001 L Finger0": "DEF-thumb.01.L",
    "Bip001 L Finger01": "DEF-thumb.02.L",
    "Bip001 L Finger1": "DEF-f_index.01.L",
    "Bip001 L Finger11": "DEF-f_index.02.L",
    "Bip001 L Finger2": "DEF-f_middle.01.L",
    "Bip001 L Finger21": "DEF-f_middle.02.L",
    "Bip001 L Finger3": "DEF-f_ring.01.L",
    "Bip001 L Finger31": "DEF-f_ring.02.L",
    "Bip001 L Finger4": "DEF-f_pinky.01.L",
    "Bip001 L Finger41": "DEF-f_pinky.02.L",

    "Bip001 R Finger0": "DEF-thumb.01.R",
    "Bip001 R Finger01": "DEF-thumb.02.R",
    "Bip001 R Finger1": "DEF-f_index.01.R",
    "Bip001 R Finger11": "DEF-f_index.02.R",
    "Bip001 R Finger2": "DEF-f_middle.01.R",
    "Bip001 R Finger21": "DEF-f_middle.02.R",
    "Bip001 R Finger3": "DEF-f_ring.01.R",
    "Bip001 R Finger31": "DEF-f_ring.02.R",
    "Bip001 R Finger4": "DEF-f_pinky.01.R",
    "Bip001 R Finger41": "DEF-f_pinky.02.R",

    "Bone_Breast_L_01": "DEF-breast.L",
    "Bone_Breast_R_01": "DEF-breast.R",
}

BODY_HELPER_TO_BODY = {
    "Bip001_B_L UpperArm Twist": "Bip001 L UpperArm",
    "Bip001_B_R UpperArm Twist": "Bip001 R UpperArm",
    "Bone L ForeArm Twist": "Bip001 L Forearm",
    "Bone R ForeArm Twist": "Bip001 R Forearm",
    "Bip001_B_L Deltoid": "Bip001 L UpperArm",
    "Bip001_B_R Deltoid": "Bip001 R UpperArm",
    "Bip001_B_L Thigh Twist": "Bip001 L Thigh",
    "Bip001_B_R Thigh Twist": "Bip001 R Thigh",
    "Bip001_B_L Hip": "Bip001 L Thigh",
    "Bip001_B_R Hip": "Bip001 R Thigh",
    "bone_KneeL": "Bip001 L Calf",
    "bone_KneeR": "Bip001 R Calf",
}

report = {
    "copied_extra_bones": [],
    "skipped_body_bones": [],
    "renamed_groups": [],
    "merged_groups": [],
    "kept_groups": [],
    "deleted_groups": [],
    "missing_target_bones": [],
    "missing_source_bones": [],
    "modifiers": [],
    "parenting": [],
    "skipped_unbound_meshes": [],
    "warnings": [],
}


def has_source_armature_modifier(mesh, source):
    return any(mod.type == "ARMATURE" and mod.object == source for mod in mesh.modifiers)


def has_any_armature_modifier_from(mesh, armatures):
    return any(mod.type == "ARMATURE" and mod.object in armatures for mod in mesh.modifiers)


def body_mesh_score(mesh):
    group_names = {group.name for group in mesh.vertex_groups}
    body_groups = set(BODY_BONE_TO_DEF) | set(BODY_HELPER_TO_BODY)
    score = len(group_names & body_groups)
    if "Bip001" in group_names:
        score += 1
    return score


def choose_body_mesh(meshes):
    body_candidates = sorted(
        ((body_mesh_score(mesh), mesh.name, mesh) for mesh in meshes),
        key=lambda item: (-item[0], item[1]),
    )
    best_score, _, body_mesh = body_candidates[0]
    if best_score <= 0:
        return None

    tied = [
        mesh.name
        for score, _, mesh in body_candidates[1:]
        if best_score - score <= BODY_MESH_SCORE_TIE_MARGIN and score > 0
    ]
    if tied:
        raise RuntimeError(
            "Could not choose one body mesh confidently from selected meshes. "
            f"Best candidate {body_mesh.name} scored {best_score}; close candidates: {tied}. "
            "Select only one body mesh plus optional bound extras/unbound props."
        )
    return body_mesh


def resolve_scene_objects():
    selected = list(bpy.context.selected_objects)
    meshes = [obj for obj in selected if obj.type == "MESH"]
    armatures = [obj for obj in selected if obj.type == "ARMATURE"]

    if len(meshes) < 1 or len(armatures) != 2:
        raise RuntimeError(
            "Select 2 armatures and at least 1 mesh before running: source old armature, target Rigify rig, "
            "and one or more meshes. The mesh with the old Armature modifier/parent is treated as the body mesh. "
            f"Got {len(armatures)} armatures and {len(meshes)} meshes."
        )

    source = None
    target = None
    body_mesh = None

    for mesh in meshes:
        for modifier in mesh.modifiers:
            if modifier.type == "ARMATURE" and modifier.object in armatures:
                source = modifier.object
                break
        if source is not None:
            break

    if source is None:
        for mesh in meshes:
            if mesh.parent in armatures:
                source = mesh.parent
                body_mesh = mesh
                break

    for armature in armatures:
        if armature != source:
            target = armature
            break

    if source is None or target is None:
        # Fallback heuristic: generated Rigify rigs usually have DEF bones.
        with_def = [arm for arm in armatures if any(b.name.startswith("DEF-") for b in arm.data.bones)]
        if len(with_def) == 1:
            target = with_def[0]
            source = next(arm for arm in armatures if arm != target)

    if source is not None:
        bound_meshes = [
            mesh
            for mesh in meshes
            if has_source_armature_modifier(mesh, source) or mesh.parent == source
        ]
        body_mesh = choose_body_mesh(bound_meshes) or choose_body_mesh(meshes)

    if source is None or target is None or body_mesh is None:
        raise RuntimeError(
            "Could not infer source and target armatures from selection. "
            "Select the body mesh with BA body vertex groups, plus old source armature, new Rigify rig, "
            "and optional bound extras/unbound props."
        )

    modifier_extra_meshes = [
        mesh
        for mesh in meshes
        if mesh != body_mesh and has_source_armature_modifier(mesh, source)
    ]
    parented_extra_meshes = [
        mesh
        for mesh in meshes
        if mesh != body_mesh and mesh not in modifier_extra_meshes and mesh.parent == source
    ]
    unbound_meshes = [
        mesh
        for mesh in meshes
        if mesh != body_mesh
        and mesh not in modifier_extra_meshes
        and mesh not in parented_extra_meshes
        and not has_any_armature_modifier_from(mesh, armatures)
    ]
    extra_meshes = modifier_extra_meshes + parented_extra_meshes
    for mesh in unbound_meshes:
        report["skipped_unbound_meshes"].append(mesh.name)

    report["warnings"].append(
        f"Using selection: source={source.name}, target={target.name}, body_mesh={body_mesh.name}, "
        f"modifier_extra_meshes={[mesh.name for mesh in modifier_extra_meshes]}, "
        f"parented_extra_meshes={[mesh.name for mesh in parented_extra_meshes]}, "
        f"unbound_meshes={[mesh.name for mesh in unbound_meshes]}"
    )
    return source, target, body_mesh, modifier_extra_meshes, parented_extra_meshes, unbound_meshes


def target_def_bones(target):
    return {bone.name for bone in target.data.bones if bone.name.startswith("DEF-")}


def build_body_mapping():
    mapping = dict(BODY_BONE_TO_DEF)
    for helper, body in BODY_HELPER_TO_BODY.items():
        target = BODY_BONE_TO_DEF.get(body)
        if target:
            mapping[helper] = target
    return mapping


def is_body_bone_name(name):
    return name in BODY_BONE_TO_DEF or name in BODY_HELPER_TO_BODY or name == "Bip001"


def source_to_target_parent_name(source_bone_name, old_to_new_body):
    if source_bone_name is None:
        return None
    if source_bone_name == "Bip001":
        return "root"
    mapped = old_to_new_body.get(source_bone_name)
    if mapped:
        return mapped
    return source_bone_name


def source_bone_to_target_bone_name(source_bone_name, old_to_new_body, target):
    if not source_bone_name:
        return None
    if source_bone_name == "Bip001":
        return "root"
    mapped = old_to_new_body.get(source_bone_name)
    if mapped and target.data.bones.get(mapped):
        return mapped
    if target.data.bones.get(source_bone_name):
        return source_bone_name
    return "root"


def get_or_create_bone_collection(armature_data, name):
    collection = armature_data.collections.get(name)
    if collection is None:
        collection = armature_data.collections.new(name)
    return collection


def classify_extra_bone_collection(bone_name):
    lowered = bone_name.lower()
    if any(token in lowered for token in ("eye", "eyebrow", "eyeblow", "mouth")):
        return "Face"
    if "hair" in lowered:
        return "Hair"
    if "skirt" in lowered:
        return "Skirt"
    return "Other"


def assign_copied_extra_bones_to_collections(target, copied_bone_names):
    if not hasattr(target.data, "collections"):
        report["warnings"].append("Target armature has no bone collections API; skipped extra bone collection assignment")
        return
    collections = {
        name: get_or_create_bone_collection(target.data, name)
        for name in ("Face", "Hair", "Skirt", "Other")
    }
    for bone_name in copied_bone_names:
        bone = target.data.bones.get(bone_name)
        if bone is None:
            continue
        collection_name = classify_extra_bone_collection(bone_name)
        collections[collection_name].assign(bone)
        report["parenting"].append(f"{bone_name} assigned to bone collection {collection_name}")


def copy_extra_bones_to_target(source, target, old_to_new_body):
    old_active = bpy.context.view_layer.objects.active
    old_mode = old_active.mode if old_active else "OBJECT"

    # Bone roll is only available from EditBone, not from Armature.data.bones.
    source_specs = {}
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    source.select_set(True)
    bpy.context.view_layer.objects.active = source
    bpy.ops.object.mode_set(mode="EDIT")
    for src_edit_bone in source.data.edit_bones:
        source_specs[src_edit_bone.name] = {
            "head": src_edit_bone.head.copy(),
            "tail": src_edit_bone.tail.copy(),
            "roll": src_edit_bone.roll,
            "use_deform": src_edit_bone.use_deform,
            "inherit_scale": src_edit_bone.inherit_scale,
            "parent": src_edit_bone.parent.name if src_edit_bone.parent else None,
        }
    bpy.ops.object.mode_set(mode="OBJECT")

    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    target.select_set(True)
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.mode_set(mode="EDIT")

    edit_bones = target.data.edit_bones
    source_world_to_target_local = target.matrix_world.inverted() @ source.matrix_world

    for source_name, spec in source_specs.items():
        if is_body_bone_name(source_name):
            report["skipped_body_bones"].append(source_name)
            continue
        if edit_bones.get(source_name):
            report["warnings"].append(f"Target already has extra bone {source_name}; skipped copy")
            continue

        eb = edit_bones.new(source_name)
        eb.head = source_world_to_target_local @ spec["head"]
        eb.tail = source_world_to_target_local @ spec["tail"]
        eb.roll = spec["roll"]
        eb.use_deform = spec["use_deform"]
        eb.inherit_scale = spec["inherit_scale"]
        eb.use_connect = False
        report["copied_extra_bones"].append(source_name)

    # Parent after all extra bones exist.
    for source_name, spec in source_specs.items():
        if is_body_bone_name(source_name):
            continue
        eb = edit_bones.get(source_name)
        if eb is None:
            continue
        old_parent_name = spec["parent"]
        parent_name = source_to_target_parent_name(old_parent_name, old_to_new_body)
        parent = edit_bones.get(parent_name) if parent_name else None
        if parent:
            eb.parent = parent
            eb.use_connect = False
        elif parent_name:
            report["warnings"].append(f"Could not find parent {parent_name} for copied bone {source_name}; left unparented")

    bpy.ops.object.mode_set(mode="OBJECT")
    assign_copied_extra_bones_to_collections(target, report["copied_extra_bones"])
    if old_active:
        bpy.context.view_layer.objects.active = old_active
        old_active.select_set(True)
        if old_mode != "OBJECT":
            try:
                bpy.ops.object.mode_set(mode=old_mode)
            except Exception:
                report["warnings"].append(f"Could not restore previous mode {old_mode}")


def read_vertex_group_weights(mesh, group_index):
    weights = {}
    for vertex in mesh.data.vertices:
        for membership in vertex.groups:
            if membership.group == group_index:
                weights[vertex.index] = membership.weight
                break
    return weights


def ensure_vertex_group(mesh, name):
    group = mesh.vertex_groups.get(name)
    if group is None:
        group = mesh.vertex_groups.new(name=name)
    return group


def add_weights(mesh, group_name, weights):
    if not weights:
        return
    group = ensure_vertex_group(mesh, group_name)
    for vertex_index, weight in weights.items():
        group.add([vertex_index], weight, "ADD")


def backup_vertex_groups(mesh):
    if not CREATE_BACKUP_VERTEX_GROUPS:
        return
    for group in list(mesh.vertex_groups):
        backup_name = f"OLD_{group.name}"
        if mesh.vertex_groups.get(backup_name):
            continue
        weights = read_vertex_group_weights(mesh, group.index)
        backup = mesh.vertex_groups.new(name=backup_name)
        for vertex_index, weight in weights.items():
            backup.add([vertex_index], weight, "REPLACE")


def migrate_vertex_groups(mesh, old_to_new_body, valid_target_bones):
    backup_vertex_groups(mesh)

    group_names_to_remove = []
    for group in list(mesh.vertex_groups):
        old_name = group.name
        new_name = old_to_new_body.get(old_name)
        if not new_name:
            report["kept_groups"].append(old_name)
            continue
        if new_name not in valid_target_bones:
            report["missing_target_bones"].append(new_name)
            report["kept_groups"].append(old_name)
            continue

        weights = read_vertex_group_weights(mesh, group.index)
        add_weights(mesh, new_name, weights)
        group_names_to_remove.append(old_name)
        if mesh.vertex_groups.get(new_name) and old_name != new_name:
            report["merged_groups"].append(f"{old_name} -> {new_name}")
        else:
            report["renamed_groups"].append(f"{old_name} -> {new_name}")

    for group_name in group_names_to_remove:
        group = mesh.vertex_groups.get(group_name)
        if group is not None:
            mesh.vertex_groups.remove(group)
            report["deleted_groups"].append(group_name)


def normalize_deform_weights(mesh):
    if not NORMALIZE_AFTER_MIGRATION:
        return
    old_active = bpy.context.view_layer.objects.active
    old_mode = old_active.mode if old_active else "OBJECT"
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = mesh
    try:
        bpy.ops.object.vertex_group_normalize_all(lock_active=False)
        report["modifiers"].append("Normalized all vertex groups")
    except Exception as exc:
        report["warnings"].append(f"Could not normalize vertex groups: {exc}")
    if old_active:
        bpy.context.view_layer.objects.active = old_active
        old_active.select_set(True)
        if old_mode != "OBJECT":
            try:
                bpy.ops.object.mode_set(mode=old_mode)
            except Exception:
                report["warnings"].append(f"Could not restore previous mode {old_mode}")


def reparent_source_children(source, target, processed_meshes, old_to_new_body):
    processed_meshes = set(processed_meshes)
    for obj in bpy.data.objects:
        if obj in processed_meshes:
            continue
        if obj.parent != source:
            continue

        world = obj.matrix_world.copy()
        if obj.parent_type == "BONE":
            old_parent_bone = obj.parent_bone
            target_bone = source_bone_to_target_bone_name(obj.parent_bone, old_to_new_body, target)
            obj.parent = target
            obj.parent_type = "BONE"
            obj.parent_bone = target_bone
            obj.matrix_parent_inverse = Matrix.Identity(4)
            obj.matrix_world = world
            report["parenting"].append(f"{obj.name} bone-parent moved {source.name}:{old_parent_bone} -> {target.name}:{target_bone}")
        else:
            obj.parent = target
            obj.parent_type = "OBJECT"
            obj.matrix_parent_inverse = target.matrix_world.inverted()
            obj.matrix_world = world
            report["parenting"].append(f"{obj.name} object-parent moved {source.name} -> {target.name}")


def retarget_mesh_to_target(mesh, source, target):
    world = mesh.matrix_world.copy()

    if REMOVE_OLD_ARMATURE_MODIFIERS:
        for modifier in list(mesh.modifiers):
            if modifier.type == "ARMATURE" and modifier.object == source:
                mesh.modifiers.remove(modifier)
                report["modifiers"].append(f"Removed old armature modifier {modifier.name}")

    modifier = None
    for mod in mesh.modifiers:
        if mod.type == "ARMATURE" and mod.object == source:
            modifier = mod
            break
    if modifier is None:
        modifier = mesh.modifiers.new(name=target.name, type="ARMATURE")
    modifier.name = target.name
    modifier.object = target
    report["modifiers"].append(f"Armature modifier now targets {target.name}")

    if PARENT_BODY_TO_TARGET_ARMATURE:
        mesh.parent = target
        mesh.parent_type = "OBJECT"
        mesh.matrix_parent_inverse = target.matrix_world.inverted()
        mesh.matrix_world = world
        report["parenting"].append(f"{mesh.name} parented to {target.name} with world transform preserved")
    else:
        mesh.parent = None
        mesh.matrix_world = world
        report["parenting"].append(f"{mesh.name} parent cleared with world transform preserved")


def retarget_shader_control_empties(context, target, meshes):
    if ba_shader_controls is None:
        report["warnings"].append(
            "ba_shader_controls module unavailable; skipped shader control retarget"
            f" ({BA_SHADER_CONTROLS_LOAD_ERROR})"
        )
        return

    old_active = bpy.context.view_layer.objects.active
    old_selected = list(bpy.context.selected_objects)
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    for mesh in meshes:
        mesh.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0] if meshes else target

    hair_empty, face_empty = ba_shader_controls.retarget_shader_controls_to_rig(context, target)
    if hair_empty:
        report["parenting"].append(f"{hair_empty.name} retargeted to {target.name}")
    if face_empty:
        report["parenting"].append(f"{face_empty.name} retargeted to {target.name}")

    bpy.ops.object.select_all(action="DESELECT")
    for obj in old_selected:
        if obj.name in bpy.data.objects:
            obj.select_set(True)
    if old_active and old_active.name in bpy.data.objects:
        bpy.context.view_layer.objects.active = old_active


def dedupe_report():
    for key, values in report.items():
        seen = set()
        unique = []
        for value in values:
            if value not in seen:
                unique.append(value)
                seen.add(value)
        report[key] = unique


def print_report():
    dedupe_report()
    print("\n=== Migrate selected body to selected Rigify rig report ===")
    for key in (
        "copied_extra_bones",
        "skipped_body_bones",
        "merged_groups",
        "kept_groups",
        "deleted_groups",
        "missing_target_bones",
        "missing_source_bones",
        "modifiers",
        "parenting",
        "skipped_unbound_meshes",
        "warnings",
    ):
        values = report[key]
        print(f"{key}: {len(values)}")
        if key not in {"kept_groups", "skipped_body_bones"}:
            for value in values:
                print(f"  - {value}")
    print("=== End report ===\n")


def main():
    source, target, mesh, modifier_extra_meshes, parented_extra_meshes, unbound_meshes = resolve_scene_objects()
    extra_meshes = modifier_extra_meshes + parented_extra_meshes

    old_to_new_body = build_body_mapping()
    valid_target_bones = {bone.name for bone in target.data.bones}
    valid_def_bones = target_def_bones(target)

    for old_name, new_name in old_to_new_body.items():
        if source.data.bones.get(old_name) is None:
            report["missing_source_bones"].append(old_name)
        if new_name not in valid_def_bones:
            report["missing_target_bones"].append(new_name)

    copy_extra_bones_to_target(source, target, old_to_new_body)
    valid_target_bones = {bone.name for bone in target.data.bones}
    migrate_vertex_groups(mesh, old_to_new_body, valid_target_bones)
    normalize_deform_weights(mesh)
    retarget_mesh_to_target(mesh, source, target)
    for extra_mesh in modifier_extra_meshes:
        retarget_mesh_to_target(extra_mesh, source, target)
    retarget_shader_control_empties(bpy.context, target, [mesh] + extra_meshes)
    reparent_source_children(source, target, [mesh] + extra_meshes, old_to_new_body)

    print_report()
    return report


main()
