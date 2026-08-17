#!/usr/bin/env python3
"""Fail-fast startup smoke test for an onedir Mantella executable.

This intentionally tests the packaged bootstrap, not source imports.  The
working directory must contain the executable's ``_internal`` directory and a
representative config.ini/custom_user_folder.ini.
"""

from __future__ import annotations

import argparse
import shutil
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen
from urllib.request import Request
import json


FAILURE_MARKERS = (
    "Traceback (most recent call last)",
    "ModuleNotFoundError",
    "ImportError",
    "FileNotFoundError",
    "DLL load failed",
    "Unable to load", 
)


def _ready(url: str) -> bool:
    try:
        with urlopen(url, timeout=1) as response:
            return response.status < 500
    except (OSError, URLError):
        return False


def _terminate(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", required=True, type=Path)
    parser.add_argument("--working-dir", type=Path)
    parser.add_argument("--config-template", type=Path)
    parser.add_argument("--user-folder", type=Path)
    parser.add_argument("--ready-url", default="http://127.0.0.1:4999/ui")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument(
        "--probe-mantella-init",
        action="store_true",
        help="POST the real /mantella initialize route after UI readiness.",
    )
    parser.add_argument(
        "--probe-conversation-start",
        action="store_true",
        help="Start an isolated microphone conversation after route initialization; exercises Transcriber and Silero VAD.",
    )
    args = parser.parse_args()

    exe = args.exe.resolve()
    workdir = (args.working_dir or exe.parent).resolve()
    if not exe.is_file():
        print(f"FAIL packaged startup: executable not found: {exe}", file=sys.stderr)
        return 2
    if not (workdir / "_internal").is_dir():
        print(f"FAIL packaged startup: missing _internal beside {exe}", file=sys.stderr)
        return 2

    config_path = workdir / "config.ini"
    config_backup = workdir / "config.ini.packaged-smoke-backup"
    user_folder_path = workdir / "custom_user_folder.ini"
    user_folder_backup = workdir / "custom_user_folder.ini.packaged-smoke-backup"
    isolated_config_path: Path | None = None
    isolated_config_backup: Path | None = None
    if args.config_template:
        if not args.config_template.is_file():
            print(f"FAIL packaged startup: config template not found: {args.config_template}", file=sys.stderr)
            return 2
        if config_path.exists():
            shutil.copy2(config_path, config_backup)
        shutil.copy2(args.config_template, config_path)
    elif not config_path.exists():
        print(f"FAIL packaged startup: missing config.ini in {workdir}", file=sys.stderr)
        return 2
    if args.user_folder:
        args.user_folder.mkdir(parents=True, exist_ok=True)
        isolated_config_path = args.user_folder / "config.ini"
        isolated_config_backup = args.user_folder / "config.ini.packaged-smoke-backup"
        if args.config_template:
            if isolated_config_path.exists():
                shutil.copy2(isolated_config_path, isolated_config_backup)
            shutil.copy2(args.config_template, isolated_config_path)
        if user_folder_path.exists():
            shutil.copy2(user_folder_path, user_folder_backup)
        user_folder_path.write_text(
            "[UserFolder]\ncustom_user_folder = " + str(args.user_folder) + "\n",
            encoding="utf-8",
        )

    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    stdout_path = Path(tempfile.mkstemp(prefix="mantella-smoke-out-", suffix=".log")[1])
    stderr_path = Path(tempfile.mkstemp(prefix="mantella-smoke-err-", suffix=".log")[1])
    stdout_file = stdout_path.open("w", encoding="utf-8", errors="replace")
    stderr_file = stderr_path.open("w", encoding="utf-8", errors="replace")
    process = subprocess.Popen(
        [str(exe)], cwd=workdir, stdout=stdout_file, stderr=stderr_file,
        creationflags=creationflags, start_new_session=(os.name != "nt"),
    )
    deadline = time.monotonic() + args.timeout
    success = False
    failure_message = ""
    try:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                stdout_file.flush(); stderr_file.flush()
                output = stdout_path.read_text(errors="replace") + "\n" + stderr_path.read_text(errors="replace")
                print(output, end="")
                failure_message = f"FAIL packaged startup: exited early with code {process.returncode}"
                break
            if _ready(args.ready_url):
                print(f"PASS packaged startup: ready at {args.ready_url}")
                if args.probe_mantella_init:
                    request = Request(
                        args.ready_url.rsplit("/ui", 1)[0] + "/mantella",
                        data=json.dumps({"mantella_request_type": "mantella_initialize"}).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    try:
                        with urlopen(request, timeout=20) as response:
                            body = json.loads(response.read().decode("utf-8"))
                        if body.get("mantella_reply_type") != "mantella_init_completed":
                            raise RuntimeError(f"unexpected initialize response: {body}")
                        print("PASS packaged Mantella initialization / tokenizer probe")
                        if args.probe_conversation_start:
                            start_body = {
                                "mantella_request_type": "mantella_start_conversation",
                                "mantella_worldid": "PackagedSmoke",
                                "mantella_input_type": "mantella_mic_input",
                                "mantella_actors": [
                                    {
                                        "mantella_actor_baseid": 0,
                                        "mantella_actor_refid": 0,
                                        "mantella_actor_name": "Prisoner",
                                        "mantella_actor_gender": 0,
                                        "mantella_actor_race": "[Race <NordRace (00013746)>]",
                                        "mantella_actor_is_player": True,
                                        "mantella_actor_relationshiprank": 0,
                                        "mantella_actor_voicetype": "[VoiceType <MaleEvenToned (00013AD2)>]",
                                        "mantella_actor_is_in_combat": False,
                                        "mantella_actor_is_enemy": False,
                                        "mantella_actor_custom_values": {"mantella_actor_pc_description": "", "mantella_actor_pc_voiceplayerinput": False},
                                        "mantella_equipment": {},
                                    },
                                    {
                                        "mantella_actor_baseid": 0,
                                        "mantella_actor_refid": 0,
                                        "mantella_actor_name": "Guard",
                                        "mantella_actor_gender": 0,
                                        "mantella_actor_race": "[Race <ImperialRace (00013744)>]",
                                        "mantella_actor_is_player": False,
                                        "mantella_actor_relationshiprank": 0,
                                        "mantella_actor_voicetype": "[VoiceType <MaleEvenToned (00013AD2)>]",
                                        "mantella_actor_is_in_combat": False,
                                        "mantella_actor_is_enemy": False,
                                        "mantella_actor_custom_values": None,
                                        "mantella_equipment": {},
                                    },
                                ],
                                "mantella_context": {"mantella_context_location": "Skyrim", "mantella_context_time": 12, "mantella_context_ingame_events": []},
                            }
                            start_request = Request(
                                args.ready_url.rsplit("/ui", 1)[0] + "/mantella",
                                data=json.dumps(start_body).encode("utf-8"),
                                headers={"Content-Type": "application/json"},
                                method="POST",
                            )
                            with urlopen(start_request, timeout=20) as response:
                                start_response = json.loads(response.read().decode("utf-8"))
                            if start_response.get("mantella_reply_type") != "mantella_start_conversation_completed":
                                raise RuntimeError(f"unexpected conversation-start response: {start_response}")
                            print("PASS packaged conversation-start / STT-VAD probe")
                    except Exception as exc:
                        failure_message = f"FAIL packaged Mantella initialization probe: {exc}"
                        break
                success = True
                break
            time.sleep(0.2)
        else:
            failure_message = f"FAIL packaged startup: readiness timeout ({args.ready_url})"
    finally:
        if args.config_template:
            if config_backup.exists():
                shutil.move(config_backup, config_path)
            else:
                config_path.unlink(missing_ok=True)
        if args.user_folder:
            if user_folder_backup.exists():
                shutil.move(user_folder_backup, user_folder_path)
            else:
                user_folder_path.unlink(missing_ok=True)
            if isolated_config_path is not None:
                if isolated_config_backup is not None and isolated_config_backup.exists():
                    shutil.move(isolated_config_backup, isolated_config_path)
                elif args.config_template:
                    isolated_config_path.unlink(missing_ok=True)
        _terminate(process)
        stdout_file.close(); stderr_file.close()
        output = stdout_path.read_text(errors="replace") + "\n" + stderr_path.read_text(errors="replace")
        for log_path in (stdout_path, stderr_path):
            try:
                log_path.unlink(missing_ok=True)
            except PermissionError:
                # A short-lived child may still hold an inherited handle. The
                # process tree has already been terminated; retain the log
                # rather than turning successful readiness into a harness
                # crash.
                pass
        if any(marker in output for marker in FAILURE_MARKERS):
            print(output, end="")
            success = False
            failure_message = "FAIL packaged startup: packaged process reported an unhandled runtime error"
    if not success:
        print(failure_message, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
