from collections import Counter
from functools import wraps
from glob import glob
import json
import os
import subprocess

import sublime
import sublime_plugin

MYPY = False
if MYPY:
    from typing import Any, Callable, Dict, List, Optional, Set, TypeVar

    T = TypeVar("T")


USE_BUILTIN_COMMAND = int(sublime.version()) > 4053
STORAGE_FILE = "LastUsedProjects"
KNOWN_WINDOWS = set()  # type: Set[sublime.WindowId]
PROJECT_TEMPLATE = """
{
    "folders": [
        {
            "path": "."
        },
    ],

    "settings": {
    }
}

"""


class AutomaticallyOpenFolderAsProject(sublime_plugin.EventListener):
    def on_activated(self, view: sublime.View) -> None:
        def program():
            window = view.window()
            if not window:
                return

            wid = window.id()
            if wid in KNOWN_WINDOWS:
                return

            KNOWN_WINDOWS.add(wid)
            window.run_command("create_std_project_file")
            window.run_command("open_the_project_instead")

        # work around ST #3370
        sublime.set_timeout(program)


class create_std_project_file(sublime_plugin.WindowCommand):
    def is_enabled(self) -> bool:
        window = self.window
        return not window.project_file_name() and bool(window.folders())

    def run(self) -> None:
        window = self.window

        folder = window.folders()[0]
        dirname = os.path.basename(folder)

        basename = dirname + ".sublime-project"
        project_file_name = os.path.join(folder, basename)
        if os.path.exists(project_file_name):
            window.status_message(
                "Project file '{}' already exists.".format(basename)
            )
            return

        items = ["Create project file {!r}".format(basename), "No, thanks"]

        def on_done(result: int) -> None:
            if result != 0:
                return  # 'No' or cancelled

            with open(project_file_name, "w") as file:
                file.write(PROJECT_TEMPLATE)

            window.status_message(
                "Created project file `{}`".format(project_file_name)
            )
            window.run_command("open_the_project_instead")

        window.show_quick_panel(items, on_done, sublime.KEEP_OPEN_ON_FOCUS_LOST)


class open_the_project_instead(sublime_plugin.WindowCommand):
    def is_enabled(self) -> bool:
        window = self.window
        return not window.project_file_name() and bool(window.folders())

    def run(self) -> None:
        window = self.window

        folder = window.folders()[0]
        pattern = os.path.join(folder, "*.sublime-project")
        paths = glob(pattern)
        if not paths:
            window.status_message("No project file in first folder")
            return

        if len(paths) > 1:
            window.status_message("More that one project file.")
            return

        if USE_BUILTIN_COMMAND:
            window.run_command(
                "open_project_or_workspace",
                {"file": paths[0], "new_window": False},
            )
        else:
            window.run_command(
                "open_project_in_new_window", {"project_file": paths[0]}
            )


class open_project_in_new_window(sublime_plugin.WindowCommand):
    def run(self, project_file: str, close_current: bool = True) -> None:
        window = self.window
        open_wids = get_open_wids()

        bin = get_executable()
        cmd = [bin, "-p", project_file]
        subprocess.Popen(cmd, startupinfo=create_startupinfo())

        if close_current:
            sublime.set_timeout(lambda: close_window(window.id(), open_wids))


def get_open_wids() -> "Set[sublime.WindowId]":
    return {w.id() for w in sublime.windows()}


def close_window(
    wid: "sublime.WindowId", open_wids: "Set[sublime.WindowId]"
) -> None:
    current_wids = get_open_wids()
    if wid not in current_wids:
        return

    if current_wids != open_wids:
        window = sublime.Window(wid)
        window.run_command("close_window")

    sublime.set_timeout(lambda: close_window(wid, open_wids))


# Function taken from https://github.com/randy3k/ProjectManager
# Copyright (c) 2017 Randy Lai <randy.cs.lai@gmail.com>
def get_executable() -> str:
    executable_path = sublime.executable_path()
    if sublime.platform() == "osx":
        app_path = executable_path[: executable_path.rfind(".app/") + 5]
        executable_path = app_path + "Contents/SharedSupport/bin/subl"

    return executable_path


