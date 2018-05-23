from glob import glob
import os
import shutil
import subprocess

import sublime
import sublime_plugin


LISTENER_KEY = 'OpenTheProjectListener'
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
            return

        if len(paths) > 1:
            window.status_message('More that one project file.')
            return

        settings = sublime.load_settings('OpenTheProject.sublime-settings')

        bin = settings.get('subl') or shutil.which('subl')
        if not bin:
            window.status_message(
                'No `which subl`. Fill in a value in the settings')
            open_settings_and_maybe_rerun(window)
            return

        path = paths[0]
        cmd = [bin, path]
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


def open_settings_and_maybe_rerun(window):
    settings = sublime.load_settings('OpenTheProject.sublime-settings')

    def listen_for_settings_change():
        settings.clear_on_change(LISTENER_KEY)
        window.run_command('open_the_project_instead')

    settings.add_on_change(LISTENER_KEY, listen_for_settings_change)
    window.run_command('edit_settings', {
        "base_file":
            "${packages}/OpenTheProject/"
            "OpenTheProject.sublime-settings",
        "default": DEFAULT_SETTINGS
    })


DEFAULT_SETTINGS = """
// OpenTheProject Settings - User
{
    // Absolute path to subl[.exe] binary
    "subl": "$0"
}
"""
