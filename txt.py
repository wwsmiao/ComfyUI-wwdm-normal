"""
Comfyui-wwdm-normal —— 文本文件批量读取节点集

功能概述：
    1. wwdm_TextFolder   ：输入文件夹路径，逐个读取文件夹内所有 txt 文本，
                           每个文件内容作为一个字符串，最终输出 STRING 列表。
    2. wwdm_TextFileList ：输入文件夹路径，输出文件夹内所有 txt 的文件路径列表。
    3. wwdm_TextJoin     ：把 STRING 列表连接成一个字符串。
    4. wwdm_TextTrimEach ：对 STRING 列表中的每一项做逐条处理（修剪/去空行/去重等）。

编码说明：
    读取时自动识别编码，顺序为 UTF-8(BOM) -> UTF-8 -> GBK/GB18030 -> UTF-16 -> Latin-1，
    带 errors="replace" 兜底，保证不会因为个别文件编码问题中断整个工作流。
"""

import os

# 支持的文本扩展名（小写）
TEXT_EXTS = {".txt", ".text", ".md", ".markdown", ".log", ".csv", ".json", ".yaml", ".yml"}

# 递归时需要跳过的系统/隐藏目录
SKIP_DIRS = {
    "__pycache__", ".git", ".svn", ".hg", ".idea", ".vscode",
    "node_modules", ".ipynb_checkpoints", "$RECYCLE.BIN", "System Volume Information",
}


# =========================================================================
# 内部工具函数
# =========================================================================
def _normalize_exts(extensions):
    """把用户填写的扩展名字符串整理成集合，例如 'txt, md' -> {'.txt', '.md'}

    返回空集合表示"不过滤扩展名"（用户填写了 * 或留空时的通配用法）。
    """
    raw = str(extensions or "").strip()
    exts = set()
    all_files = False
    for part in raw.replace(";", ",").replace("|", ",").split(","):
        part = part.strip().lower().lstrip("*").strip()
        if not part:
            if "*" in raw and not exts:
                all_files = True
            continue
        if not part.startswith("."):
            part = "." + part
        exts.add(part)

    if all_files or not raw:
        return set()
    return exts or {".txt"}


def _iter_files(folder, recursive=True, skip_hidden=True):
    """遍历文件夹，产出文件绝对路径（排序稳定）。"""
    if recursive:
        for root, dirs, files in os.walk(folder):
            if skip_hidden:
                dirs[:] = [
                    d for d in dirs
                    if d not in SKIP_DIRS and not (d.startswith(".") or d.startswith("~$"))
                ]
            for name in files:
                if skip_hidden and name.startswith("."):
                    continue
                yield os.path.join(root, name)
    else:
        for name in os.listdir(folder):
            if skip_hidden and name.startswith("."):
                continue
            full = os.path.join(folder, name)
            if os.path.isfile(full):
                yield full


def _collect_files(folder, extensions="txt", recursive=True, skip_hidden=True, sort_mode="name_asc"):
    """按扩展名收集文件列表。

    返回 (文件列表, 错误信息)。文件夹不存在时文件列表为空并返回错误信息。
    """
    folder = os.path.expanduser(os.path.expandvars(str(folder or "").strip().strip('"')))
    if not folder:
        return [], "文件夹路径为空"
    if not os.path.exists(folder):
        return [], "文件夹不存在: %s" % folder
    if not os.path.isdir(folder):
        return [], "不是文件夹: %s" % folder

    exts = _normalize_exts(extensions)
    all_files = [p for p in _iter_files(folder, recursive, skip_hidden)]
    if exts:
        files = [p for p in all_files if os.path.splitext(p)[1].lower() in exts]
    else:
        files = all_files

    def _name_key(p):
        return os.path.basename(p).lower()

    if sort_mode == "name_desc":
        files.sort(key=_name_key, reverse=True)
    elif sort_mode == "mtime_asc":
        files.sort(key=lambda p: (os.path.getmtime(p), _name_key(p)))
    elif sort_mode == "mtime_desc":
        files.sort(key=lambda p: (os.path.getmtime(p), _name_key(p)), reverse=True)
    elif sort_mode == "fullpath_asc":
        files.sort(key=lambda p: p.lower())
    elif sort_mode == "fullpath_desc":
        files.sort(key=lambda p: p.lower(), reverse=True)
    else:  # name_asc
        files.sort(key=_name_key)

    return files, ""


