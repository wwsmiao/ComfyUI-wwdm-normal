# -*- coding: utf-8 -*-
"""Comfyui-wwdm-normal 自检脚本（不依赖 ComfyUI 运行环境）"""
import importlib.util
import os
import shutil
import sys
import tempfile

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
PKG = "wwdm_normal_test"

# 以 ComfyUI 相同的方式加载插件包
spec = importlib.util.spec_from_file_location(
    PKG, os.path.join(PLUGIN_DIR, "__init__.py"),
    submodule_search_locations=[PLUGIN_DIR],
)
mod = importlib.util.module_from_spec(spec)
sys.modules[PKG] = mod
spec.loader.exec_module(mod)

print("NODE_CLASS_MAPPINGS =", sorted(mod.NODE_CLASS_MAPPINGS))
print("NODE_DISPLAY_NAME_MAPPINGS =", sorted(mod.NODE_DISPLAY_NAME_MAPPINGS))
assert "wwdm_TextFolder" in mod.NODE_CLASS_MAPPINGS
assert len(mod.NODE_CLASS_MAPPINGS) == len(mod.NODE_DISPLAY_NAME_MAPPINGS) == 5

FolderNode = mod.NODE_CLASS_MAPPINGS["wwdm_TextFolder"]
ListedNode = mod.NODE_CLASS_MAPPINGS["wwdm_TextFileList"]
JoinNode = mod.NODE_CLASS_MAPPINGS["wwdm_TextJoin"]
TrimNode = mod.NODE_CLASS_MAPPINGS["wwdm_TextTrimEach"]
ShowNode = mod.NODE_CLASS_MAPPINGS["wwdm_TextShow"]

# 构造测试文件夹
root = tempfile.mkdtemp(prefix="wwdm_normal_")
sub = os.path.join(root, "sub")
os.makedirs(sub)

with open(os.path.join(root, "01_utf8.txt"), "w", encoding="utf-8", newline="\n") as f:
    f.write("第一个文件\nUTF-8 内容")
with open(os.path.join(root, "02_gbk.txt"), "w", encoding="gb18030", newline="\n") as f:
    f.write("第二个文件\nGBK 内容")
with open(os.path.join(root, "03_bom.txt"), "w", encoding="utf-8-sig") as f:
    f.write("第三个文件")
with open(os.path.join(root, "00_skip.md"), "w", encoding="utf-8") as f:
    f.write("不应被读取（扩展名不匹配）")
with open(os.path.join(root, "04_empty.txt"), "w", encoding="utf-8") as f:
    f.write("   ")
with open(os.path.join(sub, "10_nested.txt"), "w", encoding="utf-8") as f:
    f.write("子文件夹内容")

node = FolderNode()

# 1) 核心功能：只读 txt、非递归、按文件名升序
texts, names, count = node.read_folder(root)
assert texts == ["第一个文件\nUTF-8 内容", "第二个文件\nGBK 内容", "第三个文件", ""], texts
assert names == ["01_utf8.txt", "02_gbk.txt", "03_bom.txt", "04_empty.txt"], names
assert count == 4
print("OK 1 基本读取（混合编码）:", texts)

# 2) 递归 + 去空文件
texts, names, count = node.read_folder(root, recursive=True, remove_empty=True)
assert names == ["01_utf8.txt", "02_gbk.txt", "03_bom.txt", "10_nested.txt"], names
assert count == 4
print("OK 2 递归 + remove_empty:", names)

# 3) 降序 + 文件名前缀 + 强制 UTF-8
texts, names, count = node.read_folder(
    root, sort_mode="name_desc", filename_in_list=True, encoding_mode="utf-8"
)
assert names[0] == "04_empty.txt"
assert texts[-1].startswith("01_utf8.txt: ")
print("OK 3 降序 / 前缀 / 强制编码:", texts[-1])

# 4) 扩展名 "*" 读取全部文件
files, cnt = ListedNode().list_files(root, extensions="*")
assert cnt == 5, (cnt, files)
files, cnt = ListedNode().list_files(root, extensions="txt, md")
assert cnt == 5
files, cnt = ListedNode().list_files(root, extensions="md")
assert cnt == 1 and files[0].endswith("00_skip.md")
print("OK 4 扩展名筛选:", cnt)

# 5) 列表连接
joined = JoinNode().join(["A", "B", "C"], separator=", ")
assert joined == ("A, B, C",), joined
joined = JoinNode().join(["A", "", "C"], separator="|", skip_empty=True, prefix="<", suffix=">")
assert joined == ("<A|C>",), joined
print("OK 5 列表连接:", joined)

# 6) 列表逐条处理
out, n = TrimNode().process(["  第一行  ", "", "第二行", "第二行"], remove_empty=True, dedupe=True)
assert out == ["第一行", "第二行"], out
assert n == 2
print("OK 6 逐条处理:", out)

# 7) 预览节点原样传递
previewed = ShowNode().preview(["短文本", "x" * 500], max_chars=50)
assert previewed == (["短文本", "x" * 500],)
print("OK 7 预览节点原样传递")

# 8) 异常路径
assert node.read_folder("") == ([], [], 0)
assert node.read_folder(os.path.join(root, "不存在的目录")) == ([], [], 0)
assert node.read_folder(os.path.join(root, "01_utf8.txt")) == ([], [], 0)
print("OK 8 空路径 / 不存在 / 非文件夹 均安全返回")

# 9) max_files 限制
texts, names, count = node.read_folder(root, max_files=2)
assert count == 2 and names == ["01_utf8.txt", "02_gbk.txt"]
print("OK 9 max_files 限制")

# 10) 正斜杠路径与 INPUT_TYPES 结构
texts, names, count = node.read_folder(root.replace("\\", "/"))
assert count == 4
for cls in (FolderNode, ListedNode, JoinNode, TrimNode, ShowNode):
    it = cls.INPUT_TYPES()
    assert "required" in it and cls.RETURN_TYPES and cls.FUNCTION and cls.CATEGORY == "wwdm-normal"
assert FolderNode.OUTPUT_IS_LIST == (True, True, False)
print("OK 10 正斜杠路径 + INPUT_TYPES 结构")

shutil.rmtree(root, ignore_errors=True)
print("\n全部自检通过 ✔")
