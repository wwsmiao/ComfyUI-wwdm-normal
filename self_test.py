# -*- coding: utf-8 -*-
"""Comfyui-wwdm-normal 自检脚本（不依赖 ComfyUI 运行环境）"""
import importlib.util
import importlib
import os
import shutil
import sys
import tempfile
import wave

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
assert len(mod.NODE_CLASS_MAPPINGS) == len(mod.NODE_DISPLAY_NAME_MAPPINGS) == 8

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

# 11) 新增节点：双字符串拼接（两个字符串 -> 一个字符串 + 一个字符串列表）
PairNode = mod.NODE_CLASS_MAPPINGS["wwdm_TextPairConcat"]
assert "wwdm_TextPairConcat" in mod.NODE_DISPLAY_NAME_MAPPINGS
assert PairNode.RETURN_TYPES == ("STRING", "STRING")
assert PairNode.RETURN_NAMES == ("text", "texts")
assert PairNode.OUTPUT_IS_LIST == (False, True), "第一个输出必须是单值，第二个输出必须是列表"
assert PairNode.CATEGORY == "wwdm-normal"

pair = PairNode()

joined, lst = pair.concat_pair("Hello", "World")
assert joined == "HelloWorld" and lst == ["Hello", "World"], (joined, lst)

joined, lst = pair.concat_pair("Hello", "World", connection=" ")
assert joined == "Hello World" and lst == ["Hello", "World"]

joined, lst = pair.concat_pair("第一行", "第二行", connection="\\n")
assert joined == "第一行\n第二行", repr(joined)
assert lst == ["第一行", "第二行"]

joined, lst = pair.concat_pair("  A  ", "  B  ", connection="-", trim=True)
assert (joined, lst) == ("A-B", ["A", "B"]), (joined, lst)

joined, lst = pair.concat_pair("只有这一句", "", connection=" | ", skip_empty=True)
assert (joined, lst) == ("只有这一句", ["只有这一句"]), (joined, lst)

joined, lst = pair.concat_pair("a", "b", connection="", skip_empty=False)
assert (joined, lst) == ("ab", ["a", "b"])

joined, lst = pair.concat_pair("aa", "bb", uppercase_list=True)
assert joined == "aabb" and lst == ["AA", "BB"]

# 单一输出校验：text 是 str（不是 list），texts 是 list
joined, lst = pair.concat_pair("x", "y")
assert isinstance(joined, str) and isinstance(lst, list) and len(lst) == 2

# 上游误接列表输入时取第一项，不报错
joined, lst = pair.concat_pair(["first", "second"], "B")
assert (joined, lst) == ("firstB", ["first", "B"]), (joined, lst)

print("OK 11 双字符串拼接（新节点）:", pair.concat_pair("Hello", "World", connection=" "))

# 12) 新增节点：图片文件夹读取（文件夹 -> 图片列表）
try:
    from PIL import Image as PILImage
    HAVE_PIL = True
except ImportError:
    HAVE_PIL = False