def _read_text_file(path):
    """读取单个文本文件，自动尝试常见编码，返回 (内容, 使用的编码)。"""
    with open(path, "rb") as f:
        raw = f.read()

    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig", errors="replace"), "utf-8-sig"
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16", errors="replace"), "utf-16"

    for enc in ("utf-8", "gb18030", "big5", "shift_jis"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue

    return raw.decode("utf-8", errors="replace"), "utf-8(replace)"


def _first(value, default=""):
    """INPUT_IS_LIST 场景下拿到单个值，而不是列表。"""
    if isinstance(value, (list, tuple)):
        return value[0] if len(value) > 0 else default
    return default if value is None else value


def _unescape(text):
    """把用户输入的 \\n \\t \\r \\\\ 转成真实字符，便于在单行输入框里写换行。"""
    out = []
    i = 0
    table = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\"}
    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text) and text[i + 1] in table:
            out.append(table[text[i + 1]])
            i += 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)


# =========================================================================
# 1. wwdm_TextFolder - 读取文件夹中的所有文本
# =========================================================================
class WWDMTextFolder:
    """
    文本文件夹读取节点

    功能说明：
        输入一个文件夹路径，逐个读取该文件夹（可选包含子文件夹）中的所有文本文件，
        每个文件的内容作为一个字符串，最后以 STRING 列表的形式输出。

    参数说明：
        folder_path : 文件夹路径，例如 E:\\ComfyUI\\input\\mytxts
                      支持 Windows 反斜杠或正斜杠，支持 %VAR% / ~ 展开。
        extensions  : 参与读取的扩展名，逗号分隔；填 "*" 表示读取所有文件。
                      默认 "txt" 表示只读取 .txt。
        recursive   : 是否递归读取子文件夹。
        sort_mode   : 文件排序方式（决定列表中字符串的顺序）。
                      name_asc / name_desc：按文件名
                      fullpath_asc / fullpath_desc：按完整路径
                      mtime_asc / mtime_desc：按修改时间
        encoding_mode : 输出编码处理方式。
                      auto     - 自动识别编码（推荐）
                      utf-8    - 强制 UTF-8
                      gb18030  - 强制 GB18030/GBK
                      utf-8-sig- 强制 UTF-8(BOM)
                      utf-16   - 强制 UTF-16
        strip_mode  : 文本修剪方式。
                      none    - 原样输出
                      rstrip  - 去除末尾空白（不含换行）
                      strip   - 去除首尾空白（含换行）
        normalize_newlines : 是否把 Windows 换行(\\r\\n)统一为 \\n。
        remove_empty: 是否跳过读取后内容为空的文件。
        skip_hidden : 是否跳过隐藏文件与系统目录（.git、__pycache__ 等）。
        max_files   : 最多读取的文件数量（0 = 不限制）。
        filename_in_list : 是否在文本前加上 "文件名: "，便于分辨来源。

    输出说明：
        texts     : STRING 列表，每个元素是一个文件的内容（启用 filename_in_list
                    时带有文件名前缀）。
        filenames : STRING 列表，每个元素的文件名。
        count     : INT，成功读取的文件数量。

    使用示例：
        示例1 - 读取文件夹内所有 txt：
            folder_path: "E:\\ComfyUI\\input\\prompts"
            texts 结果: ["第一个文件内容", "第二个文件内容", "第三个文件内容"]

        示例2 - 读取所有文件并按修改时间排序：
            folder_path: "D:\\data"  extensions: "*"  sort_mode: mtime_desc
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "folder_path": ("STRING", {"multiline": False, "default": ""}),
                "extensions": ("STRING", {"multiline": False, "default": "txt"}),
                "sort_mode": (
                    ["name_asc", "name_desc", "fullpath_asc", "fullpath_desc", "mtime_asc", "mtime_desc"],
                    {"default": "name_asc"},
                ),
            },
            "optional": {
                "recursive": ("BOOLEAN", {"default": False}),
                "encoding_mode": (
                    ["auto", "utf-8", "gb18030", "utf-8-sig", "utf-16"],
                    {"default": "auto"},
                ),
                "strip_mode": (["none", "rstrip", "strip"], {"default": "rstrip"}),
                "normalize_newlines": ("BOOLEAN", {"default": True}),
                "remove_empty": ("BOOLEAN", {"default": False}),
                "skip_hidden": ("BOOLEAN", {"default": True}),
                "max_files": ("INT", {"default": 0, "min": 0, "max": 100000, "step": 1}),
                "filename_in_list": ("BOOLEAN", {"default": False}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "INT")
    OUTPUT_IS_LIST = (True, True, False)
    RETURN_NAMES = ("texts", "filenames", "count")
    FUNCTION = "read_folder"
    CATEGORY = "wwdm-normal"
    DESCRIPTION = "读取文件夹中的所有文本文件，每个文件作为一个字符串，输出字符串列表。"

    def read_folder(
        self,
        folder_path,
        extensions="txt",
        sort_mode="name_asc",
        recursive=False,
        encoding_mode="auto",
        strip_mode="rstrip",
        normalize_newlines=True,
        remove_empty=False,
        skip_hidden=True,
        max_files=0,
        filename_in_list=False,
    ):
        files, error = _collect_files(
            folder_path,
            extensions=extensions,
            recursive=recursive,
            skip_hidden=skip_hidden,
            sort_mode=sort_mode,
        )

        if error:
            print("[Comfyui-wwdm-normal] %s" % error)
            return ([], [], 0)

        if not files:
            print("[Comfyui-wwdm-normal] 文件夹中未找到匹配的文件: %s" % folder_path)
            return ([], [], 0)

        if max_files and int(max_files) > 0:
            files = files[: int(max_files)]

        texts = []
        names = []
        failed = []

        for path in files:
            try:
                if encoding_mode == "auto":
                    content, used = _read_text_file(path)
                else:
                    with open(path, "r", encoding=encoding_mode, errors="replace") as f:
                        content = f.read()
                    used = encoding_mode
            except Exception as exc:  # 单个文件失败不影响整体
                failed.append("%s (%s)" % (path, exc))
                continue

            if normalize_newlines:
                content = content.replace("\r\n", "\n").replace("\r", "\n")

            if strip_mode == "strip":
                content = content.strip()
            elif strip_mode == "rstrip":
                content = content.rstrip()

            if remove_empty and not content.strip():
                continue

            name = os.path.basename(path)
            if filename_in_list:
                texts.append("%s: %s" % (name, content))
            else:
                texts.append(content)
            names.append(name)

        if failed:
            print("[Comfyui-wwdm-normal] 以下文件读取失败，已跳过：")
            for item in failed:
                print("    - %s" % item)

        print("[Comfyui-wwdm-normal] 已读取 %d/%d 个文件（目录: %s）" % (len(texts), len(files), folder_path))
        return (texts, names, len(texts))


# =========================================================================
# 2. wwdm_TextFileList - 文件路径列表
# =========================================================================
class WWDMTextFileList:
    """
    文本文件列表节点

    功能说明：
        输入文件夹路径，输出该文件夹内匹配文件的完整路径列表。
        适合与其它需要批量路径的节点配合使用。

    参数说明：
        folder_path : 文件夹路径（也可以直接填单个文件的路径）。
        extensions  : 参与筛选的扩展名，逗号分隔；"*" 表示所有文件。
        recursive   : 是否递归子文件夹。
        sort_mode   : 排序方式（同"文本文件夹读取"节点）。
        skip_hidden : 是否跳过隐藏文件与系统目录。
        max_files   : 最多输出数量（0 = 不限制）。

    输出说明：
        file_paths : STRING 列表，文件完整路径。
        count      : INT，文件数量。

    使用示例：
        示例1:
            folder_path: "E:\\ComfyUI\\input\\prompts"
            file_paths 结果: ["E:\\ComfyUI\\input\\prompts\\a.txt", "E:\\ComfyUI\\input\\prompts\\b.txt"]
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "folder_path": ("STRING", {"multiline": False, "default": ""}),
                "extensions": ("STRING", {"multiline": False, "default": "txt"}),
                "sort_mode": (
                    ["name_asc", "name_desc", "fullpath_asc", "fullpath_desc", "mtime_asc", "mtime_desc"],
                    {"default": "name_asc"},
                ),
            },
            "optional": {
                "recursive": ("BOOLEAN", {"default": False}),
                "skip_hidden": ("BOOLEAN", {"default": True}),
                "max_files": ("INT", {"default": 0, "min": 0, "max": 100000, "step": 1}),
            },
        }

    RETURN_TYPES = ("STRING", "INT")
    OUTPUT_IS_LIST = (True, False)
    RETURN_NAMES = ("file_paths", "count")
    FUNCTION = "list_files"
    CATEGORY = "wwdm-normal"
    DESCRIPTION = "列出文件夹中所有匹配的文本文件路径。"

    def list_files(
        self,
        folder_path,
        extensions="txt",
        sort_mode="name_asc",
        recursive=False,
        skip_hidden=True,
        max_files=0,
    ):
        path = os.path.expanduser(os.path.expandvars(str(folder_path or "").strip().strip('"')))

        if path and os.path.isfile(path):
            return ([path], 1)

        files, error = _collect_files(
            path,
            extensions=extensions,
            recursive=recursive,
            skip_hidden=skip_hidden,
            sort_mode=sort_mode,
        )

        if error:
            print("[Comfyui-wwdm-normal] %s" % error)
            return ([], 0)

        if max_files and int(max_files) > 0:
            files = files[: int(max_files)]

        return (files, len(files))


