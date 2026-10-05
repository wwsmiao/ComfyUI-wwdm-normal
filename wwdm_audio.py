"""
Comfyui-wwdm-normal —— 音频播放辅助模块

职责：
    1. 从节点输入里解析出音频文件路径（支持字符串、字典、AUDIO 对象等任意输入）。
    2. 调用系统播放器播放该音频文件（Windows / macOS / Linux）。
    3. 提供"只解析不播放"的试运行开关（环境变量 WWDM_AUDIO_NO_PLAY=1），便于自动化测试。

设计说明：
    本模块只在被调用时才导入，避免影响插件其它节点的加载。
    所有外部命令都通过参数列表/环境变量传递路径，不做字符串拼接，避免引号与特殊字符问题。
"""

import os
import shutil
import subprocess
import sys
import time
import wave

# 支持的音频扩展名
AUDIO_EXTS = {
    ".mp3", ".wav", ".flac", ".ogg", ".oga", ".m4a", ".aac", ".wma",
    ".opus", ".aiff", ".aif", ".ape", ".mid", ".midi", ".mp4", ".mkv",
}

# 常见音频目录（用户只给文件名时去这些目录里找）
DEFAULT_SEARCH_DIRS = [
    r"C:\Windows\Media",
    os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Media"),
    os.path.expanduser(r"~\Music"),
    os.path.expanduser(r"~\音乐"),
]


def normalize_path(raw):
    """把用户输入整理成干净的文件路径。"""
    if raw is None:
        return ""
    text = str(raw).strip()
    text = text.strip().strip("\u200b")
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):
        text = text[1:-1].strip()
    text = os.path.expandvars(text)
    text = os.path.expanduser(text)
    return text


def resolve_audio_path(raw, search_dirs=None):
    """解析音频路径。

    返回 (绝对路径, 错误信息)。找不到时绝对路径为空字符串。
    """
    text = normalize_path(raw)
    if not text:
        return "", "音频路径为空"

    if os.path.isfile(text):
        return os.path.abspath(text), ""

    if os.path.isdir(text):
        return "", "这是一个文件夹，不是音频文件: %s" % text

    # 只有文件名时，去常见音频目录里找
    if os.sep not in text and "/" not in text:
        for directory in (search_dirs or DEFAULT_SEARCH_DIRS):
            if not directory:
                continue
            candidate = os.path.join(directory, text)
            if os.path.isfile(candidate):
                return os.path.abspath(candidate), ""

    return "", "找不到音频文件: %s" % text


def extract_path_from_input(value, depth=0):
    """从任意类型的输入里尽力提取音频路径字符串。

    支持：str / os.PathLike / dict(含 path、audio_path、filename、file 等键) /
          ComfyUI 的 AUDIO 对象（{"waveform":..., "sample_rate":...} 或带 path 属性）。
    提取不到时返回 None。
    """
    if value is None or depth > 3:
        return None

    if isinstance(value, (str, os.PathLike)):
        text = normalize_path(value)
        return text or None

    if isinstance(value, dict):
        for key in ("path", "audio_path", "file", "filepath", "filename", "source", "audio"):
            if key in value:
                found = extract_path_from_input(value[key], depth + 1)
                if found:
                    return found
        return None

    if isinstance(value, (list, tuple)):
        for item in value:
            found = extract_path_from_input(item, depth + 1)
            if found:
                return found
        return None

    # 对象：常见属性
    for attr in ("path", "audio_path", "file_path", "filename", "source"):
        if hasattr(value, attr):
            found = extract_path_from_input(getattr(value, attr), depth + 1)
            if found:
                return found

    return None


def wav_duration(path):
    """WAV 文件时长（秒）；其它格式或读取失败返回 None。"""
    try:
        with wave.open(path, "rb") as handle:
            frames = handle.getnframes()
            rate = handle.getframerate() or 1
            return frames / float(rate)
    except Exception:
        return None


