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
import re

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


def _natural_key(text):
    """自然排序键：把字符串中的数字段按数值比较。

    例如 ["1.png", "2.jpg", "10.png"] -> 1, 2, 10（而不是字符串排序的 1, 10, 2）。

    实现要点：键固定为 (文本, 数字, 文本, 数字) 四元组，保证同一位置类型一致
    （str 对 str、int 对 int），否则 Python 比较混合类型会得到错误的顺序。
    """
    chunks = re.split(r"(\d+)", str(text).lower())
    texts = chunks[0::2]      # 第 0、2、... 段是文本
    numbers = chunks[1::2]    # 第 1、3、... 段是数字
    texts += [""] * (2 - len(texts))
    numbers += [""] * (2 - len(numbers))
    return (texts[0], int(numbers[0]) if numbers[0] else 0, texts[1], int(numbers[1]) if numbers[1] else 0)


def _collect_files(folder, extensions="txt", recursive=True, skip_hidden=True, sort_mode="name_natural"):
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
        return os.path.basename(p)

    def _path_key(p):
        return p

    if sort_mode == "name_desc":
        files.sort(key=_name_key, reverse=True)
    elif sort_mode == "name_natural":
        files.sort(key=lambda p: _natural_key(_name_key(p)))
    elif sort_mode == "mtime_asc":
        files.sort(key=lambda p: (os.path.getmtime(p), _natural_key(_name_key(p))))
    elif sort_mode == "mtime_desc":
        files.sort(key=lambda p: (os.path.getmtime(p), _natural_key(_name_key(p))), reverse=True)
    elif sort_mode == "fullpath_asc":
        files.sort(key=lambda p: _path_key(p).lower())
    elif sort_mode == "fullpath_desc":
        files.sort(key=lambda p: _path_key(p).lower(), reverse=True)
    else:  # name_asc
        files.sort(key=lambda p: _name_key(p).lower())

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
                      name_asc / name_desc：按文件名（默认 name_asc）
                      name_natural：按文件名自然排序（编号 1, 2, 10 正确）
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
                    ["name_asc", "name_desc", "fullpath_asc", "fullpath_desc", "mtime_asc", "mtime_desc", "name_natural"],
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
                    ["name_asc", "name_desc", "fullpath_asc", "fullpath_desc", "mtime_asc", "mtime_desc", "name_natural"],
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


# =========================================================================
# 6. wwdm_ImageFolder - 依次读取文件夹中的所有图片
# =========================================================================
# 支持的图片扩展名（小写）
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff", ".jfif", ".avif"}


def _load_one_image(path, max_megapixels=0):
    """把单个图片文件读成 ComfyUI 的 IMAGE 张量。

    返回 (image_tensor[1,H,W,C] float32 0-1, mask_tensor[1,h,w] 或 None)。
    依赖 torch / numpy / Pillow，全部在函数内延迟导入，避免插件导入阶段出问题。
    """
    import numpy as np
    import torch
    from PIL import Image, ImageOps, ImageSequence

    alpha = None
    mask_tensor = None

    # 单次打开：取第一帧 RGB，并取出透明通道
    with Image.open(path) as opened:
        frame = next(ImageSequence.Iterator(opened), None)
        if frame is None:
            raise ValueError("图片没有可读取的帧")
        frame = ImageOps.exif_transpose(frame)
        image = frame.convert("RGB")
        if "A" in frame.getbands():
            alpha = frame.getchannel("A").copy()

    # 超大图保护：按比例缩小（RGB 与 alpha 一起处理，保证尺寸一致）
    limit = int(max_megapixels or 0)
    if limit > 0:
        pixels = image.size[0] * image.size[1]
        if pixels > limit * 1_000_000:
            scale = (limit * 1_000_000 / float(pixels)) ** 0.5
            new_size = (max(1, int(image.size[0] * scale)), max(1, int(image.size[1] * scale)))
            image = image.resize(new_size, Image.LANCZOS)
            if alpha is not None:
                alpha = alpha.resize(new_size, Image.LANCZOS)

    arr = np.asarray(image).astype(np.float32) / 255.0
    tensor = torch.from_numpy(arr)[None,]

    if alpha is not None:
        alpha_arr = np.asarray(alpha).astype(np.float32) / 255.0
        mask_tensor = 1.0 - torch.from_numpy(alpha_arr)[None,]

    return tensor, mask_tensor


