"""
Comfyui-wwdm-normal —— 视频处理辅助模块

职责：
    1. 从任意输入里解析出视频文件路径（字符串 / VIDEO 对象 / 字典 / 列表）。
    2. 取视频的最后一帧（优先用 PyAV，必要时退回 ffmpeg 命令行）。
    3. 读取视频基础信息（编码、分辨率、帧率、时长、总帧数）。

设计说明：
    所有重依赖（av / numpy / torch / ffmpeg）都在函数内部按需导入与调用，
    保证插件在缺少某个依赖时只是该节点报错，而不是整个插件加载失败。
"""

import io
import os
import shutil
import subprocess
import tempfile

# 支持的视频扩展名
VIDEO_EXTS = {
    ".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".wmv", ".m4v",
    ".mpg", ".mpeg", ".ts", ".m2ts", ".mts", ".3gp", ".ogv", ".gif",
}

# 用户只给文件名时，去这些目录里找
DEFAULT_SEARCH_DIRS = [
    os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Videos"),
    os.path.expanduser(r"~\Videos"),
    os.path.expanduser(r"~\视频"),
]


def normalize_path(raw):
    """把用户输入整理成干净的文件路径。"""
    if raw is None:
        return ""
    text = str(raw).strip().strip("\u200b")
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):
        text = text[1:-1].strip()
    return os.path.expanduser(os.path.expandvars(text))


def resolve_video_path(raw, search_dirs=None):
    """解析视频文件路径，返回 (绝对路径, 错误信息)。"""
    text = normalize_path(raw)
    if not text:
        return "", "视频路径为空"

    if os.path.isfile(text):
        return os.path.abspath(text), ""
    if os.path.isdir(text):
        return "", "这是一个文件夹，不是视频文件: %s" % text

    candidates = []
    # 相对路径：相对 ComfyUI 的 input 目录
    try:
        import folder_paths
        candidates.append(os.path.join(folder_paths.get_input_directory(), text))
        candidates.append(os.path.join(folder_paths.get_output_directory(), text))
    except Exception:
        pass

    for directory in (search_dirs or DEFAULT_SEARCH_DIRS):
        if directory:
            candidates.append(os.path.join(directory, text))

    for candidate in candidates:
        if os.path.isfile(candidate):
            return os.path.abspath(candidate), ""

    return "", "找不到视频文件: %s" % text


def extract_path_from_input(value, depth=0):
    """从任意输入里尽力提取视频路径（或 VIDEO 对象的文件来源）。"""
    if value is None or depth > 3:
        return None

    if isinstance(value, (str, os.PathLike)):
        text = normalize_path(value)
        return text or None

    # VIDEO 对象：拿它的底层文件来源
    if hasattr(value, "get_stream_source"):
        try:
            source = value.get_stream_source()
        except Exception:
            source = None
        if isinstance(source, (str, os.PathLike)):
            return str(source)
        if isinstance(source, io.BytesIO):
            return source  # 交给读取函数落临时文件
        return None

    if isinstance(value, dict):
        for key in ("path", "video_path", "file", "filepath", "filename", "source", "video"):
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

    for attr in ("path", "video_path", "file_path", "filename", "source"):
        if hasattr(value, attr):
            found = extract_path_from_input(getattr(value, attr), depth + 1)
            if found:
                return found

    return None


def _materialize_source(source):
    """把 BytesIO 之类的内存视频落成临时文件，返回 (可打开的路径或源, 临时文件路径或 None)。"""
    if isinstance(source, io.BytesIO):
        handle = tempfile.NamedTemporaryFile(prefix="wwdm_video_", suffix=".mp4", delete=False)
        source.seek(0)
        handle.write(source.read())
        handle.close()
        return handle.name, handle.name
    return source, None


def get_video_info(path_or_source, timeout=None):
    """读取视频基础信息，返回 dict（失败时只填得出多少填多少）。"""
    import av

    source, tmp = _materialize_source(path_or_source)
    info = {"filename": os.path.basename(str(source))}
    try:
        kwargs = {}
        if timeout:
            kwargs["timeout"] = float(timeout)
        with av.open(source, mode="r", **kwargs) as container:
            stream = container.streams.video[0] if container.streams.video else None
            if stream is not None:
                info["codec"] = stream.codec.canonical_name if stream.codec else ""
                info["width"] = int(stream.width or 0)
                info["height"] = int(stream.height or 0)
                if stream.average_rate:
                    info["fps"] = float(stream.average_rate)
                if stream.frames:
                    info["total_frames"] = int(stream.frames)
            if container.duration:
                info["duration"] = float(container.duration) / float(av.time_base)
            if container.format and container.format.name:
                info["format"] = container.format.name
    finally:
        if tmp:
            try:
                os.remove(tmp)
            except OSError:
                pass
    return info


