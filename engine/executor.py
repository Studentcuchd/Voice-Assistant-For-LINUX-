"""Command executor for the voice assistant."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import quote_plus

from engine.interpreter import Command
from utils.logger import get_logger

try:
    import pyautogui  # type: ignore[import-not-found]
except ImportError:
    pyautogui = None

log = get_logger(__name__)

DEFAULT_TIMEOUT = 15


class Executor:
    """Execute resolved commands using local system tools."""

    def __init__(self) -> None:
        self._dispatch: dict[str, Callable[[Command], str]] = {
            "launch_app": self._launch_app,
            "search_web": self._search_web,
            "create_directory": self._create_directory,
            "delete_file": self._delete_file,
            "delete_directory": self._delete_directory,
            "list_files": self._list_files,
            "print_working_dir": self._print_working_dir,
            "change_directory": self._change_directory,
            "go_home": self._go_home,
            "show_cpu": self._show_cpu,
            "show_memory": self._show_memory,
            "show_disk": self._show_disk,
            "show_system_info": self._show_system_info,
            "show_processes": self._show_processes,
            "shutdown": self._shutdown,
            "reboot": self._reboot,
            "update_system": self._update_system,
            "clear_screen": self._clear_screen,
            "show_date": self._show_date,
            "show_ip": self._show_ip,
            "show_uptime": self._show_uptime,
            "create_file": self._create_file,
            "automation_type": self._automation_type,
            "automation_hotkey": self._automation_hotkey,
        }

    def run(self, command: Command) -> str:
        log.info("Executing: %s (action=%s, arg=%s)", command.id, command.action, command.argument)

        if command.dangerous and not self._confirm(command):
            return "⚠️  Command cancelled by user."

        handler = self._dispatch.get(command.action)
        if handler is None:
            log.error("No handler registered for action '%s'", command.action)
            return f"❌  Unknown action '{command.action}'."

        try:
            return handler(command)
        except Exception as exc:  # noqa: BLE001
            log.exception("Handler crashed for %s: %s", command.action, exc)
            return f"❌  Error during '{command.description}': {exc}"

    def _confirm(self, command: Command) -> bool:
        print(f"\n⚠️   DANGEROUS COMMAND: {command.description.upper()}")
        if command.argument:
            print(f"    Target: {command.argument}")

        try:
            answer = input("    Are you sure? (yes/no): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return False

        confirmed = answer in {"yes", "y"}
        log.info("User %s the dangerous command '%s'", "confirmed" if confirmed else "cancelled", command.id)
        return confirmed

    @staticmethod
    def _run_cmd(
        args: list[str],
        *,
        shell: bool = False,
        timeout: int = DEFAULT_TIMEOUT,
        capture: bool = True,
    ) -> tuple[int, str, str]:
        try:
            result = subprocess.run(
                args,
                shell=shell,
                capture_output=capture,
                text=True,
                timeout=timeout,
            )
            return result.returncode, (result.stdout or "").strip(), (result.stderr or "").strip()
        except subprocess.TimeoutExpired:
            return -1, "", "Command timed out."
        except FileNotFoundError:
            cmd_name = args if shell else args[0]
            return -1, "", f"Command not found: {cmd_name}"

    @staticmethod
    def _detach_kwargs() -> dict:
        """Return platform-specific kwargs to detach subprocess from parent."""
        if os.name == "nt":  # Windows
            return {"creationflags": subprocess.DETACHED_PROCESS}
        return {"start_new_session": True}  # Unix/Linux

    @staticmethod
    def _which_first(candidates: list[str]) -> Optional[str]:
        for candidate in candidates:
            if candidate and shutil.which(candidate):
                return candidate
        return None

    @staticmethod
    def _looks_like_url(value: str) -> bool:
        text = (value or "").strip().lower()
        if not text:
            return False
        return text.startswith(("http://", "https://", "www.")) or ("." in text and " " not in text)

    def _open_url(self, url: str) -> bool:
        target = url.strip()
        if not target:
            return False
        if target.startswith("www."):
            target = f"https://{target}"
        if not target.startswith(("http://", "https://")):
            target = f"https://{target}"

        if webbrowser.open_new_tab(target):
            return True

        if os.name == "nt":
            rc, _, _ = self._run_cmd(["cmd", "/c", "start", "", target], shell=False, capture=False)
            return rc == 0

        opener = self._which_first(["xdg-open", "gio", "open"])
        if opener:
            if opener == "gio":
                rc, _, _ = self._run_cmd(["gio", "open", target], capture=False)
            else:
                rc, _, _ = self._run_cmd([opener, target], capture=False)
            return rc == 0
        return False

    def _launch_app_by_name(self, app_name: str) -> bool:
        target = app_name.strip()
        if not target:
            return False

        direct = self._which_first([target])
        if direct:
            subprocess.Popen(
                [direct],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                **self._detach_kwargs(),
            )
            return True

        if os.name == "nt":
            rc, _, _ = self._run_cmd(["cmd", "/c", "start", "", target], shell=False, capture=False)
            return rc == 0

        try:
            subprocess.Popen(
                [target],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                **self._detach_kwargs(),
            )
            return True
        except Exception:
            return False

    def _launch_app(self, command: Command) -> str:
        candidates = command.app_candidates or ([command.argument] if command.argument else [])

        if command.id == "open_browser" and command.argument:
            lower_arg = command.argument.strip().lower()
            if lower_arg.startswith(("http://", "https://", "www.")):
                url = command.argument if lower_arg.startswith(("http://", "https://")) else f"https://{command.argument}"
                opened = self._open_url(url)
                if opened:
                    return f"✅  Opened browser URL: {url}"

        app = self._which_first([candidate for candidate in candidates if candidate])
        if not app:
            tried = ", ".join(candidate for candidate in candidates if candidate)
            if command.id == "open_browser":
                opened = self._open_url("https://www.google.com")
                if opened:
                    return "✅  Opened default web browser."
                return "❌  Could not open the default web browser."
            if command.argument and self._launch_app_by_name(command.argument):
                return f"✅  Launched: {command.argument}"
            return f"❌  Could not find any of: {tried}. Is it installed?"

        subprocess.Popen(
            [app],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            **self._detach_kwargs(),
        )
        return f"✅  Launched: {app}"

    def _search_web(self, command: Command) -> str:
        query = (command.argument or "").strip()
        if not query:
            return "❌  Please specify what to search for. Example: 'search for python lists'"

        # Open URLs directly when the user dictates a site.
        if self._looks_like_url(query):
            opened = self._open_url(query)
            if not opened:
                return "❌  Could not open the URL in the browser."
            return f"✅  Opened URL: {query}"

        url = f"https://www.google.com/search?q={quote_plus(query)}"
        opened = self._open_url(url)
        if not opened:
            return "❌  Could not open the web browser for search."

        return f"✅  Searched the web for: {query}"

    def _create_directory(self, command: Command) -> str:
        if not command.argument:
            return "❌  Please specify a folder name. Example: 'create folder my_project'"
        path = Path(command.argument).expanduser()
        try:
            path.mkdir(parents=True, exist_ok=True)
            return f"✅  Folder created: {path.resolve()}"
        except PermissionError:
            return f"❌  Permission denied: cannot create '{path}'."
        except OSError as exc:
            return f"❌  Cannot create folder: {exc}"

    def _delete_file(self, command: Command) -> str:
        if not command.argument:
            return "❌  Please specify a file name."
        path = Path(command.argument).expanduser()
        if not path.exists():
            return f"❌  File not found: {path}"
        if not path.is_file():
            return f"❌  '{path}' is not a file. Use 'delete folder' for directories."
        path.unlink()
        return f"✅  Deleted file: {path}"

    def _delete_directory(self, command: Command) -> str:
        if not command.argument:
            return "❌  Please specify a folder name."
        path = Path(command.argument).expanduser()
        if not path.exists():
            return f"❌  Folder not found: {path}"
        if not path.is_dir():
            return f"❌  '{path}' is not a directory."
        shutil.rmtree(path)
        return f"✅  Deleted folder: {path}"

    def _list_files(self, command: Command) -> str:
        target = Path(command.argument or ".").expanduser()
        if not target.exists():
            return f"❌  Path not found: {target}"

        try:
            entries = sorted(target.iterdir(), key=lambda item: (item.is_file(), item.name.lower()))
        except PermissionError:
            return f"❌  Permission denied: cannot list '{target}'."

        if not entries:
            return f"📂  '{target}' is empty."

        lines = [f"📂  Contents of {target.resolve()}:"]
        for entry in entries:
            icon = "📄" if entry.is_file() else "📁"
            lines.append(f"  {icon}  {entry.name}")
        return "\n".join(lines)

    def _create_file(self, command: Command) -> str:
        if not command.argument:
            return "❌  Please specify a file name."
        path = Path(command.argument).expanduser()
        try:
            path.touch(exist_ok=True)
            return f"✅  File created: {path.resolve()}"
        except OSError as exc:
            return f"❌  Cannot create file: {exc}"

    def _print_working_dir(self, _command: Command) -> str:
        return f"📍  Current directory: {Path.cwd()}"

    def _change_directory(self, command: Command) -> str:
        if not command.argument:
            return "❌  Please specify a directory. Example: 'go to Documents'"
        path = Path(command.argument).expanduser()
        try:
            os.chdir(path)
            return f"✅  Changed to: {Path.cwd()}"
        except FileNotFoundError:
            return f"❌  Directory not found: {path}"
        except PermissionError:
            return f"❌  Permission denied: {path}"

    def _go_home(self, _command: Command) -> str:
        home = Path.home()
        os.chdir(home)
        return f"✅  Changed to home: {home}"

    def _show_cpu(self, _command: Command) -> str:
        if os.name == "nt":
            rc, out, err = self._run_cmd(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "(Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average",
                ]
            )
            if rc != 0:
                return f"❌  Could not read CPU info: {err}"
            return f"🖥️   CPU usage: {out.strip()}%"

        rc, out, err = self._run_cmd(["top", "-bn1"])
        if rc != 0:
            try:
                with open("/proc/stat", encoding="utf-8") as handle:
                    line = handle.readline()
                fields = list(map(int, line.split()[1:]))
                idle = fields[3]
                total = sum(fields)
                used_pct = 100 * (1 - idle / total)
                return f"🖥️   CPU usage: {used_pct:.1f}%  (snapshot)"
            except Exception:
                return f"❌  Could not read CPU info: {err}"

        for line in out.splitlines():
            if "cpu" in line.lower() and "%" in line:
                return f"🖥️   {line.strip()}"
        return f"🖥️   CPU info:\n{out[:500]}"

    def _show_memory(self, _command: Command) -> str:
        if os.name == "nt":
            rc, out, err = self._run_cmd(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "Get-CimInstance Win32_OperatingSystem | Select-Object TotalVisibleMemorySize,FreePhysicalMemory",
                ]
            )
            if rc != 0:
                return f"❌  Could not read memory info: {err}"
            return f"🧠  Memory usage:\n{out}"

        rc, out, err = self._run_cmd(["free", "-h"])
        if rc != 0:
            return f"❌  Could not read memory info: {err}"
        lines = out.splitlines()
        header = lines[0] if lines else ""
        memory = lines[1] if len(lines) > 1 else ""
        return f"🧠  Memory usage:\n  {header}\n  {memory}"

    def _show_disk(self, _command: Command) -> str:
        if os.name == "nt":
            rc, out, err = self._run_cmd(
                ["powershell", "-NoProfile", "-Command", "Get-PSDrive -PSProvider FileSystem"]
            )
            if rc != 0:
                return f"❌  Could not read disk info: {err}"
            return "💾  Disk usage:\n" + out

        rc, out, err = self._run_cmd(["df", "-h", "--total"])
        if rc != 0:
            rc, out, err = self._run_cmd(["df", "-h"])
        if rc != 0:
            return f"❌  Could not read disk info: {err}"

        relevant = [line for line in out.splitlines() if not line.startswith(("tmpfs", "udev"))]
        return "💾  Disk usage:\n" + "\n".join(f"  {line}" for line in relevant[:10])

    def _show_system_info(self, _command: Command) -> str:
        if os.name == "nt":
            return f"ℹ️   System info: {platform.platform()}"

        rc, out, err = self._run_cmd(["uname", "-a"])
        if rc != 0:
            return f"❌  Could not read system info: {err}"
        return f"ℹ️   System info: {out}"

    def _show_processes(self, _command: Command) -> str:
        if os.name == "nt":
            rc, out, err = self._run_cmd(["tasklist"])
            if rc != 0:
                return f"❌  Could not list processes: {err}"
            lines = out.splitlines()
            return "⚙️   Running processes:\n" + "\n".join(lines[:25])

        rc, out, err = self._run_cmd(["ps", "aux", "--sort=-%cpu"])
        if rc != 0:
            return f"❌  Could not list processes: {err}"
        lines = out.splitlines()
        header = lines[0] if lines else ""
        top10 = lines[1:11]
        return "⚙️   Top processes (by CPU):\n  " + header + "\n  " + "\n  ".join(top10)

    def _shutdown(self, _command: Command) -> str:
        rc, _, err = self._run_cmd(["shutdown", "-h", "now"])
        if rc != 0:
            return f"❌  Shutdown failed: {err}"
        return "🔴  System is shutting down…"

    def _reboot(self, _command: Command) -> str:
        rc, _, err = self._run_cmd(["reboot"])
        if rc != 0:
            return f"❌  Reboot failed: {err}"
        return "🔄  System is rebooting…"

    def _update_system(self, _command: Command) -> str:
        if os.name == "nt":
            rc, _, err = self._run_cmd(["winget", "upgrade", "--all"], timeout=120, capture=False)
            if rc == 0:
                return "✅  Windows packages updated via winget."
            return f"❌  Update failed: {err or 'winget is unavailable.'}"

        print("📦  Running system update (this may take a while)…")
        proc = subprocess.run(["sudo", "apt", "update"], capture_output=False, timeout=120)
        if proc.returncode == 0:
            return "✅  Package lists updated. Run 'sudo apt upgrade' to install updates."
        return "❌  Update failed. You may need to run manually with sudo."

    def _clear_screen(self, _command: Command) -> str:
        os.system("cls" if os.name == "nt" else "clear")  # noqa: S605
        return "🧹  Screen cleared."

    def _show_date(self, _command: Command) -> str:
        return f"🗓️   Current date and time: {datetime.now():%Y-%m-%d %H:%M:%S}"

    def _show_ip(self, _command: Command) -> str:
        if os.name == "nt":
            rc, out, err = self._run_cmd(["ipconfig"])
            if rc != 0:
                return f"❌  Could not read IP address: {err}"
            addresses = []
            for line in out.splitlines():
                if "IPv4" in line:
                    parts = line.split(":", 1)
                    if len(parts) == 2 and parts[1].strip():
                        addresses.append(parts[1].strip())
            if not addresses:
                return "❌  No IP address detected."
            return "🌐  IP address(es): " + ", ".join(addresses)

        rc, out, err = self._run_cmd(["hostname", "-I"])
        if rc != 0:
            return f"❌  Could not read IP address: {err}"
        addresses = out.split()
        if not addresses:
            return "❌  No IP address detected."
        return "🌐  IP address(es): " + ", ".join(addresses)

    def _show_uptime(self, _command: Command) -> str:
        if os.name == "nt":
            rc, out, err = self._run_cmd(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "((Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime).ToString()",
                ]
            )
            if rc != 0:
                return f"❌  Could not read uptime: {err}"
            return f"⏱️   Uptime: {out.strip()}"

        rc, out, err = self._run_cmd(["uptime", "-p"])
        if rc != 0:
            return f"❌  Could not read uptime: {err}"
        return f"⏱️   {out.strip()}"

    def _automation_type(self, command: Command) -> str:
        text = (command.argument or "").strip()
        if not text:
            return "❌  Please provide text to type."

        xdotool = self._which_first(["xdotool"])
        if xdotool:
            rc, _, err = self._run_cmd([xdotool, "type", "--delay", "1", text])
            if rc == 0:
                return f"✅  Typed text: {text}"
            if err:
                log.warning("xdotool typing failed: %s", err)

        if pyautogui is not None:
            pyautogui.write(text, interval=0.01)
            return f"✅  Typed text: {text}"

        return "❌  Typing failed. Install xdotool or pyautogui."

    def _automation_hotkey(self, command: Command) -> str:
        keys = (command.argument or "").strip()
        if not keys:
            return "❌  Please provide a hotkey (example: ctrl+c)."

        xdotool = self._which_first(["xdotool"])
        if xdotool:
            rc, _, err = self._run_cmd([xdotool, "key", keys])
            if rc == 0:
                return f"✅  Pressed keys: {keys}"
            if err:
                log.warning("xdotool hotkey failed: %s", err)

        if pyautogui is not None:
            try:
                pyautogui.hotkey(*[part.strip() for part in keys.split("+") if part.strip()])
                return f"✅  Pressed keys: {keys}"
            except Exception as exc:  # noqa: BLE001
                return f"❌  Could not press keys: {exc}"

        return "❌  Hotkey failed. Install xdotool or pyautogui."