class WWDMImageFolder:
    """
    图片文件夹读取节点

    功能说明：
        输入一个文件夹路径，依次按顺序读取该文件夹（可选包含子文件夹）中的所有图片，
        每张图片作为一个 IMAGE 元素，最终输出一个 IMAGE 列表（图片列表）。
        列表顺序由 sort_mode 决定，与"文本文件夹读取"节点保持一致。

    参数说明：
        folder_path : 文件夹路径，例如 E:\\ComfyUI\\input\\images
        extensions  : 参与读取的图片扩展名，逗号分隔；填 "*" 表示所有文件（非图片会报错跳过）。
                      默认 "png, jpg, jpeg, webp, bmp, gif, tif, tiff"
        sort_mode   : 图片顺序。
                      name_natural：按文件名自然排序（默认，img1, img2, img10 正确）
                      name_asc / name_desc：按文件名字符串排序（1, 10, 2）
                      fullpath_asc / fullpath_desc：按完整路径
                      mtime_asc / mtime_desc：按修改时间
        recursive   : 是否递归读取子文件夹。
        skip_hidden : 是否跳过隐藏文件与系统目录。
        max_images  : 最多读取的图片数量（0 = 不限制）。
        start_index : 从序列的第几张图片开始取（1 = 第一张；0 与 1 等价）。
        end_index   : 取到序列的第几张图片为止（含这一张；0 = 一直取到最后）。
                      例：start_index=3、end_index=7 -> 只读第 3、4、5、6、7 张。
        slice_index : 只取序列中的某一张（如 5 = 只要第 5 张）；0 = 不启用该选项。
        max_megapixels : 单张图片的百万像素上限，超过则等比缩小（0 = 不限制）。

    输出说明：
        images    : IMAGE 列表，每个元素是一张图（[1, H, W, C] float32 0~1）。
        filenames : STRING 列表，对应的文件名。
        masks     : MASK 列表，有透明通道的图片给出遮罩，其余为 None。
        count     : INT，成功读取的图片数量。

    使用示例：
        示例1 - 读取文件夹内所有图片：
            folder_path: "E:\\ComfyUI\\input\\images"
            images 结果: [图1, 图2, 图3]   （按文件名顺序）
            filenames 结果: ["01.png", "02.png", "03.png"]

        示例2 - 按修改时间倒序取最新 10 张：
            folder_path: "D:\\photos"  sort_mode: mtime_desc  max_images: 10

        示例3 - 只取第 3 张到第 7 张（共 5 张）：
            folder_path: "D:\\photos"  start_index: 3  end_index: 7
            filenames 结果: ["03.png", "04.png", "05.png", "06.png", "07.png"]

        示例4 - 只取第 5 张：
            folder_path: "D:\\photos"  slice_index: 5

        示例5 - 从第 20 张取到最后：
            folder_path: "D:\\photos"  start_index: 20  end_index: 0

    提示：
        输出是图片列表，接到批次类节点（如 Image Batch / 图像批量）即按顺序合并；
        接普通 IMAGE 输入时按 ComfyUI 规则逐张执行一次。
        序号按"排序后的顺序"计算，从 1 开始。
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "folder_path": ("STRING", {"multiline": False, "default": ""}),
                "extensions": ("STRING", {"multiline": False, "default": "png, jpg, jpeg, webp, bmp, gif, tif, tiff"}),
                "sort_mode": (
                    ["name_natural", "name_asc", "name_desc", "fullpath_asc", "fullpath_desc", "mtime_asc", "mtime_desc"],
                    {"default": "name_natural"},
                ),
            },
            "optional": {
                "recursive": ("BOOLEAN", {"default": False}),
                "skip_hidden": ("BOOLEAN", {"default": True}),
                "start_index": ("INT", {"default": 0, "min": 0, "max": 100000, "step": 1,
                                        "tooltip": "从第几张开始取（1 = 第一张，0 与 1 等价）"}),
                "end_index": ("INT", {"default": 0, "min": 0, "max": 100000, "step": 1,
                                      "tooltip": "取到第几张为止，含这一张（0 = 一直取到最后）"}),
                "slice_index": ("INT", {"default": 0, "min": 0, "max": 100000, "step": 1,
                                        "tooltip": "只取某一张（如 5 = 只要第 5 张）；0 = 不启用"}),
                "max_images": ("INT", {"default": 0, "min": 0, "max": 100000, "step": 1}),
                "max_megapixels": ("INT", {"default": 0, "min": 0, "max": 1000, "step": 1}),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING", "MASK", "INT")
    RETURN_NAMES = ("images", "filenames", "masks", "count")
    OUTPUT_IS_LIST = (True, True, True, False)
    FUNCTION = "read_images"
    CATEGORY = "wwdm-normal"
    DESCRIPTION = "依次读取文件夹中的所有图片，可指定第几张到第几张，输出图片列表。"

    def read_images(
        self,
        folder_path,
        extensions="png, jpg, jpeg, webp, bmp, gif, tif, tiff",
        sort_mode="name_natural",
        recursive=False,
        skip_hidden=True,
        start_index=0,
        end_index=0,
        slice_index=0,
        max_images=0,
        max_megapixels=0,
    ):
        # 默认只挑图片扩展名；用户填 "*" 时读取全部文件
        exts = _normalize_exts(extensions)
        if not exts:
            files, error = _collect_files(
                folder_path, extensions="*", recursive=recursive,
                skip_hidden=skip_hidden, sort_mode=sort_mode,
            )
        else:
            files, error = _collect_files(
                folder_path, extensions=extensions, recursive=recursive,
                skip_hidden=skip_hidden, sort_mode=sort_mode,
            )
            if not error:
                files = [p for p in files if os.path.splitext(p)[1].lower() in IMAGE_EXTS]

        if error:
            print("[Comfyui-wwdm-normal] %s" % error)
            return ([], [], [], 0)

        if not files:
            print("[Comfyui-wwdm-normal] 文件夹中未找到图片: %s" % folder_path)
            return ([], [], [], 0)

        total_found = len(files)

        # 按序列位置选择：序号从 1 开始（1 = 排序后的第一张）
        slice_index = int(_first(slice_index, 0) or 0)
        start_index = int(_first(start_index, 0) or 0)
        end_index = int(_first(end_index, 0) or 0)

        if slice_index > 0:
            if slice_index > total_found:
                print("[Comfyui-wwdm-normal] 只找到 %d 张图片，取不到第 %d 张（目录: %s）"
                      % (total_found, slice_index, folder_path))
                return ([], [], [], 0)
            files = [files[slice_index - 1]]
            print("[Comfyui-wwdm-normal] 序列选择: 第 %d 张（共 %d 张）" % (slice_index, total_found))
        elif start_index > 1 or end_index > 0:
            start_pos = max(0, start_index - 1) if start_index > 0 else 0
            end_pos = end_index if end_index > 0 else total_found
            if start_pos >= total_found:
                print("[Comfyui-wwdm-normal] 只找到 %d 张图片，起始序号 %d 超出范围（目录: %s）"
                      % (total_found, start_index, folder_path))
                return ([], [], [], 0)
            selected = files[start_pos:end_pos]
            if not selected:
                print("[Comfyui-wwdm-normal] 序号区间 %d-%d 没有取到图片（共 %d 张）"
                      % (start_index, end_index, total_found))
                return ([], [], [], 0)
            print("[Comfyui-wwdm-normal] 序列选择: 第 %d 张 到 第 %d 张（共 %d 张，请求 %d-%d）"
                  % (start_pos + 1, start_pos + len(selected), total_found,
                     start_index if start_index > 0 else 1, end_pos))
            files = selected

        if max_images and int(max_images) > 0:
            files = files[: int(max_images)]

        images = []
        names = []
        masks = []
        failed = []

        for path in files:
            try:
                image, mask = _load_one_image(path, max_megapixels=max_megapixels)
            except Exception as exc:  # 单张图失败不影响整体
                failed.append("%s (%s)" % (path, exc))
                continue

            images.append(image)
            names.append(os.path.basename(path))
            masks.append(mask)

        if failed:
            print("[Comfyui-wwdm-normal] 以下图片读取失败，已跳过：")
            for item in failed:
                print("    - %s" % item)

        print("[Comfyui-wwdm-normal] 已读取 %d/%d 张图片（目录: %s）" % (len(images), len(files), folder_path))
        return (images, names, masks, len(images))


# =========================================================================
# 7. wwdm_AudioPlay - 播放指定位置的音效/音乐
# =========================================================================
class WWDMAudioPlay:
    """
    播放音频节点

    功能说明：
        输入为"任何"（音频文件路径字符串，或上游任意输出），
        解析出音频文件位置后调用系统播放器播放该音效/音乐。

    参数说明：
        audio       : 任意输入（*）。可以是：
                      - 音频文件路径字符串（最常用），如 "E:\\\\sfx\\\\ding.mp3"
                      - 只写文件名（如 "ding.wav"）时会去 C:\\\\Windows\\\\Media 等常见目录找
                      - 字典 / 对象（含 path、audio_path、filename 等键或属性）
        path        : 备用路径输入框；当 audio 没接或解析不出路径时使用它。
        volume      : 音量 0~1（WMP / afplay / paplay / mpv 生效）。
        speed       : 播放速度 0.5~2（WMP / afplay / ffplay 生效）。
        wait_mode   : wait  = 播放完（或到 max_seconds）再继续工作流
                      async = 立即返回，后台播放（推荐用于生成过程中的音效）
        play_count  : 重复播放次数。
        max_seconds : 最长播放秒数（0 = 不限制）；wait 模式下超时会自动停止。

    输出说明：
        played  : BOOLEAN / 列表，是否播放成功。
        path    : STRING / 列表，实际播放的文件路径。
        message : STRING / 列表，执行说明或错误原因。

    使用示例：
        示例1 - 完成时播放提示音：
            path: "C:\\\\Windows\\\\Media\\\\notify.wav"  wait_mode: async

        示例2 - 由上游节点传入路径：
            audio <- (任意节点的字符串输出)  wait_mode: wait

        示例3 - 试听一段音乐的前 10 秒：
            path: "D:\\\\music\\\\demo.mp3"  max_seconds: 10  wait_mode: wait
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "path": ("STRING", {"multiline": False, "default": ""}),
            },
            "optional": {
                "audio": ("*", {}),
                "volume": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.05}),
                "speed": ("FLOAT", {"default": 1.0, "min": 0.5, "max": 2.0, "step": 0.05}),
                "wait_mode": (["wait", "async"], {"default": "async"}),
                "play_count": ("INT", {"default": 1, "min": 1, "max": 100, "step": 1}),
                "max_seconds": ("INT", {"default": 0, "min": 0, "max": 36000, "step": 1}),
            },
        }

    RETURN_TYPES = ("BOOLEAN", "STRING", "STRING")
    RETURN_NAMES = ("played", "path", "message")
    OUTPUT_IS_LIST = (True, True, True)
    FUNCTION = "play"
    CATEGORY = "wwdm-normal"
    DESCRIPTION = "播放指定位置的音效或音乐（输入为任何类型）。"

    def play(self, path="", audio=None, volume=1.0, speed=1.0,
             wait_mode="async", play_count=1, max_seconds=0):
        from . import wwdm_audio

        # 输入解包（可能是列表）
        raw_path = _first(path, "")
        raw_audio = _first(audio, None)
        volume = float(_first(volume, 1.0) or 1.0)
        speed = float(_first(speed, 1.0) or 1.0)
        wait_mode = str(_first(wait_mode, "async"))
        play_count = int(_first(play_count, 1) or 1)
        max_seconds = int(_first(max_seconds, 0) or 0)

        # 优先用"任何"输入里解析到的路径，其次用 path 输入框
        candidate = wwdm_audio.extract_path_from_input(raw_audio)
        if not candidate:
            candidate = raw_path

        if not candidate:
            message = "没有可播放的音频路径：请把音频路径填到 path，或把路径字符串接到 audio 输入"
            print("[Comfyui-wwdm-normal] " + message)
            return ([False], [""], [message])

        resolved, error = wwdm_audio.resolve_audio_path(candidate)
        if error:
            print("[Comfyui-wwdm-normal] " + error)
            return ([False], [candidate], [error])

        success, logs = wwdm_audio.play_audio_node(
            resolved,
            volume=volume,
            speed=speed,
            wait_mode=wait_mode,
            play_count=play_count,
            max_seconds=max_seconds,
        )

        header = "[Comfyui-wwdm-normal] 播放 %s（%s）" % (resolved, wait_mode)
        print(header)
        for line in logs:
            print("    " + line)

        message = " | ".join(logs) if logs else "未执行播放"
        return ([success > 0], [resolved], [message])