if HAVE_PIL:
    ImageNode = mod.NODE_CLASS_MAPPINGS["wwdm_ImageFolder"]
    assert "wwdm_ImageFolder" in mod.NODE_DISPLAY_NAME_MAPPINGS
    assert ImageNode.RETURN_TYPES == ("IMAGE", "STRING", "MASK", "INT")
    assert ImageNode.RETURN_NAMES == ("images", "filenames", "masks", "count")
    assert ImageNode.OUTPUT_IS_LIST == (True, True, True, False), "images 必须是列表输出"
    assert ImageNode.CATEGORY == "wwdm-normal"

    img_dir = os.path.join(root, "imgs")
    nested = os.path.join(img_dir, "nested")
    os.makedirs(nested)
    # 文件名故意用 1 / 2 / 10 检验排序：自然升序下 1,2,10
    PILImage.new("RGB", (8, 6), (255, 0, 0)).save(os.path.join(img_dir, "1.png"))
    PILImage.new("RGB", (12, 10), (0, 255, 0)).save(os.path.join(img_dir, "2.jpg"))
    PILImage.new("RGBA", (5, 5), (0, 0, 255, 128)).save(os.path.join(img_dir, "3_alpha.png"))
    PILImage.new("RGB", (4, 4), (1, 1, 1)).save(os.path.join(nested, "10.png"))
    with open(os.path.join(img_dir, "not_image.txt"), "w", encoding="utf-8") as f:
        f.write("不是图片")
    with open(os.path.join(img_dir, "broken.png"), "wb") as f:
        f.write(b"this is not a real png")

    image_node = ImageNode()
    images, names, masks, count = image_node.read_images(img_dir)
    assert names == ["1.png", "2.jpg", "3_alpha.png"], names   # broken.png 被跳过
    assert count == 3 and len(images) == 3 and len(masks) == 3
    assert names[0] == "1.png" and tuple(images[0].shape) == (1, 6, 8, 3), tuple(images[0].shape)
    assert tuple(images[1].shape) == (1, 10, 12, 3), tuple(images[1].shape)
    assert masks[2] is not None and tuple(masks[2].shape) == (1, 5, 5), tuple(masks[2].shape)
    assert masks[0] is None and masks[1] is None          # 无透明通道时为 None
    assert 0.0 <= float(images[0].min()) and float(images[0].max()) <= 1.0

    # 递归 + 数量限制（自然排序：1, 2, 3, 10）
    images, names, masks, count = image_node.read_images(img_dir, recursive=True)
    assert count == 4 and names == ["1.png", "2.jpg", "3_alpha.png", "10.png"], names
    images, names, masks, count = image_node.read_images(img_dir, recursive=True, max_images=2)
    assert count == 2 and names == ["1.png", "2.jpg"], names
    # 纯字符串排序作为对照：1, 10, 2, 3
    images, names, masks, count = image_node.read_images(img_dir, recursive=True, sort_mode="name_asc")
    assert names == ["1.png", "10.png", "2.jpg", "3_alpha.png"], names

    # 按修改时间倒序 + " * " 扩展名（读全部文件，坏图跳过）
    images, names, masks, count = image_node.read_images(img_dir, extensions="*", sort_mode="mtime_desc")
    assert count == 3
    # 超大图保护
    images, names, masks, count = image_node.read_images(img_dir, max_megapixels=1)
    assert count == 3 and images[0].shape[3] == 3

    # 异常与空文件夹
    assert image_node.read_images("") == ([], [], [], 0)
    assert image_node.read_images(os.path.join(root, "不存在")) == ([], [], [], 0)
    empty = os.path.join(root, "empty_dir")
    os.makedirs(empty, exist_ok=True)
    assert image_node.read_images(empty) == ([], [], [], 0)

    print("OK 12 图片文件夹读取（新节点）: 4 张图按 1,2,3,10 顺序读出，坏图被跳过")
else:
    print("SKIP 12 未安装 Pillow，跳过图片节点自检")

# 13) 新增节点：播放音频（任意输入 -> 播放指定位置的音效/音乐）
#     测试统一走"试运行"模式（WWDM_AUDIO_NO_PLAY=1），不真的出声
AudioNode = mod.NODE_CLASS_MAPPINGS["wwdm_AudioPlay"]
assert "wwdm_AudioPlay" in mod.NODE_DISPLAY_NAME_MAPPINGS
assert AudioNode.RETURN_TYPES == ("BOOLEAN", "STRING", "STRING")
assert AudioNode.RETURN_NAMES == ("played", "path", "message")
assert AudioNode.OUTPUT_IS_LIST == (True, True, True)
assert AudioNode.CATEGORY == "wwdm-normal"
it = AudioNode.INPUT_TYPES()
assert it["required"]["path"][0] == "STRING"
assert it["optional"]["audio"][0] == "*", "audio 必须是“任意类型”输入"

