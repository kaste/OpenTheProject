from collections import Counter
from functools import wraps
from glob import glob
import json
import os

import sublime
import sublime_plugin

from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    TypeVar,
    TYPE_CHECKING,
)

if TYPE_CHECKING:
    from typing_extensions import ParamSpec

    P = ParamSpec("P")

T = TypeVar("T")
WindowId = int

STORAGE_FILE = "LastUsedProjects"
KNOWN_WINDOWS = set()  # type: Set[WindowId]
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
    # Use `on_activated` as we actually wait for a folder to get attached
    # to the window.  See `window.folders()` is checked *before* we register
    # the window as "known".
    def on_activated(self, view: sublime.View) -> None:
        window = view.window()
        if not window:
            return

        wid = window.id()
        if wid in KNOWN_WINDOWS:
            return

        if not window.folders():
            return

        KNOWN_WINDOWS.add(wid)

        if window.project_file_name():
            return

        settings = view.settings()
        auto_generate_projects = settings.get("auto_generate_projects", "ask")
        if auto_generate_projects in (True, "ask"):
            folder = window.folders()[0]
            pattern = os.path.join(folder, "*.sublime-project")
            paths = glob(pattern)
            if len(paths) == 1:
                window.status_message(
                    "Project file '{}' already exists.".format(
                        os.path.split(paths[0])[1]
                    )
                )

            elif len(paths) > 1:
                window.status_message(
                    "Multiple project files exist in '{}'.".format(folder)
                )

            else:
                window.run_command(
                    "create_std_project_file",
                    {"confirm": auto_generate_projects == "ask"},
                )
                return

        window.run_command("open_the_project_instead")


class create_std_project_file(sublime_plugin.WindowCommand):
    def is_enabled(self) -> bool:
        window = self.window
        return not window.project_file_name() and bool(window.folders())

    def run(self, confirm: bool = False) -> None:
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

        def create_project_file():
            with open(project_file_name, "w") as file:
                file.write(PROJECT_TEMPLATE)

            window.status_message(
                "Created project file `{}`".format(project_file_name)
            )
            window.run_command(
                "open_project_or_workspace",
                {"file": project_file_name, "new_window": False},
            )

        if confirm:

            def on_done(result: int) -> None:
                if result != 0:
                    return  # 'No' or cancelled
                create_project_file()

            items = ["Create project file {!r}".format(basename), "No, thanks"]
            window.show_quick_panel(
                items, on_done, sublime.KEEP_OPEN_ON_FOCUS_LOST
            )

        else:
            create_project_file()


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

        window.run_command(
            "open_project_or_workspace",
            {"file": paths[0], "new_window": False},
        )


def eat_exceptions(f: "Callable[P, T]") -> "Callable[P, Optional[T]]":
    @wraps(f)
    def wrapped(*a, **kw):
        try:
            return f(*a)
        except:
            return None

    return wrapped


@eat_exceptions
def read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf8") as f:
        return json.load(f)


def write_json(path: str, data: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf8") as f:
        json.dump(data, f, sort_keys=True, indent=4)


def storage_file_path() -> str:
    return os.path.join(sublime.packages_path(), "User", STORAGE_FILE)


def read_storage_file() -> Dict[str, Any]:
    return read_json(storage_file_path()) or {
        "_": "Do not edit manually; storage for OpenTheProject package",
        "paths": [],
    }


def write_storage_file(data: Dict[str, Any]) -> None:
    write_json(storage_file_path(), data)


def get_history(key: str) -> Any:
    d = read_storage_file()
    return d[key]


def persist_history(**kw: Any) -> None:
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
        self.window.run_command(
            "open_project_or_workspace",
            {"file": project_file, "new_window": True},
        )