# =========================================================================
# 8. wwdm_SaveText - 把字符串保存为 txt 文本
# =========================================================================
# 文件名里的编号占位符（支持 {n} 与 {n:03d} 这类格式）
_NUMBER_PLACEHOLDER = re.compile(r"\{n(?::(\d+)d)?\}")


def _resolve_output_dir(save_dir=""):
    """决定保存目录。

    save_dir 为空 -> ComfyUI 的 output 目录；相对路径 -> 相对 output 目录；绝对路径 -> 原样使用。
    """
    custom = str(save_dir or "").strip().strip('"')
    base = None
    try:
        import folder_paths  # ComfyUI 自带；脱离 ComfyUI 运行时可能不存在
        base = folder_paths.get_output_directory()
    except Exception:
        base = None

    if not custom:
        return base or os.path.abspath("output")
    expanded = os.path.expanduser(os.path.expandvars(custom))
    if os.path.isabs(expanded):
        return expanded
    return os.path.join(base or os.path.abspath("output"), expanded)


def _format_number(number, number_format="plain", width=0):
    """按格式生成编号文本。"""
    if number_format == "00000":
        return "%05d" % number
    if number_format == "custom" and width > 0:
        return ("%0" + str(int(width)) + "d") % number
    return str(number)


def _build_filename(number, prefix="", suffix="", name_pattern="", number_format="plain", width=0):
    """根据设置生成文件名（含 .txt 后缀；name_pattern 里没有 {n} 时会自动补编号）。"""
    pattern = str(name_pattern or "").strip()
    prefix = str(prefix or "")
    suffix = str(suffix or "")
    token = _format_number(number, number_format, width)

    if pattern:
        if _NUMBER_PLACEHOLDER.search(pattern):
            def _replace(match):
                width_value = int(match.group(1)) if match.group(1) else int(width or 0)
                return ("%0" + str(width_value) + "d") % number if width_value > 0 else str(number)
            name = _NUMBER_PLACEHOLDER.sub(_replace, pattern)
        else:
            name = "%s_%s" % (pattern, token)
    else:
        name = "%s%s%s" % (prefix, token, suffix)

    if not name.lower().endswith(".txt"):
        name += ".txt"
    return name


