import bpy
from pathlib import Path

# One-click pipeline:
# 1. Select one source/original armature and one or more meshes.
# 2. Run this script.
# 3. It creates/alights a Rigify Human metarig, generates the Rigify rig, and
#    migrates selected meshes from the source armature to the generated rig.
#
# This script reuses the workspace scripts:
# - create_and_align_human_metarig.py
# - migrate_body_to_rig_auto.py

CREATE_SCRIPT = "create_and_align_human_metarig.py"
MIGRATE_SCRIPT = "migrate_body_to_rig_auto.py"
GENERATED_RIG_SUFFIX = "_rigify_auto"


def script_dir():
    if "__file__" in globals():
        return Path(__file__).resolve().parent
    return Path(r"E:\project\code\ba\ba_shader")


def load_script(name):
    text = bpy.data.texts.get(name)
    if text is not None:
        return text.as_string()
    path = script_dir() / name
    return path.read_text(encoding="utf-8")


def require_selection():
    selected = list(bpy.context.selected_objects)
    armatures = [obj for obj in selected if obj.type == "ARMATURE"]
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


def run_script_text(name):
    script = load_script(name)
    namespace = {"__name__": "__main__", "__file__": str(script_dir() / name)}
    exec(compile(script, name, "exec"), namespace)
    return namespace


def create_and_align_metarig(source):
    before = set(bpy.data.objects)
    select_only([source], active=source)
    run_script_text(CREATE_SCRIPT)
    after = set(bpy.data.objects)

    new_armatures = [obj for obj in after - before if obj.type == "ARMATURE"]
    if len(new_armatures) == 1:
        return new_armatures[0]

    expected_name = f"{source.name}_metarig_auto"
    obj = bpy.data.objects.get(expected_name)
    if obj and obj.type == "ARMATURE":
        return obj

    candidates = [obj for obj in bpy.data.objects if obj.type == "ARMATURE" and obj.name.endswith("_metarig_auto")]
    if candidates:
        return candidates[-1]
    raise RuntimeError("Could not find generated metarig after create/alignment step")


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
    return rig


def migrate_meshes(source, generated_rig, meshes):
    select_only([source, generated_rig] + meshes, active=meshes[0])
    run_script_text(MIGRATE_SCRIPT)


def hide_setup_armatures(source, metarig):
    for obj in (source, metarig):
        obj.hide_set(True)
        obj.hide_viewport = True
        obj.hide_render = True


def main():
    source, meshes = require_selection()
    print("\n=== Auto Rigify bind pipeline ===")
    print(f"Source armature: {source.name}")
    print(f"Meshes: {[mesh.name for mesh in meshes]}")

    metarig = create_and_align_metarig(source)
    print(f"Generated aligned metarig: {metarig.name}")

    generated_rig = generate_rigify_rig(metarig, source)
    print(f"Generated Rigify rig: {generated_rig.name}")

    migrate_meshes(source, generated_rig, meshes)
    hide_setup_armatures(source, metarig)
    select_only([generated_rig] + meshes, active=generated_rig)
    print("Migration completed")
    print(f"Hidden setup armatures: {source.name}, {metarig.name}")
    print("=== End Auto Rigify bind pipeline ===\n")


main()
