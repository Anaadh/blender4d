Blender4D
=========

This is a fork of Blender 5.2.2 that looks and works like Cinema 4D R24. I came from C4D and wanted Blender to feel the same, so this is Blender with C4D's managers, menus, hotkeys, generators and tags, and nothing taken away. All the Blender stuff is still there.

Most of it is a Python add-on, [C4D Feel](https://github.com/Anaadh/c4d-feel), which also runs on normal Blender. This fork adds the parts that needed C++:

- **A real Object Manager.** The Outliner gets a "Cinema 4D style" mode with the editor/render dots, the generator check and tag icons on every row, and you keep Blender's drag and drop parenting, renaming and everything else. Tags can be dragged onto other objects to copy them, and cameras get a look-through button.
- **A proper command palette.** The top bar gets a second, taller row so the palette icons are big like in C4D.
- **C4D Feel built in.** It's bundled and switched on, so you open it and you're in the C4D layout.

![Blender4D](doc/blender4d/screenshot.jpg)

This is an unofficial fork. It isn't made or endorsed by the Blender Foundation or Maxon. Blender is a trademark of the Blender Foundation and Cinema 4D is a trademark of Maxon.

### Branches

- `blender4d` is the default branch: the official `v5.2.2` release plus the Blender4D commits on top.
- `main` and the other branches are Blender's, as they come from upstream.

### Building it (Windows)

You need Visual Studio 2022 17.14 or newer, CMake and git-lfs.

```
git clone -b blender4d https://github.com/Anaadh/blender4d.git
cd blender4d
make update
make release
```

That's Blender's normal build, see the [build docs](https://developer.blender.org/docs/handbook/building_blender/) for other platforms. A full build is heavy. If your machine struggles, limit the jobs, for example with Ninja: `ninja -j 4`.

To have your own settings separate from a regular Blender install, make an empty folder called `portable` next to `blender.exe`.

### Keeping up with Blender

The Blender4D changes are small and live in a few files (`editors/space_outliner`, `editors/space_topbar`, `editors/screen`, `makesrna`), so moving to a new Blender release is mostly rebasing the `blender4d` commits onto the new tag.

### License

GPL, same as Blender. The original Blender README follows.

---

<!--
Keep this document short & concise,
linking to external resources instead of including content in-line.
See 'release/text/readme.html' for the end user read-me.
-->

Blender
=======

Blender is the free and open source 3D creation suite.
It supports the entirety of the 3D pipeline—modeling, rigging, animation, simulation, rendering, compositing,
motion tracking and video editing.

![Blender screenshot](https://code.blender.org/wp-content/uploads/2018/12/springrg.jpg "Blender screenshot")

Project Pages
-------------

- [Main Website](https://www.blender.org)
- [Reference Manual](https://docs.blender.org/manual/en/latest/index.html)
- [User Community](https://www.blender.org/community/)

Development
-----------

- [Build Instructions](https://developer.blender.org/docs/handbook/building_blender/)
- [Code Review & Bug Tracker](https://projects.blender.org)
- [Developer Forum](https://devtalk.blender.org)
- [Developer Documentation](https://developer.blender.org/docs/)


License
-------

Blender as a whole is licensed under the GNU General Public License, Version 3.
Individual files may have a different but compatible license.

See [blender.org/about/license](https://www.blender.org/about/license) for details.