def _scan_existing_numbers(directory, prefix="", suffix="", name_pattern=""):
    """扫描目录里已存在的编号，返回最大编号（没有则返回 0）。"""
    if not os.path.isdir(directory):
        return 0

    pattern = str(name_pattern or "").strip()
    prefix = str(prefix or "")
    suffix = str(suffix or "")
    highest = 0

    try:
        entries = os.listdir(directory)
    except OSError:
        return 0

    for entry in entries:
        if not entry.lower().endswith(".txt"):
            continue
        stem = entry[:-4]

        if pattern:
            # 先把编号占位符换成捕获组，再对字面部分转义（顺序不能反，否则 \ 会把 {} 也转义掉）
            regex = _NUMBER_PLACEHOLDER.sub("\x00", pattern)
            regex = re.escape(regex).replace("\x00", r"(\d+)")
            match = re.fullmatch(regex, stem)
            if not match:
                continue
            try:
                highest = max(highest, int(match.group(1)))
            except (ValueError, IndexError):
                continue
        else:
            if prefix and not stem.startswith(prefix):
                continue
            if suffix and not stem.endswith(suffix):
                continue
            middle = stem[len(prefix): len(stem) - len(suffix) if suffix else len(stem)]
            if middle.isdigit():
                highest = max(highest, int(middle))

    return highest