# =========================================================================
# 3. wwdm_TextJoin - 列表连接为字符串
# =========================================================================
class WWDMTextJoin:
    """
    文本列表连接节点

    功能说明：
        把上游输出的 STRING 列表按分隔符连接成一个字符串。
        常与"文本文件夹读取"节点配合，把多个文件内容合并成一段提示词。

    参数说明：
        texts     : STRING 列表输入。
        separator : 连接符，默认 "\\n\\n"（注：此处写 \\n 即为换行，可在界面直接输入真实换行）。
        prefix    : 连接结果的前缀。
        suffix    : 连接结果的后缀。
        skip_empty: 是否跳过空字符串。
        max_items : 最多参与连接的元素数量（0 = 不限制）。

    输出说明：
        text : STRING，连接后的字符串。

    使用示例：
        texts: ["A", "B", "C"]  separator: ", "
        结果: "A, B, C"
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "texts": ("STRING", {"forceInput": True, "INPUT_IS_LIST": True}),
                "separator": ("STRING", {"multiline": False, "default": "\n"}),
            },
            "optional": {
                "prefix": ("STRING", {"multiline": False, "default": ""}),
                "suffix": ("STRING", {"multiline": False, "default": ""}),
                "skip_empty": ("BOOLEAN", {"default": False}),
                "max_items": ("INT", {"default": 0, "min": 0, "max": 100000, "step": 1}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "join"
    CATEGORY = "wwdm-normal"
    DESCRIPTION = "把字符串列表连接成一个字符串。"

    def join(self, texts, separator="\n", prefix="", suffix="", skip_empty=False, max_items=0):
        items = list(texts) if isinstance(texts, (list, tuple)) else [texts]
        items = ["" if item is None else str(item) for item in items]

        if skip_empty:
            items = [item for item in items if item.strip()]

        limit = int(_first(max_items, 0) or 0)
        if limit > 0:
            items = items[:limit]

        sep = str(_first(separator, "\n"))
        pre = str(_first(prefix, ""))
        suf = str(_first(suffix, ""))

        return (pre + sep.join(items) + suf,)


# =========================================================================
# 3-1. wwdm_TextPairConcat - 两个字符串拼接
# =========================================================================
class WWDMTextPairConcat:
    """
    双字符串拼接节点

    功能说明：
        接收两个字符串，拼接输出：
          - 输出1 text  ：一个字符串，即 A 与 B 拼接后的结果；
          - 输出2 texts ：一个字符串列表，即 [A, B]（不拼接，按顺序分成两项）。

    参数说明：
        text_a        : 字符串 A（可连接上游 STRING；若上游是列表则取第一项）。
        text_b        : 字符串 B（同上）。
        connection    : A 与 B 之间的连接符，默认空字符串。
                        可直接写 \\n / \\t / \\r / \\\\ 表示换行、制表符等。
        trim          : 拼接前是否去除 A、B 各自的首尾空白。
        skip_empty    : 某一项为空时是否忽略它（只用另一项，不产生多余连接符）。
        uppercase_list: 列表输出是否转为大写。

    输出说明：
        text  : STRING，拼接结果。
        texts : STRING 列表，[A, B] 两项（受 trim / skip_empty / uppercase_list 影响）。

    使用示例：
        示例1 - 基础拼接：
            text_a: "Hello"  text_b: "World"  connection: " "
            text 结果: "Hello World"
            texts 结果: ["Hello", "World"]

        示例2 - 换行拼接：
            text_a: "第一行"  text_b: "第二行"  connection: "\\n"
            text 结果: "第一行\\n第二行"
            texts 结果: ["第一行", "第二行"]

        示例3 - 忽略空项：
            text_a: "只有这一句"  text_b: ""  connection: " | "  skip_empty: true
            text 结果: "只有这一句"
            texts 结果: ["只有这一句"]
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text_a": ("STRING", {"multiline": True, "default": ""}),
                "text_b": ("STRING", {"multiline": True, "default": ""}),
            },
            "optional": {
                "connection": ("STRING", {"multiline": False, "default": ""}),
                "trim": ("BOOLEAN", {"default": False}),
                "skip_empty": ("BOOLEAN", {"default": False}),
                "uppercase_list": ("BOOLEAN", {"default": False}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("text", "texts")
    OUTPUT_IS_LIST = (False, True)
    FUNCTION = "concat_pair"
    CATEGORY = "wwdm-normal"
    DESCRIPTION = "两个字符串拼接：输出一个字符串和一个字符串列表。"

    def concat_pair(
        self,
        text_a,
        text_b,
        connection="",
        trim=False,
        skip_empty=False,
        uppercase_list=False,
    ):
        a = "" if _first(text_a, "") is None else str(_first(text_a, ""))
        b = "" if _first(text_b, "") is None else str(_first(text_b, ""))

        if bool(_first(trim, False)):
            a = a.strip()
            b = b.strip()

        parts = [a, b]
        if bool(_first(skip_empty, False)):
            parts = [p for p in parts if p != ""]

        sep = _unescape(str(_first(connection, "")))
        joined = sep.join(parts)

        if bool(_first(uppercase_list, False)):
            parts = [p.upper() for p in parts]

        return (joined, parts)


# =========================================================================
# 4. wwdm_TextTrimEach - 列表逐条处理
# =========================================================================
class WWDMTextTrimEach:
    """
    文本列表逐条处理节点

    功能说明：
        对 STRING 列表中的每一个字符串单独做处理，输出处理后的列表。

    参数说明：
        texts : STRING 列表输入。
        mode  : 处理方式。
                strip          - 去除每项首尾空白
                rstrip         - 去除每项末尾空白
                collapse       - 把连续空白合并为单个空格
                strip_lines    - 每行去空白并移除空行
                remove_blank_lines - 仅移除空行
                none           - 不处理
        dedupe : 是否去除重复项（保留首次出现顺序）。
        remove_empty : 是否移除空字符串。

    输出说明：
        texts : STRING 列表，处理后的结果。
        count : INT，结果数量。

    使用示例：
        texts: ["  第一行  ", "", "第二行"]  mode: strip  remove_empty: true
        结果: ["第一行", "第二行"]
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "texts": ("STRING", {"forceInput": True, "INPUT_IS_LIST": True}),
                "mode": (
                    ["strip", "rstrip", "collapse", "strip_lines", "remove_blank_lines", "none"],
                    {"default": "strip"},
                ),
            },
            "optional": {
                "dedupe": ("BOOLEAN", {"default": False}),
                "remove_empty": ("BOOLEAN", {"default": False}),
            },
        }

    RETURN_TYPES = ("STRING", "INT")
    OUTPUT_IS_LIST = (True, False)
    RETURN_NAMES = ("texts", "count")
    FUNCTION = "process"
    CATEGORY = "wwdm-normal"
    DESCRIPTION = "对字符串列表中的每一项逐条处理。"

    def process(self, texts, mode="strip", dedupe=False, remove_empty=False):
        import re

        mode = str(_first(mode, "strip"))
        dedupe = bool(_first(dedupe, False))
        remove_empty = bool(_first(remove_empty, False))

        items = list(texts) if isinstance(texts, (list, tuple)) else [texts]
        result = []

        for item in items:
            text = "" if item is None else str(item)

            if mode == "strip":
                text = text.strip()
            elif mode == "rstrip":
                text = text.rstrip()
            elif mode == "collapse":
                text = re.sub(r"\s+", " ", text).strip()
            elif mode == "strip_lines":
                lines = [l.strip() for l in text.split("\n")]
                text = "\n".join([l for l in lines if l])
            elif mode == "remove_blank_lines":
                lines = text.split("\n")
                text = "\n".join([l for l in lines if l.strip()])

            if remove_empty and not text.strip():
                continue
            if dedupe and text in result:
                continue

            result.append(text)

        return (result, len(result))


# =========================================================================
# 5. wwdm_TextShow - 文本预览
# =========================================================================
class WWDMTextShow:
    """
    文本预览节点

    功能说明：
        接收字符串（或字符串列表），在控制台打印预览，并把原文原样向下传递，
        方便在调试工作流时查看文件夹读取结果。

    参数说明：
        text        : STRING 或 STRING 列表输入。
        max_chars   : 每条最多打印的字符数（0 = 不限制）。
        show_index  : 是否打印序号。

    输出说明：
        text : STRING 列表，原样输出（不做任何修改）。
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {"forceInput": True, "INPUT_IS_LIST": True}),
            },
            "optional": {
                "max_chars": ("INT", {"default": 200, "min": 0, "max": 100000, "step": 1}),
                "show_index": ("BOOLEAN", {"default": True}),
            },
        }

    RETURN_TYPES = ("STRING",)
    OUTPUT_IS_LIST = (True,)
    RETURN_NAMES = ("text",)
    FUNCTION = "preview"
    CATEGORY = "wwdm-normal"
    DESCRIPTION = "打印文本预览并原样传递。"

    def preview(self, text, max_chars=200, show_index=True):
        items = list(text) if isinstance(text, (list, tuple)) else [text]
        items = ["" if item is None else str(item) for item in items]

        limit = int(_first(max_chars, 200) or 0)
        indexed = bool(_first(show_index, True))

        print("[Comfyui-wwdm-normal] 共 %d 条文本：" % len(items))
        for i, item in enumerate(items):
            shown = item if limit <= 0 or len(item) <= limit else item[:limit] + " ...<已截断>"
            tag = "[%d] " % i if indexed else ""
            print("    %s%s" % (tag, shown.replace("\n", "\\n")))

        return (items,)