def create_startupinfo() -> "Optional[subprocess.STARTUPINFO]":
    if os.name == "nt":
        info = subprocess.STARTUPINFO()
        info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return info

    return None


# Type reads okay, but mypy doesn't support decorators, +1
# https://github.com/python/mypy/issues/3157
def eat_exceptions(f: "Callable[..., T]") -> "Callable[..., Optional[T]]":
    @wraps(f)
    def wrapped(*a, **kw):
        try:
            return f(*a)
        except:
            return None

    return wrapped


@eat_exceptions
def read_json(path: str) -> "Dict[str, Any]":
    with open(path, "r", encoding="utf8") as f:
        return json.load(f)


def write_json(path: str, data: "Dict[str, Any]") -> None:
    with open(path, "w", encoding="utf8") as f:
        json.dump(data, f, sort_keys=True, indent=4)


def storage_file_path() -> str:
    return os.path.join(sublime.packages_path(), "User", STORAGE_FILE)


def read_storage_file() -> "Dict[str, Any]":
    return read_json(storage_file_path()) or {
        "_": "Do not edit manually; storage for OpenTheProject package",
        "paths": [],
    }


def write_storage_file(data: "Dict[str, Any]") -> None:
    write_json(storage_file_path(), data)


def get_history(key: str) -> "Any":
    d = read_storage_file()
    return d[key]


def persist_history(**kw: "Any") -> None:
    d = read_storage_file()
    d.update(**kw)
    write_storage_file(d)


def get_paths_history() -> "List[str]":
    return get_history("paths")


class RememberLastUsedProjects(sublime_plugin.EventListener):
    def on_activated_async(self, view: sublime.View) -> None:
        window = view.window()
        if not window:
            return

        project_path = window.project_file_name()
        if not project_path:
            return

        paths = get_paths_history()
        if project_path not in paths:
            paths.append(project_path)
        elif paths[-1:] == [project_path]:
            return
        else:
            paths.remove(project_path)
            paths.append(project_path)

        persist_history(paths=paths)


EMPTY_LIST = "No projects in history."


def get_items(paths):
    _paths = [
        (p, components[0][:-16], components[1:])
        for p, components in (
            (p, list(reversed(p.split(os.sep)))) for p in paths
        )
    ]
    counts = Counter(stem for path, stem, components in _paths)
    unique = lambda stem: counts[stem] == 1  # noqa: E731

    rv = []
    for path, stem, components in reversed(_paths):
        if unique(stem):
            rv.append(([stem], path))
        else:
            rv.append(([stem] + components, path))

    return [
        [" {} ".format(os.sep).join(components), path] for components, path in rv
    ]


class open_last_used_project(sublime_plugin.WindowCommand):
    def run(self, project_file: str = None) -> None:
        if project_file is not None:
            self.open_or_focus_project(project_file)
            return

        _paths = get_paths_history()
        paths = [p for p in _paths if os.path.exists(p)]
        if paths != _paths:
            persist_history(paths=paths)

        items = get_items(paths)

        def on_done(idx: int):
            if idx == -1:
                return

            selected = items[idx]
            if selected == EMPTY_LIST:
                return

            self.open_or_focus_project(selected[1])

        self.window.show_quick_panel(
            # items or [EMPTY_LIST],
            [i[0] for i in items] or [EMPTY_LIST],
            on_done,
            flags=0,
            # flags=sublime.MONOSPACE_FONT,
            selected_index=1,
        )

    def open_or_focus_project(self, project_file: str) -> None:
        if USE_BUILTIN_COMMAND:
            self.window.run_command(
                "open_project_or_workspace",
                {"file": project_file, "new_window": True},
            )
        else:
            self.impl(project_file)

    def impl(self, project_file: str) -> None:
        for w in sublime.windows():
            if w.project_file_name() == project_file:
                ag, av = w.active_group(), w.active_view()
                w.focus_group(ag)
                if av:
                    w.focus_view(av)
                return
        else:
            self.window.run_command(
                "open_project_in_new_window",
                {"project_file": project_file, "close_current": False},
            )
