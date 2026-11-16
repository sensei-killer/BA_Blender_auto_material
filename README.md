# BA_Blender_auto_material

## Usage
- Blender 4.2 - 5.3
- Install the add-on
- Find **BA** in the sidebar
- Select the model and make sure it is in a static pose facing the `-Y` axis
- Set up the materials

## Version 0.2.3

- Validate material resources before replacing existing nodes.
- Match selected textures without relying on file-selection order.
- Keep face and hair shader controls separate for each character.
- Update bundled shader and outline groups explicitly with **Update Node Resources**.
  Existing instance values are preserved; old groups are retained as backups.
- Remove confirmed invalid legacy drivers from the bundled resources.
- Check Rigify inputs before conversion and restore scene data after Python failures.
- Adapt Geometry Nodes inputs and image color spaces to Blender 5.2 and 5.3 while
  retaining the Blender 4.x API paths.

See [release notes](CHANGELOG.md) and the [Chinese verification guide](VERIFICATION_0.2.3.md).

## Feedback

[![Discord](https://img.shields.io/discord/YOUR_SERVER_ID?label=Discord&logo=discord)](https://discord.gg/3nmxESc6Ha)

If you run into any issues, you can reach me on this Discord server. I don’t always check GitHub.
