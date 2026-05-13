import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def module_tree(name):
    return ast.parse((ROOT / name).read_text(encoding="utf-8"))


def top_level_defs(tree, kind):
    return [
        node.name
        for node in tree.body
        if isinstance(node, kind)
    ]


def test_common_blender_helpers_live_in_utils_module():
    utils = module_tree("ba_utils.py")
    functions = set(top_level_defs(utils, ast.FunctionDef))

    assert {
        "nodegroup_blend_path",
        "import_node_group",
        "ensure_node_group",
        "ensure_output",
        "clear_nodes",
        "new_tex",
        "safe_link",
        "import_material",
        "ensure_socket_is_attribute",
    }.issubset(functions)


def test_init_only_registers_one_character_setup_operator():
    init_tree = module_tree("__init__.py")
    class_names = top_level_defs(init_tree, ast.ClassDef)

    assert "BA_OT_setup_materials" not in class_names


def test_duplicate_helpers_are_not_redeclared_in_feature_modules():
    duplicate_helpers = {
        "ensure_node_group",
        "import_node_group",
        "ensure_output",
        "clear_nodes",
        "new_tex",
        "safe_link",
        "import_material",
        "ensure_socket_is_attribute",
    }

    for module_name in [
        "ba_ch_materials.py",
        "ba_props.py",
        "ba_halo.py",
        "ba_outline.py",
        "ba_props_outline.py",
    ]:
        tree = module_tree(module_name)
        functions = set(top_level_defs(tree, ast.FunctionDef))

        assert not (functions & duplicate_helpers), module_name


def test_prop_outline_node_group_name_is_spelled_correctly():
    source = (ROOT / "ba_props_outline.py").read_text(encoding="utf-8")

    assert "ba_weapon_outline" in source
    assert "ba_weapeon_ouline" not in source


def test_shader_controls_expose_shared_head_control_helper():
    source = (ROOT / "ba_shader_controls.py").read_text(encoding="utf-8")

    assert "def ensure_head_control" in source
    assert "def ensure_hair_spec_control" in source
    assert "def ensure_face_light_dot_control" in source


def test_rotation_driver_helpers_guard_against_missing_empty():
    source = (ROOT / "ba_shader_controls.py").read_text(encoding="utf-8")

    assert "if empty is None:" in source


if __name__ == "__main__":
    test_common_blender_helpers_live_in_utils_module()
    test_init_only_registers_one_character_setup_operator()
    test_duplicate_helpers_are_not_redeclared_in_feature_modules()
    test_prop_outline_node_group_name_is_spelled_correctly()
    test_shader_controls_expose_shared_head_control_helper()
    test_rotation_driver_helpers_guard_against_missing_empty()