# Windows 播放脚本：优先 WMP COM（支持 mp3/wav/wma 等，可设音量/速度），
# 失败则退回 .NET SoundPlayer（仅 wav）。路径/音量/速度通过环境变量传入。
WINDOWS_PLAYER_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$f = $env:WWDM_AUDIO_FILE
if (-not (Test-Path -LiteralPath $f)) { Write-Error ('file not found: ' + $f); exit 2 }

$played = $false
try {
    $w = New-Object -ComObject WMPlayer.OCX
    $w.settings.volume = [int]$env:WWDM_AUDIO_VOLUME
    $w.settings.rate = [double]$env:WWDM_AUDIO_SPEED
    $m = $w.newMedia($f)
    $w.currentMedia = $m
    $w.controls.play()
    Start-Sleep -Milliseconds 400

    # playState: 3 = 正常播放中，8 = 媒体结束（说明确实播放过），有 duration 说明能识别该文件
    $state = [int]$w.playState
    $duration = 0.0
    try { $duration = [double]$w.currentMedia.duration } catch { $duration = 0.0 }

    if ($state -eq 3 -or $state -eq 8) {
        if ($env:WWDM_AUDIO_WAIT -eq '1' -and $state -eq 3) {
            # 等待播放自然结束（父进程超时会结束本进程，不影响）
            while ([int]$w.playState -eq 3) { Start-Sleep -Milliseconds 150 }
        }
        $played = $true
    }
    try { $w.controls.stop() } catch { }
    try { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($w) } catch { }
} catch {
    $played = $false
}

if (-not $played -and $env:WWDM_AUDIO_ISWAV -eq '1') {
    try {
        $p = New-Object System.Media.SoundPlayer $f
        $p.PlaySync()
        $played = $true
    } catch {
        $played = $false
    }
}

