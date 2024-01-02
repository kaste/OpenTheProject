from collections import defaultdict
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
                project_file_name = os.path.split(paths[0])[1]
                window.status_message(
                    f"Project file '{project_file_name}' already exists."
                )

            elif len(paths) > 1:
                window.status_message(
                    f"Multiple project files exist in '{folder}'."
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
            window.status_message(f"Project file '{basename}' already exists.")
            return

        def create_project_file():
            with open(project_file_name, "w") as file:
                file.write(PROJECT_TEMPLATE)

            window.status_message(f"Created project file `{project_file_name}`")
            window.run_command(
                "open_project_or_workspace",
                {"file": project_file_name, "new_window": False},
            )

        if confirm:

            def on_done(result: int) -> None:
                if result != 0:
                    return  # 'No' or cancelled
                create_project_file()

            items = [f"Create project file {basename!r}", "No, thanks"]
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


NEW_WINDOW_DEFAULT = True
NOT_SET = object()
WINDOW_KIND = [sublime.KIND_ID_COLOR_ORANGISH, "W", "Window"]
PROJECT_KIND = [sublime.KIND_ID_NAMESPACE, "P", "Project"]


def get_items(paths: List[str], open_projects: List[str]):
    _paths = [
        (p, stem, components[1:])
        for p, components in (
            (p, list(reversed(p.split(os.sep)))) for p in paths
        )
        if (stem := components[0][:-16])
    ]

    grouped_by_stem = defaultdict(list)
    for path, stem, components in _paths:
        grouped_by_stem[stem].append((path, components))
    unique = lambda stem: len(grouped_by_stem[stem]) == 1  # noqa: E731

    rv = []
    for path, stem, components in reversed(_paths):
        if unique(stem):
            display_name = stem

        else:
            others = [
                components_
                for path_, components_ in grouped_by_stem[stem]
                if path_ != path
            ]
            reduced_components = []
            for part, *other_parts in zip(*(components, *others)):
                reduced_components.append(part)
                if any(p != part for p in other_parts):
                    break

            display_name = f" {os.sep} ".join(
                [stem]
                + (
                    # Often the project file ("stem") is the same as the
                    # folder name, omit the duplication then.
                    reduced_components[1:]
                    if reduced_components[0] == stem
                    else reduced_components
                ),
            )

        rv.append(
            sublime.ListInputItem(
                text=display_name,
                value=path,
                kind=(WINDOW_KIND if path in open_projects else PROJECT_KIND),
            )
        )

    return rv


class ProjectFileInputHandler(sublime_plugin.ListInputHandler):  # type: ignore[name-defined]
    def __init__(self, empty_list_message, confirm_modifier, new_window_default):
        self.empty_list_message = empty_list_message
        self._confirm_modifier = confirm_modifier
        self._new_window_default = new_window_default
        self._open_projects = [
            project_file_name
            for w in sublime.windows()
            if (project_file_name := w.project_file_name())
        ]

    def preview(self, text) -> str:
        if text in self._open_projects:
            return "[enter] to switch to window"

        if self._new_window_default:
            return "[ctrl+enter] to switch projects, [enter] to keep separate windows"
        else:
            return "[enter] to switch projects, [ctrl+enter] to keep separate windows"

    def list_items(self):
        _paths = get_paths_history()
        paths = [p for p in _paths if os.path.exists(p)]
        if paths != _paths:
            persist_history(paths=paths)

        return (
            get_items(paths, self._open_projects)
            if paths
            else [self.empty_list_message],
            1,
        )

    def want_event(self):
        return True

    def confirm(self, text, event):
        self._confirm_modifier(event.get("modifier_keys", {}))

    def validate(self, text: str, event):
        return True


class open_last_used_project(sublime_plugin.WindowCommand):
    new_window = NOT_SET
    EMPTY_LIST_MESSAGE = "No projects in history."

    def input_description(self):
        return "Switch to"

    def input(self, args):
        if "project_file" not in args:

            def confirm_modifier(key_modifiers):
                alt_action = key_modifiers.get("primary", False)
                self.new_window = (
                    not new_window_default if alt_action else new_window_default
                )

            new_window_default = args.get("new_window", NEW_WINDOW_DEFAULT)
            return ProjectFileInputHandler(
                self.EMPTY_LIST_MESSAGE, confirm_modifier, new_window_default
            )

    def run(self, project_file: str, new_window=NEW_WINDOW_DEFAULT) -> None:
        if project_file == self.EMPTY_LIST_MESSAGE:
            return

        self.window.run_command(
            "open_project_or_workspace",
            {
                "file": project_file,
                "new_window": (
                    new_window if self.new_window is NOT_SET else self.new_window
                ),
            },
        )
