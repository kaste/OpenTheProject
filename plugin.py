from glob import glob
import os
import subprocess

import sublime
import sublime_plugin


SUBL_BINARY = 'c:\\Dev\\Sublime Text 3\\subl.exe'
KNOWN_WINDOWS = set()


class AutomaticallyOpenFolderAsProject(sublime_plugin.EventListener):
    def on_activated_async(self, view):
        window = view.window()
        if not window:
            return

        wid = window.id()
        if wid in KNOWN_WINDOWS:
            return

        KNOWN_WINDOWS.add(wid)
        window.run_command('open_the_project_instead')


class open_the_project_instead(sublime_plugin.WindowCommand):
    def is_enabled(self):
        window = self.window
        return not window.project_file_name() and bool(window.folders())

    def run(self):
        window = self.window

        if window.project_file_name():
            window.status_message('Window already bound to a project')
            return

        folders = window.folders()
        if not folders:
            window.status_message('No open folder')
            return

        folder = folders[0]
        pattern = os.path.join(folder, '*.sublime-project')
        paths = glob(pattern)
        if not paths:
            window.status_message('No project file in first folder')
        if len(paths) > 1:
            window.status_message('More that one project file.')

        path = paths[0]
        cmd = [SUBL_BINARY, path]
        try:
            subprocess.Popen(cmd, startupinfo=create_startupinfo())
        except OSError:
            raise
        else:
            sublime.set_timeout_async(
                lambda: window.run_command('close_window'), 100)


def create_startupinfo():
    if os.name == 'nt':
        info = subprocess.STARTUPINFO()
        info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return info

    return None
