from collections import deque
from glob import glob
import os
import subprocess

import sublime
import sublime_plugin

try:
    from typing import Deque, List, Optional, Set  # noqa
except ImportError:
    ...


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
        window = view.window()
        if not window:
            return

        wid = window.id()
        if wid in KNOWN_WINDOWS:
            return

        KNOWN_WINDOWS.add(wid)
        window.run_command("create_std_project_file")
        window.run_command("open_the_project_instead")


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

        window.run_command(
            "open_project_in_new_window", {"project_file": paths[0]}
        )


class open_project_in_new_window(sublime_plugin.WindowCommand):
    def run(
        self, project_file: str, close_current: bool = True
    ) -> None:  # type: ignore
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


def get_paths_history() -> "List[str]":
    s = sublime.load_settings(STORAGE_FILE)
    return s.get("paths") or []


def persist_paths_history(paths) -> None:
    s = sublime.load_settings(STORAGE_FILE)
    s.set("paths", paths[-30:])
    sublime.save_settings(STORAGE_FILE)


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

        persist_paths_history(paths)
        print("--> last_used_projects", [os.path.basename(p) for p in paths])


class open_last_used_project(sublime_plugin.WindowCommand):
    def run(self, project_file: str) -> None:
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

    def input(self, args):
        if "project_file" not in args:
            return ChooseProjectFile()


class ChooseProjectFile(sublime_plugin.ListInputHandler):
    def name(self) -> str:
        return "project_file"

    def list_items(self):
        return (
            [
                (os.path.basename(p)[:-16], p)
                for p in reversed(get_paths_history())
            ],
            1,
        ) or ["No projects in history."]