if (-not $played) { Write-Error 'no available windows audio backend'; exit 3 }
"""


def build_player_command(path, volume=1.0, speed=1.0):
    """构造系统播放命令。

    返回 (命令列表, 额外信息 dict)。命令不可用时返回 (None, {"error": 原因})。
    路径通过参数/环境变量传入，不做 shell 字符串拼接。
    """
    volume = max(0.0, min(1.0, float(volume)))
    speed = max(0.1, min(4.0, float(speed)))

    if sys.platform.startswith("win"):
        powershell = shutil.which("powershell") or shutil.which("pwsh")
        if not powershell:
            return None, {"error": "系统里找不到 powershell，无法播放音频"}
        return [powershell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                "-Command", WINDOWS_PLAYER_SCRIPT], {"mode": "windows", "path": path}

    if sys.platform == "darwin":
        player = shutil.which("afplay")
        if not player:
            return None, {"error": "系统里找不到 afplay，无法播放音频"}
        return [player, "-v", "%.3f" % volume, "-r", "%.3f" % speed, path], {"mode": "darwin"}

    # Linux / 其它：按可用性依次尝试
    for name in ("paplay", "aplay", "ffplay", "mpv", "cvlc", "play"):
        player = shutil.which(name)
        if not player:
            continue
        if name == "paplay":
            return [player, "--volume=%d" % int(volume * 65536), path], {"mode": name}
        if name == "aplay":
            return [player, "-q", path], {"mode": name}
        if name == "ffplay":
            return [player, "-nodisp", "-autoexit", "-loglevel", "error",
                    "-af", "volume=%.3f" % volume, "-filter:a", "atempo=%.3f" % speed, path], {"mode": name}
        if name == "mpv":
            return [player, "--no-video", "--volume=%d" % int(volume * 100), path], {"mode": name}
        if name == "cvlc":
            return [player, "--play-and-exit", "--intf", "dummy", path], {"mode": name}
        if name == "play":
            return [player, "-q", path], {"mode": name}

    return None, {"error": "系统里找不到可用的音频播放器（paplay/aplay/ffplay/mpv/cvlc/play 都没有）"}


def _short_error(raw, lines=2):
    """把播放器的报错压成一行，避免 PowerShell 把整段脚本和堆栈回显出来。"""
    text = str(raw or "")
    if not text.strip():
        return "未知错误"

    # 优先取脚本自己写的可读错误（-ErrorAction Stop 会保留原文）
    for marker in ("no available windows audio backend", "file not found:"):
        if marker in text:
            return "%s: %s" % (marker, marker)

    interesting = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(("$", "if (", "try", "}", "catch", "Start-Sleep", "while (",
                            "$ErrorActionPreference", "Write-Error", "+", "At line", "所在位置")):
            continue
        interesting.append(line)

    if interesting:
        return " / ".join(interesting[-lines:])[:200]
    return "未知错误（播放器未返回可读信息）"


def play_audio(path, volume=1.0, speed=1.0, wait=False, timeout=None):
    """播放音频文件。

    返回 (是否成功, 说明信息)。
    wait=True 时等待播放结束；timeout 为最长等待秒数（None 表示不限制）。
    """
    if os.environ.get("WWDM_AUDIO_NO_PLAY") == "1":
        cmd, _extra = build_player_command(path, volume, speed)
        if cmd is None:
            return False, _extra.get("error", "无法构造播放命令")
        return True, "[试运行] 未实际播放，命令: %s" % " ".join(cmd[:2] + ["..."])

    if not os.path.isfile(path):
        return False, "文件不存在: %s" % path

    cmd, extra = build_player_command(path, volume, speed)
    if cmd is None:
        return False, extra.get("error", "无法构造播放命令")

    env = os.environ.copy()
    if sys.platform.startswith("win"):
        env["WWDM_AUDIO_FILE"] = path
        env["WWDM_AUDIO_VOLUME"] = str(int(max(0.0, min(1.0, float(volume))) * 100))
        env["WWDM_AUDIO_SPEED"] = "%.3f" % max(0.1, min(4.0, float(speed)))
        env["WWDM_AUDIO_ISWAV"] = "1" if path.lower().endswith(".wav") else "0"
        env["WWDM_AUDIO_WAIT"] = "1" if wait else "0"

    try:
        if wait:
            proc = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            limit = timeout if timeout else None
            try:
                proc.wait(timeout=limit)
            except subprocess.TimeoutExpired:
                proc.terminate()
                return True, "已播放（达到最大时长 %s 秒后停止）" % timeout

            if proc.returncode == 0:
                return True, "播放完成"

            if proc.returncode == 2:
                return False, "文件不存在: %s" % path

            err = _short_error((proc.stderr.read() or b"").decode("utf-8", "replace"))
            if "no available windows audio backend" in err:
                return False, "系统播放器无法播放该文件（格式不支持或文件损坏）: %s" % path
            return False, "播放失败（退出码 %s）: %s" % (proc.returncode, err)

        subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
        return True, "已开始播放（后台模式）"
    except Exception as exc:
        return False, "播放出错: %s" % exc


def play_audio_node(path, volume=1.0, speed=1.0, wait_mode="wait", play_count=1, max_seconds=0):
    """供节点调用：按次数播放，返回 (成功次数, 日志行列表)。"""
    logs = []
    success = 0
    count = max(1, int(play_count or 1))
    duration = wav_duration(path)

    for index in range(count):
        timeout = float(max_seconds) if max_seconds and max_seconds > 0 else None
        if timeout is None and wait_mode == "wait" and duration:
            timeout = duration + 3.0  # 兜底：避免异常情况下永久阻塞

        ok, message = play_audio(
            path,
            volume=volume,
            speed=speed,
            wait=(wait_mode == "wait"),
            timeout=timeout,
        )
        logs.append("第 %d/%d 次: %s" % (index + 1, count, message))
        if ok:
            success += 1
        else:
            break  # 播放失败就不再重复
        if wait_mode == "wait" and count > 1:
            time.sleep(0.1)

    return success, logs