class WWDMSaveText:
    """
    保存文本节点

    功能说明：
        把输入字符串保存为 txt 文本文件。保存的文件名可由用户自定义，
        默认按 1、2、3…… 的数字顺序命名（1.txt、2.txt、……）。
        输入是字符串列表时，每个字符串分别保存为一个 txt 文件。

    参数说明：
        text        : 字符串（或字符串列表）。
        save_dir    : 保存目录。留空 = ComfyUI 的 output 目录；
                      相对路径 = 相对 output 目录（如 "prompts" -> output/prompts）；
                      也可以填绝对路径。
        name_pattern: 自定义文件名模板，支持 {n} 编号占位符与 {n:03d} 补零写法。
                      示例：out_{n:03d} -> out_001.txt、out_002.txt
                      留空时使用下面的 prefix + 编号 + suffix 组合。
        prefix      : 文件名前缀（name_pattern 留空时生效）。
        suffix      : 文件名后缀（name_pattern 留空时生效，编号在中间）。
        number_format : 编号写法。plain = 1、2、10；00000 = 00001、00002；custom = 用 number_width 指定补零位数。
        number_width  : number_format=custom 时的补零位数。
        start_index : 起始编号（默认 1）。
        continue_numbering : 是否从目录里已有文件的最大编号继续，避免覆盖已有文件。
        overwrite   : 同名文件是否直接覆盖（关闭时会自动往后找一个没用过的编号）。
        encoding    : 文本编码，utf-8 / utf-8-sig / gbk / gb18030。
        add_newline : 是否在文本末尾补一个换行。

    输出说明：
        file_paths : STRING 列表，保存后的 txt 完整路径。
        count      : INT，保存的文件数量。
        save_dir   : STRING，实际保存目录。

    使用示例：
        示例1 - 默认数字命名：
            text: "你好世界"
            save_dir 留空
            结果: output/1.txt（内容是"你好世界"）…… 下一批是 2.txt

        示例2 - 自定义名称：
            text: "提示词内容"  name_pattern: "prompt_{n:03d}"
            结果: output/prompt_001.txt

        示例3 - 前缀 + 智能续号：
            text: "第一条"  prefix: "note_"  continue_numbering: true
            结果: output/note_1.txt（已有 note_5.txt 时则保存为 note_6.txt）
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {"multiline": True, "default": "", "forceInput": True}),
                "save_dir": ("STRING", {"multiline": False, "default": ""}),
            },
            "optional": {
                "name_pattern": ("STRING", {"multiline": False, "default": ""}),
                "prefix": ("STRING", {"multiline": False, "default": ""}),
                "suffix": ("STRING", {"multiline": False, "default": ""}),
                "number_format": (["plain", "00000", "custom"], {"default": "plain"}),
                "number_width": ("INT", {"default": 3, "min": 1, "max": 12, "step": 1}),
                "start_index": ("INT", {"default": 1, "min": 0, "max": 999999999, "step": 1}),
                "continue_numbering": ("BOOLEAN", {"default": True}),
                "overwrite": ("BOOLEAN", {"default": False}),
                "encoding": (["utf-8", "utf-8-sig", "gbk", "gb18030"], {"default": "utf-8"}),
                "add_newline": ("BOOLEAN", {"default": False}),
            },
        }

    RETURN_TYPES = ("STRING", "INT", "STRING")
    RETURN_NAMES = ("file_paths", "count", "save_dir")
    OUTPUT_IS_LIST = (True, False, False)
    OUTPUT_NODE = True  # 属于"输出节点"：即使下游没有连线，也要执行保存
    FUNCTION = "save_text"
    CATEGORY = "wwdm-normal"
    DESCRIPTION = "把字符串保存为 txt 文本，文件名可自定义，默认 1.txt、2.txt……"

    def save_text(
        self,
        text,
        save_dir="",
        name_pattern="",
        prefix="",
        suffix="",
        number_format="plain",
        number_width=3,
        start_index=1,
        continue_numbering=True,
        overwrite=False,
        encoding="utf-8",
        add_newline=False,
    ):
        # 输入可能是列表（解包成多条文本）
        items = list(text) if isinstance(text, (list, tuple)) else [text]
        items = ["" if item is None else str(item) for item in items]

        name_pattern = str(_first(name_pattern, "") or "")
        prefix = str(_first(prefix, "") or "")
        suffix = str(_first(suffix, "") or "")
        number_format = str(_first(number_format, "plain") or "plain")
        number_width = int(_first(number_width, 3) or 3)
        start_index = int(_first(start_index, 1) or 0)
        continue_numbering = bool(_first(continue_numbering, True))
        overwrite = bool(_first(overwrite, False))
        encoding = str(_first(encoding, "utf-8") or "utf-8")
        add_newline = bool(_first(add_newline, False))
        raw_save_dir = str(_first(save_dir, "") or "")

        directory = _resolve_output_dir(raw_save_dir)
        try:
            os.makedirs(directory, exist_ok=True)
        except Exception as exc:
            message = "无法创建保存目录 %s: %s" % (directory, exc)
            print("[Comfyui-wwdm-normal] " + message)
            return ([], 0, directory)

        number = max(0, start_index)
        if continue_numbering:
            existing = _scan_existing_numbers(directory, prefix, suffix, name_pattern)
            number = max(number, existing + 1)

        saved = []
        failed = []

        for content in items:
            if add_newline and content and not content.endswith("\n"):
                content = content + "\n"

            target = os.path.join(directory, _build_filename(
                number, prefix, suffix, name_pattern, number_format, number_width))

            if not overwrite:
                # 同名文件已存在时，往后找一个没用过的编号，避免覆盖别人
                guard = 0
                while os.path.exists(target) and guard < 100000:
                    number += 1
                    guard += 1
                    target = os.path.join(directory, _build_filename(
                        number, prefix, suffix, name_pattern, number_format, number_width))

            try:
                with open(target, "w", encoding=encoding, newline="") as handle:
                    handle.write(content)
            except Exception as exc:
                failed.append("%s (%s)" % (target, exc))
                number += 1
                continue

            saved.append(target)
            print("[Comfyui-wwdm-normal] 已保存: %s" % target)
            number += 1

        if failed:
            print("[Comfyui-wwdm-normal] 以下文件保存失败：")
            for item in failed:
                print("    - %s" % item)

        print("[Comfyui-wwdm-normal] 共保存 %d/%d 个 txt 到 %s" % (len(saved), len(items), directory))
        return (saved, len(saved), directory)
