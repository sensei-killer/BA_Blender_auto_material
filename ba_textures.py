"""Resolve only the images selected for this operation, without order heuristics."""

import os
import re

import bpy


class MaterialSetupError(RuntimeError):
    pass


def load_selected_images(directory, files):
    paths = []
    for item in files:
        name = item.name
        if not name or not name.strip():
            raise MaterialSetupError('No image filename was received. Select image files and try again.')
        path = os.path.join(bpy.path.abspath(directory), name)
        if not os.path.isfile(path):
            raise MaterialSetupError(f'Selected image is missing or is not a file: {path}')
        paths.append(path)
    images = []
    existing = set(bpy.data.images)
    for path in paths:
        try:
            image = bpy.data.images.load(path, check_existing=True)
        except (OSError, RuntimeError) as exc:
            raise MaterialSetupError(f'Cannot read selected image: {path}: {exc}') from exc
        if image.size[0] <= 0 or image.size[1] <= 0:
            if image not in existing and image.users == 0:
                bpy.data.images.remove(image)
            raise MaterialSetupError(f'Selected file has no readable image data: {path}')
        images.append(image)
    return images


def name_key(name):
    return re.sub(r"\.\d{3,}$", "", name or "").casefold()


def image_key(image):
    path = bpy.path.abspath(image.filepath) if image.filepath else name_key(image.name)
    return os.path.splitext(os.path.basename(path))[0].casefold()


def unique_images(images):
    result = []
    paths = set()
    for image in images:
        key = bpy.path.abspath(image.filepath).casefold() if image.filepath else image.as_pointer()
        if key not in paths:
            result.append(image)
            paths.add(key)
    return result


def choose(candidates, material, purpose):
    if len(candidates) > 1:
        names = ", ".join(image.name for image in candidates)
        raise MaterialSetupError(f"{material.name}: ambiguous {purpose} textures: {names}")
    return candidates[0] if candidates else None


def find_character_image(images, role, material):
    role = role.casefold()
    candidates = [i for i in unique_images(images) if image_key(i).endswith(role)]
    material_key = name_key(material.name)
    character = re.search(r"(?:^|_)(ch\d+)(?:_|$)", material_key)
    if character:
        token = character.group(1)
        exact = [i for i in candidates if re.search(r"(?:^|_)" + re.escape(token) + r"(?:_|$)", image_key(i))]
        if exact:
            return choose(exact, material, role)
        candidates = [i for i in candidates if not re.search(r"(?:^|_)ch\d+(?:_|$)", image_key(i))]
    return choose(candidates, material, role)


def find_prop_images(images, material):
    images = unique_images(images)
    masks = [i for i in images if image_key(i).endswith("mask")]
    bases = [i for i in images if i not in masks]
    key = name_key(material.name)
    keys = {key, re.sub(r"_alpha$", "", key)}
    matched = [i for i in bases if image_key(i) in keys]
    character = re.search(r'(?:^|_)(ch\d+)(?:_|$)', key)
    if character:
        token = character.group(1)
        def compatible(image):
            image_character = re.search(r'(?:^|_)(ch\d+)(?:_|$)', image_key(image))
            return image_character is None or image_character.group(1) == token
        bases = [i for i in bases if compatible(i)]
        masks = [i for i in masks if compatible(i)]
    base = choose(matched or bases, material, "base color")
    if base:
        base_key = image_key(base)
        matched_masks = [i for i in masks if image_key(i) in {base_key + "_mask", base_key + "mask"}]
        mask = choose(matched_masks or masks, material, "mask")
    else:
        mask = choose(masks, material, "mask")
    return base, mask
