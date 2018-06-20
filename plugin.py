from glob import glob
import os
import subprocess

import sublime
import sublime_plugin


KNOWN_WINDOWS = set()
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
    def on_activated_async(self, view):
        window = view.window()
        if not window:
            return

        wid = window.id()
        if wid in KNOWN_WINDOWS:
            return

        KNOWN_WINDOWS.add(wid)
        window.run_command('create_std_project_file')
        window.run_command('open_the_project_instead')


class create_std_project_file(sublime_plugin.WindowCommand):
    def is_enabled(self):
        window = self.window
        return not window.project_file_name() and bool(window.folders())

    def run(self):
        window = self.window

        folder = window.folders()[0]
        dirname = os.path.basename(folder)

        basename = dirname + '.sublime-project'
        project_file_name = os.path.join(folder, basename)
        if os.path.exists(project_file_name):
            window.status_message(
                "Project file '{}' already exists.".format(basename)
            )
            return

        items = ['Create project file {!r}'.format(basename), 'No, thanks']

        def on_done(result):
            if result != 0:
                return  # 'No' or cancelled

            with open(project_file_name, 'w') as file:
                file.write(PROJECT_TEMPLATE)

            window.status_message(
                'Created project file `{}`'.format(project_file_name)
            )
            window.run_command('open_the_project_instead')

        window.show_quick_panel(items, on_done)


class open_the_project_instead(sublime_plugin.WindowCommand):
    def is_enabled(self):
        window = self.window
        return not window.project_file_name() and bool(window.folders())

    def run(self):
        window = self.window

        folder = window.folders()[0]
        pattern = os.path.join(folder, '*.sublime-project')
        paths = glob(pattern)
        if not paths:
            window.status_message('No project file in first folder')
            return

        if len(paths) > 1:
            window.status_message('More that one project file.')
            return

        bin = get_executable()
        path = paths[0]
        cmd = [bin, path]
        try:
            subprocess.Popen(cmd, startupinfo=create_startupinfo())
        except OSError:
            raise
        else:
            sublime.set_timeout_async(
                lambda: window.run_command('close_window'), 100
            )


# Function taken from https://github.com/randy3k/ProjectManager
# Copyright (c) 2017 Randy Lai <randy.cs.lai@gmail.com>
def get_executable():
    executable_path = sublime.executable_path()
    if sublime.platform() == 'osx':
        app_path = executable_path[: executable_path.rfind('.app/') + 5]
        executable_path = app_path + 'Contents/SharedSupport/bin/subl'

    return executable_path


def create_startupinfo():
    if os.name == 'nt':
        info = subprocess.STARTUPINFO()
        info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return info

    return None
