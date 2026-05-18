import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_child_of_constraint_inherits_rotation_only():
    source = (ROOT / "ba_shader_controls.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }

    assert "configure_rotation_only_child_of" in functions
    assert "configure_rotation_only_child_of(child_of)" in source

    expected_settings = {
        "use_location_x": "False",
        "use_location_y": "False",
        "use_location_z": "False",
        "use_rotation_x": "True",
        "use_rotation_y": "True",
        "use_rotation_z": "True",
        "use_scale_x": "False",
        "use_scale_y": "False",
        "use_scale_z": "False",
    }

    for attr, value in expected_settings.items():
        assert f"constraint.{attr} = {value}" in source


if __name__ == "__main__":
    test_child_of_constraint_inherits_rotation_only()
