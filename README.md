# Hi

The plugin automatically opens a folder as a project.

:confused:? So, you usually type 

```
subl <folder>
OR
subl .
```

But this opens the folder not bound to any project data or project settings. :cry:  

We can fix that. :wink: If there is a `*.sublime-project` in that folder, we just open the project instead!  And if there is no project file, we will ask you to create a basic one.
A new view setting `auto_generate_projects` can be used to parameterize the latter feature.
Set it to `True` to create a project file automatically without asking, `"ask"` (the default)
to confirm the creation, and `False` to never do it.

If you set `False` you can invoke `Create Project File: from first open folder`
from the Command Palette.


# Open Project

There is also a simple project switcher `Open Project` (the command is called `open_last_used_project`).  E.g.

```
  { "keys": ["ctrl+o"], "command": "open_last_used_project"},
```

This is similar to the built in "Quick Switch Project" but suppresses workspace
files (because ~~nobody uses~~I don't use them[1]). It uses a standard quick panel
which just works perfectly.  Use `ctrl+enter` to switch projects, reusing the window,
and `enter` to focus or open a new window.  As the most recently used project is
selected by default, this allows for e.g. `ctrl+o, ctrl+enter` to switch between the two recent projects very quickly.

(It also cleans up quickly as it hides unreachable folders. 👋)

This feature transparently saves its state to "User/LastUsedProjects".  You shouldn't edit this
file probably.

[1] I don't use *multiple* workspaces per project.