def _last_frame_pyav(source, end_time=None, timeout=None):
    """用 PyAV 取最后一帧，返回 (h, w, 3) 的 uint8 numpy 数组。

    end_time 不为 None 时，表示只在该时间点之前取（用于 VIDEO 对象的裁剪区间）。
    """
    import av
    import numpy as np

    kwargs = {}
    if timeout:
        kwargs["timeout"] = float(timeout)

    last = None
    with av.open(source, mode="r", **kwargs) as container:
        if not container.streams.video:
            raise ValueError("文件里没有视频流")

        # 先跳到接近结尾的位置，再从那里顺序解码到结束，取最后一帧
        if end_time is not None and end_time > 0:
            try:
                container.seek(int(end_time * av.time_base), backward=True)
            except Exception:
                pass

        for frame in container.decode(video=0):
            if end_time is not None and frame.time is not None and frame.time > end_time + 0.5:
                break
            last = frame

    if last is None:
        raise ValueError("没有解出任何视频帧")

    return np.asarray(last.to_image())


def _last_frame_ffmpeg(path, timeout=None):
    """用 ffmpeg 抓最后一帧（PyAV 解码失败时的兜底），返回 (h, w, 3) uint8 数组。"""
    import numpy as np

    exe = shutil.which("ffmpeg")
    if not exe:
        raise RuntimeError("系统里没有 ffmpeg，无法兜底解码该视频")

    with tempfile.TemporaryDirectory(prefix="wwdm_lastframe_") as tmp_dir:
        out_pattern = os.path.join(tmp_dir, "last_%06d.png")
        # 从结尾往前 3 秒开始抓帧，最多输出 30 张，取最后一张即"最后一帧"
        # 注意：不要用 -vsync（新版 ffmpeg 已移除该选项）
        cmd = [exe, "-hide_banner", "-loglevel", "error", "-y", "-sseof", "-3",
               "-i", path, "-frames:v", "30", out_pattern]
        try:
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  timeout=timeout or 300)
        except subprocess.TimeoutExpired:
            raise RuntimeError("ffmpeg 解码超时")

        files = sorted(f for f in os.listdir(tmp_dir) if f.endswith(".png"))
        if not files:
            # 极短视频可能落在 -3s 之前，退回整段解码（限制输出帧数）
            cmd = [exe, "-hide_banner", "-loglevel", "error", "-y",
                   "-i", path, "-frames:v", "100000", out_pattern]
            try:
                proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      timeout=timeout or 300)
            except subprocess.TimeoutExpired:
                raise RuntimeError("ffmpeg 解码超时")
            files = sorted(f for f in os.listdir(tmp_dir) if f.endswith(".png"))

        if not files:
            err = (proc.stderr or b"").decode("utf-8", "replace").strip()
            raise RuntimeError("ffmpeg 未取出帧: %s" % (err[:300] or "未知错误"))

        from PIL import Image
        with Image.open(os.path.join(tmp_dir, files[-1])) as img:
            return np.asarray(img.convert("RGB"))


def read_last_frame(path_or_source, end_time=None, timeout=None, decoder="auto"):
    """读取视频最后一帧。

    返回 (image_tensor[1,H,W,C] float32 0-1, 使用的解码器名称)。
    decoder: auto / pyav / ffmpeg
    """
    import numpy as np
    import torch

    source, tmp = _materialize_source(path_or_source)
    errors = []
    array = None
    used = ""

    try:
        if decoder in ("auto", "pyav"):
            try:
                array = _last_frame_pyav(source, end_time=end_time, timeout=timeout)
                used = "pyav"
            except Exception as exc:
                errors.append("PyAV: %s" % exc)

        need_ffmpeg = array is None and decoder in ("auto", "ffmpeg")
        if need_ffmpeg and isinstance(source, str) and os.path.isfile(source):
            try:
                array = _last_frame_ffmpeg(source, timeout=timeout)
                used = "ffmpeg"
            except Exception as exc:
                errors.append("ffmpeg: %s" % exc)

        if array is None:
            raise RuntimeError("；".join(errors) or "无法解码该视频")

        if array.ndim == 2:  # 灰度图补成三通道
            array = np.stack([array] * 3, axis=-1)
        elif array.ndim == 3 and array.shape[2] == 4:  # 带 alpha 的视频
            array = array[:, :, :3]

        tensor = torch.from_numpy(array.astype(np.float32) / 255.0)[None,]
        return tensor, used
    finally:
        if tmp:
            try:
                os.remove(tmp)
            except OSError:
                pass