# 路径解析与"任意输入"提取
aud = importlib.import_module(PKG + ".wwdm_audio")
wav_path = os.path.join(root, "ding.wav")
with wave.open(wav_path, "wb") as fh:
    fh.setnchannels(1)
    fh.setsampwidth(2)
    fh.setframerate(8000)
    fh.writeframes(b"\x00\x00" * 800)

resolved, err = aud.resolve_audio_path('"%s"' % wav_path)          # 带引号也要能解析
assert err == "" and resolved == os.path.abspath(wav_path), (resolved, err)
resolved, err = aud.resolve_audio_path("ding.wav")                 # 只给文件名 -> 常见目录里找
assert (resolved, err) != ("", ""), "文件名兜底查找不应崩溃"
resolved, err = aud.resolve_audio_path(os.path.join(root, "不存在.mp3"))
assert resolved == "" and "找不到" in err, (resolved, err)
resolved, err = aud.resolve_audio_path(root)                       # 给的是文件夹
assert resolved == "" and "文件夹" in err, (resolved, err)
assert aud.normalize_path('  "E:\\a b\\c.mp3"  ') == "E:\\a b\\c.mp3"

assert aud.extract_path_from_input("abc.mp3") == "abc.mp3"
assert aud.extract_path_from_input({"path": "d.mp3"}) == "d.mp3"
assert aud.extract_path_from_input({"waveform": 1, "sample_rate": 44100}) is None
assert aud.extract_path_from_input(["x.mp3", "y.mp3"]) == "x.mp3"
assert aud.extract_path_from_input(12345) is None
assert round(aud.wav_duration(wav_path), 2) == 0.1

cmd, extra = aud.build_player_command(wav_path, volume=1.0, speed=1.0)
assert cmd is not None, extra
if os.name == "nt":
    assert cmd[0].lower().endswith(("powershell.exe", "powershell", "pwsh.exe", "pwsh")), cmd[0]
    assert wav_path not in " ".join(cmd), "路径不应拼进命令行，避免转义问题"
    assert "WWDM_AUDIO_FILE" in cmd[-1]

os.environ["WWDM_AUDIO_NO_PLAY"] = "1"
try:
    ok, res, msg = AudioNode().play(path=wav_path, wait_mode="async")
    assert ok == [True] and res == [os.path.abspath(wav_path)], (ok, res, msg)
    assert "试运行" in msg[0], msg

    # "任意"输入优先于 path 输入框
    ok, res, msg = AudioNode().play(path="", audio=wav_path)
    assert ok == [True] and res == [os.path.abspath(wav_path)], (ok, res)

    # 字典形式的任意输入
    ok, res, msg = AudioNode().play(path="", audio={"path": wav_path})
    assert ok == [True], (ok, msg)

    # 列表输入取第一项
    ok, res, msg = AudioNode().play(path="", audio=[wav_path])
    assert ok == [True], (ok, msg)

    # 无法解析的任意输入 -> 回退到 path；两者都空 -> 失败并给提示
    ok, res, msg = AudioNode().play(path=wav_path, audio={"waveform": 1})
    assert ok == [True], (ok, msg)
    ok, res, msg = AudioNode().play(path="", audio={"waveform": 1})
    assert ok == [False] and "没有可播放的音频路径" in msg[0], (ok, msg)

    # 文件不存在 -> 明确报错，不抛异常
    ok, res, msg = AudioNode().play(path=os.path.join(root, "nope.mp3"))
    assert ok == [False] and "找不到" in msg[0], (ok, msg)

    # 重复播放次数记录
    ok, res, msg = AudioNode().play(path=wav_path, play_count=3)
    assert ok == [True] and msg[0].count("次:") == 3, msg
finally:
    os.environ.pop("WWDM_AUDIO_NO_PLAY", None)

print("OK 13 播放音频（新节点）: 路径解析/任意输入提取/试运行播放 均正常")

shutil.rmtree(root, ignore_errors=True)
print("\n全部自检通过 ✔")
