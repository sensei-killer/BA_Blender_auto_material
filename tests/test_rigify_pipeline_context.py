from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_auto_rigify_pipeline_passes_explicit_migration_context():
    pipeline = (ROOT / "auto_rigify_bind_pipeline.py").read_text(encoding="utf-8")
    migrate = (ROOT / "migrate_body_to_rig_auto.py").read_text(encoding="utf-8")

    assert "def run_script_text(name, extra_namespace=None)" in pipeline
    assert "namespace.update(extra_namespace)" in pipeline
    assert '"BA_SOURCE_ARMATURE": source' in pipeline
    assert '"BA_TARGET_ARMATURE": generated_rig' in pipeline
    assert '"BA_SELECTED_MESHES": meshes' in pipeline

    assert "def resolve_scene_objects_from_context()" in migrate
    assert 'source = globals().get("BA_SOURCE_ARMATURE")' in migrate
    assert 'target = globals().get("BA_TARGET_ARMATURE")' in migrate
    assert 'meshes = globals().get("BA_SELECTED_MESHES")' in migrate
    assert "return resolve_scene_objects_from_context() or resolve_scene_objects_from_selection()" in migrate


if __name__ == "__main__":
    test_auto_rigify_pipeline_passes_explicit_migration_context()
