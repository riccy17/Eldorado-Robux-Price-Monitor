"""Alert delivery helpers."""

from __future__ import annotations

import subprocess
import sys
import urllib.parse
import urllib.request

from .config import MonitorConfig, resolve_alarm_path, resolved_telegram_credentials


def play_alert_sound(config: MonitorConfig, sound_debug: bool = False) -> None:
    if not config.sound_enabled:
        return

    sound_path = resolve_alarm_path(config.sound_file)
    if sound_path is None:
        print("Sound alert skipped: no supported audio file was found in alarm/.")
        return

    try:
        if sys.platform == "win32":
            volume = max(0, min(100, int(config.alert_volume)))
            sound_uri = sound_path.resolve().as_uri().replace("'", "''")
            powershell_command = (
                "Add-Type -AssemblyName PresentationCore; "
                f"$player=New-Object System.Windows.Media.MediaPlayer; $player.Volume={volume}/100; "
                f"$player.Open([Uri]'{sound_uri}'); $player.Play(); "
                "$tries=0; "
                "while (-not $player.NaturalDuration.HasTimeSpan -and $tries -lt 50) { Start-Sleep -Milliseconds 100; $tries++ }; "
                "if ($player.NaturalDuration.HasTimeSpan) { Start-Sleep -Milliseconds $player.NaturalDuration.TimeSpan.TotalMilliseconds } else { Start-Sleep -Seconds 5 }"
            )
            command = [
                "powershell",
                "-NoProfile",
                "-STA",
                "-WindowStyle",
                "Hidden",
                "-Command",
                powershell_command,
            ]
            if sound_debug:
                result = subprocess.run(command, capture_output=True, text=True, check=False)
                if result.stdout:
                    print(result.stdout.strip())
                if result.stderr:
                    print(result.stderr.strip())
            else:
                subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return

        if sys.platform == "darwin":
            subprocess.run(["afplay", str(sound_path)], check=False)
            return

        for command in (["paplay", str(sound_path)], ["aplay", str(sound_path)]):
            try:
                subprocess.run(command, check=False)
                return
            except FileNotFoundError:
                continue
        print("Sound alert skipped: no supported Linux audio player was found (tried paplay and aplay).")
    except Exception as exc:
        print(f"Sound playback failed: {exc}")


def send_telegram_message(config: MonitorConfig, message: str) -> None:
    if not config.telegram.enabled:
        return

    bot_token, chat_id = resolved_telegram_credentials(config)
    if not bot_token or not chat_id:
        print("Telegram alert skipped: bot token or chat ID is not configured.")
        return

    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = urllib.parse.urlencode(
            {
                "chat_id": chat_id,
                "text": message,
                "disable_web_page_preview": True,
            }
        ).encode("utf-8")
        request = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(request, timeout=config.telegram.timeout_seconds) as response:
            response.read()
    except Exception as exc:
        print(f"Telegram send failed: {exc}")
