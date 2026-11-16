import bpy
from pathlib import Path

if __package__:
    from . import create_and_align_human_metarig as create_script
    from . import migrate_body_to_rig_auto as migrate_script
    from .ba_rigify_state import ConversionState, ConversionRecoveryError
else:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import create_and_align_human_metarig as create_script
    import migrate_body_to_rig_auto as migrate_script
    from ba_rigify_state import ConversionState, ConversionRecoveryError

# One-click pipeline:
# 1. Select one source/original armature and one or more meshes.
# 2. Run this script.
# 3. It creates/aligns a Rigify Human metarig, generates the Rigify rig, and
#    migrates selected meshes from the source armature to the generated rig.
#
# This script reuses the workspace scripts:
# - create_and_align_human_metarig.py
# - migrate_body_to_rig_auto.py

GENERATED_RIG_SUFFIX = "_rigify_auto"
IGNORED_RIG_NAME_TOKENS = ("mouthre",)


def is_ignored_rig(obj):
    if obj is None or obj.type != "ARMATURE":
        return False
    lowered = obj.name.lower()
    return any(token in lowered for token in IGNORED_RIG_NAME_TOKENS)


def require_selection():
    selected = list(bpy.context.selected_objects)
    armatures = [obj for obj in selected if obj.type == "ARMATURE" and not is_ignored_rig(obj)]
    meshes = [obj for obj in selected if obj.type == "MESH"]
    if len(armatures) != 1 or len(meshes) < 1:
        raise RuntimeError(
            "Select exactly one source armature and at least one mesh before running. "
            f"Got {len(armatures)} armatures and {len(meshes)} meshes."
        )
    return armatures[0], meshes


def select_only(objects, active=None):
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = active or (objects[0] if objects else None)


def create_and_align_metarig(source, ground_meshes=None):
    return create_script.main(source, ground_meshes)


def generate_rigify_rig(metarig, source):
    before = set(bpy.data.objects)
    rig_basename = f"{source.name}{GENERATED_RIG_SUFFIX}"
    metarig.data.rigify_rig_basename = rig_basename

    select_only([metarig], active=metarig)
    bpy.ops.object.mode_set(mode="POSE")
    bpy.ops.pose.rigify_generate()
    bpy.ops.object.mode_set(mode="OBJECT")
    after = set(bpy.data.objects)

    new_armatures = [obj for obj in after - before if obj.type == "ARMATURE"]
    if len(new_armatures) == 1:
        rig = new_armatures[0]
    else:
        rig = bpy.data.objects.get(rig_basename)
        if rig is None:
            rig = bpy.data.objects.get("rig")
        if rig is None:
            rig_candidates = [obj for obj in new_armatures if any(b.name.startswith("DEF-") for b in obj.data.bones)]
            rig = rig_candidates[0] if rig_candidates else None
    if rig is None:
        raise RuntimeError("Rigify generate completed but generated rig could not be found")

    rig.name = rig_basename
    rig.data.name = rig_basename
    # Rigify creates a fresh rig at identity while keeping metarig-local bones.
    rig.matrix_world = metarig.matrix_world.copy()
    bpy.context.view_layer.update()
    return rig


def migrate_meshes(source, generated_rig, meshes):
    select_only([source, generated_rig] + meshes, active=meshes[0])
    return migrate_script.main(source, generated_rig, meshes)


def hide_setup_armatures(source, metarig):
    for obj in (source, metarig):
        obj.hide_set(True)
        obj.hide_viewport = True
        obj.hide_render = True


def preflight(source, meshes):
    for name in ('Bip001 Pelvis', 'Bip001 Spine', 'Bip001 Spine1', 'Bip001 Neck', 'Bip001 Head'):
        if source.data.bones.get(name) is None:
            raise RuntimeError(f'Source rig is missing required bone: {name}')
    for side in ('L', 'R'):
        for name in ('Clavicle', 'UpperArm', 'Forearm', 'Hand', 'Thigh', 'Calf', 'Foot', 'Finger0', 'Finger01', 'Finger1', 'Finger11', 'Finger2', 'Finger21'):
            bone = f'Bip001 {side} {name}'
            if source.data.bones.get(bone) is None:
                raise RuntimeError(f'Source rig is missing required bone: {bone}')
    if source.library or source.data.library or any(m.library or m.data.library for m in meshes):
        raise RuntimeError('Rigify conversion requires editable local objects and mesh data')
    if bpy.data.objects.get(source.name + GENERATED_RIG_SUFFIX):
        raise RuntimeError('A generated rig already exists for this source; use the existing rig or restore the original scene first')
    for mesh in meshes:
        other_rigs = [mod.object for mod in mesh.modifiers if mod.type == 'ARMATURE' and mod.object and mod.object != source and not is_ignored_rig(mod.object)]
        if mesh.parent and mesh.parent.type == 'ARMATURE' and mesh.parent != source and not is_ignored_rig(mesh.parent):
            other_rigs.append(mesh.parent)
        if other_rigs:
            raise RuntimeError(f'{mesh.name} is bound to another armature; select only meshes for {source.name}')
    if abs(source.matrix_world.determinant()) < 1e-10:
        raise RuntimeError('Source rig has a non-invertible transform')
    if not migrate_script.find_body_meshes(meshes):
        raise RuntimeError('Selection has no recognizable body vertex groups')
    try:
        bpy.ops.object.armature_human_metarig_add.get_rna_type()
        bpy.ops.pose.rigify_generate.get_rna_type()
    except (AttributeError, RuntimeError) as exc:
        raise RuntimeError('Enable the Rigify add-on before converting') from exc


def main():
    source, meshes = require_selection()
    bpy.context.view_layer.update()
    preflight(source, meshes)
    body_meshes = migrate_script.find_body_meshes_for_source(source, meshes)
    state = ConversionState(bpy.context, source, meshes, body_meshes)
    try:
        state.begin()
        result = run_pipeline(source, meshes, body_meshes)
    except Exception as exc:
        try:
            errors = state.rollback()
        except Exception as recovery_exc:
            errors = [str(recovery_exc)]
        detail = '; recovery incomplete, generated data retained: ' + '; '.join(errors) if errors else '; original data restored'
        error_type = ConversionRecoveryError if errors else RuntimeError
        raise error_type(f'Rigify conversion failed: {exc}{detail}') from exc
    try:
        state.release_new_data()
    except Exception as exc:
        raise ConversionRecoveryError(f'Rigify conversion completed but cleanup failed: {exc}') from exc
    return result


def run_pipeline(source, meshes, ground_meshes=None):
    print("\n=== Auto Rigify bind pipeline ===")
    print(f"Source armature: {source.name}")
    print(f"Meshes: {[mesh.name for mesh in meshes]}")

    metarig = create_and_align_metarig(source, ground_meshes)
    print(f"Generated aligned metarig: {metarig.name}")

    generated_rig = generate_rigify_rig(metarig, source)
    print(f"Generated Rigify rig: {generated_rig.name}")

    migrate_meshes(source, generated_rig, meshes)
    hide_setup_armatures(source, metarig)
    select_only([generated_rig] + meshes, active=generated_rig)
    bpy.context.view_layer.update()
    print("Migration completed")
    print(f"Hidden setup armatures: {source.name}, {metarig.name}")
    print("=== End Auto Rigify bind pipeline ===\n")
    return generated_rig


if __name__ == '__main__':
    main()
