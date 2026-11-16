"""Restore only data touched by a Rigify conversion when a Python step fails."""

import bpy


def copy_value(value):
    if isinstance(value, bpy.types.ID):
        return value
    if hasattr(value, 'copy'):
        return value.copy()
    if hasattr(value, '__len__') and not isinstance(value, str):
        return tuple(value)
    return value


def constraint_state(constraint):
    values = {}
    for prop in constraint.bl_rna.properties:
        if prop.is_readonly or prop.identifier == 'rna_type' or prop.type == 'COLLECTION':
            continue
        try:
            values[prop.identifier] = copy_value(getattr(constraint, prop.identifier))
        except (AttributeError, TypeError):
            continue
    return constraint, values


def restore_drivers(owner, backup):
    if owner.animation_data:
        for curve in list(owner.animation_data.drivers):
            owner.animation_data.drivers.remove(curve)
    if backup is None or backup.animation_data is None:
        return
    drivers = owner.animation_data_create().drivers
    for original in backup.animation_data.drivers:
        curve = drivers.from_existing(src_driver=original)
        for variable in curve.driver.variables:
            for target in variable.targets:
                if target.id == backup:
                    target.id = owner


class ConversionState:
    def __init__(self, context, source, meshes, weighted_meshes):
        self.context = context
        self.selected = list(context.selected_objects)
        self.active = context.view_layer.objects.active
        self.mode = self.active.mode if self.active else 'OBJECT'
        self.objects_before = set(bpy.data.objects)
        self.collections_before = set(bpy.data.collections)
        self.data_before = {name: set(getattr(bpy.data, name)) for name in ('meshes', 'armatures', 'actions', 'texts')}
        weighted_meshes = set(weighted_meshes)
        touched = set(meshes) | {source}
        touched.update(o for o in bpy.data.objects if o.parent == source or o.get('_ba_owner_rig') == source)
        touched.update(o for o in bpy.data.objects if o.name in ('hair_spec_normal', 'face_light_dot', source.name + '_metarig_auto'))
        self.states = []
        self.driver_trees = set()
        self.drivers = {}
        for obj in touched:
            state = {
                'object': obj, 'name': obj.name, 'data_name': obj.data.name if obj.data else None,
                'parent': obj.parent, 'parent_type': obj.parent_type, 'parent_bone': obj.parent_bone,
                'world': obj.matrix_world.copy(), 'parent_inverse': obj.matrix_parent_inverse.copy(),
                'hidden': obj.hide_get(), 'hide_viewport': obj.hide_viewport, 'hide_render': obj.hide_render,
                'owner': obj.get('_ba_owner_rig'), 'role': obj.get('_ba_control_role'),
                'constraints': [constraint_state(c) for c in obj.constraints],
                'modifiers': [(m, m.name, m.object) for m in obj.modifiers if m.type == 'ARMATURE'],
            }
            if obj in meshes:
                if obj in weighted_meshes:
                    state['mesh'] = obj.data
                    state['groups'] = [(g.name, g.lock_weight) for g in obj.vertex_groups]
                    state['active_group'] = obj.vertex_groups.active_index
                for slot in obj.material_slots:
                    if slot.material and slot.material.node_tree:
                        tree = slot.material.node_tree
                        self.driver_trees.add(tree)
            self.states.append(state)

    def begin(self):
        # Let Blender copy the complete FCurves, including user modifiers/flags.
        for tree in self.driver_trees:
            backup = tree.copy() if tree.animation_data and tree.animation_data.drivers else None
            self.drivers[tree] = backup
        for state in self.states:
            if 'mesh' in state:
                state['object'].data = state['mesh'].copy()

    def rollback(self):
        context = self.context
        errors = []
        try:
            if context.object and context.object.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
        except RuntimeError as exc:
            errors.append(f'Cannot leave current mode: {exc}')
        for state in self.states:
            obj = state['object']
            try:
                obj.name = state['name']
                if obj.data and state['data_name']:
                    obj.data.name = state['data_name']
                if 'mesh' in state and obj.data != state['mesh']:
                    obj.vertex_groups.clear()
                    for name, locked in state['groups']:
                        obj.vertex_groups.new(name=name).lock_weight = locked
                    obj.data = state['mesh']
                    obj.vertex_groups.active_index = state['active_group']
                previous = {m for m, _, _ in state['modifiers']}
                for mod in list(obj.modifiers):
                    if mod.type == 'ARMATURE' and mod not in previous:
                        obj.modifiers.remove(mod)
                for mod, name, target in state['modifiers']:
                    mod.name, mod.object = name, target
                obj.parent, obj.parent_type, obj.parent_bone = state['parent'], state['parent_type'], state['parent_bone']
                obj.matrix_parent_inverse = state['parent_inverse']
                obj.matrix_world = state['world']
                obj.hide_viewport, obj.hide_render = state['hide_viewport'], state['hide_render']
                obj.hide_set(state['hidden'])
                for key, value in (('_ba_owner_rig', state['owner']), ('_ba_control_role', state['role'])):
                    if value is None:
                        if key in obj:
                            del obj[key]
                    else:
                        obj[key] = value
                old_constraints = {c for c, _ in state['constraints']}
                for constraint in list(obj.constraints):
                    if constraint not in old_constraints:
                        obj.constraints.remove(constraint)
                for constraint, values in state['constraints']:
                    for key, value in values.items():
                        setattr(constraint, key, value)
            except Exception as exc:
                errors.append(f'{state["name"]}: {exc}')
        for tree, drivers in self.drivers.items():
            try:
                restore_drivers(tree, drivers)
            except Exception as exc:
                errors.append(f'{tree.name}: {exc}')
        if not errors:
            for obj in set(bpy.data.objects) - self.objects_before:
                bpy.data.objects.remove(obj, do_unlink=True)
            for collection in set(bpy.data.collections) - self.collections_before:
                bpy.data.collections.remove(collection)
            self.release_new_data(failed=True)
        try:
            bpy.ops.object.select_all(action='DESELECT')
            for obj in self.selected:
                obj.select_set(True)
            context.view_layer.objects.active = self.active
            if self.active and self.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode=self.mode)
            context.view_layer.update()
        except RuntimeError as exc:
            errors.append(f'Cannot restore selection/mode: {exc}')
        return errors

    def release_new_data(self, failed=False):
        for backup in self.drivers.values():
            if backup is not None:
                bpy.data.node_groups.remove(backup)
        self.drivers.clear()
        for name, previous in self.data_before.items():
            collection = getattr(bpy.data, name)
            for item in set(collection) - previous:
                if item.users == 0 or (failed and name == 'texts' and item.use_fake_user and item.users == 1):
                    collection.remove(item)
