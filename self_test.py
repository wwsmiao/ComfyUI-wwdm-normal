# -*- coding: utf-8 -*-
"""Comfyui-wwdm-normal 自检脚本（不依赖 ComfyUI 运行环境）"""
import importlib.util
import importlib
import os
import shutil
import subprocess
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
assert len(mod.NODE_CLASS_MAPPINGS) == len(mod.NODE_DISPLAY_NAME_MAPPINGS) == 10

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

    # 序列选择：按顺序取第几张到第几张（序号从 1 开始）
    # 自然顺序为 1.png, 2.jpg, 3_alpha.png, 10.png
    def names_of(**kwargs):
        return image_node.read_images(img_dir, recursive=True, **kwargs)[1]

    assert names_of(start_index=2) == ["2.jpg", "3_alpha.png", "10.png"]
    assert names_of(end_index=2) == ["1.png", "2.jpg"]
    assert names_of(start_index=2, end_index=3) == ["2.jpg", "3_alpha.png"]
    assert names_of(start_index=1, end_index=1) == ["1.png"]
    assert names_of(start_index=3, end_index=99) == ["3_alpha.png", "10.png"]   # 末页超出会自动收尾
    assert names_of(start_index=20) == []                                       # 起始越界 -> 空列表
    assert names_of(slice_index=3) == ["3_alpha.png"]                           # 单张选择
    assert names_of(slice_index=1) == ["1.png"]
    assert names_of(slice_index=99) == []                                       # 单张越界 -> 空列表
    assert names_of(slice_index=0, start_index=0, end_index=0)[0] == "1.png"    # 都不填 = 全部
    # 区间与 max_images 同时使用时，先按区间取，再限量
    assert names_of(start_index=2, max_images=1) == ["2.jpg"]
    # 区间同样影响 images / masks 输出（三者长度一致）
    imgs, nms, mks, cnt = image_node.read_images(img_dir, recursive=True, start_index=2, end_index=3)
    assert cnt == 2 and len(imgs) == len(nms) == len(mks) == 2
    assert tuple(imgs[0].shape) == (1, 10, 12, 3), tuple(imgs[0].shape)         # 第 2 张是 2.jpg

    print("OK 12b 图片序列选择: 第几张到第几张 / 单张 / 越界处理 均正常")

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

# 14) 新增节点：保存文本为 txt（字符串 -> txt，文件名可自定义，默认 1-n）
SaveNode = mod.NODE_CLASS_MAPPINGS["wwdm_SaveText"]
assert "wwdm_SaveText" in mod.NODE_DISPLAY_NAME_MAPPINGS
assert SaveNode.RETURN_TYPES == ("STRING", "INT", "STRING")
assert SaveNode.RETURN_NAMES == ("file_paths", "count", "save_dir")
assert SaveNode.OUTPUT_IS_LIST == (True, False, False)
assert SaveNode.OUTPUT_NODE is True, "保存节点必须是输出节点，否则没有下游连线时不会执行"
assert SaveNode.CATEGORY == "wwdm-normal"
assert SaveNode.INPUT_TYPES()["required"]["text"][0] == "STRING"

save_dir = os.path.join(root, "saved")
save = SaveNode()

# 14.1 默认命名：1.txt、2.txt、3.txt
paths, count, out_dir = save.save_text("第一条内容", save_dir=save_dir)
assert count == 1 and paths[0].endswith(os.sep + "1.txt"), (paths, count)
assert open(paths[0], encoding="utf-8").read() == "第一条内容"
paths, count, out_dir = save.save_text("第二条内容", save_dir=save_dir)
assert count == 1 and paths[0].endswith(os.sep + "2.txt"), paths
paths, count, _ = save.save_text(["A", "B"], save_dir=save_dir)      # 列表输入 -> 多个文件
assert count == 2 and [os.path.basename(p) for p in paths] == ["3.txt", "4.txt"], paths
assert open(os.path.join(save_dir, "4.txt"), encoding="utf-8").read() == "B"

# 14.2 自定义名称：模板 {n:03d}
paths, count, _ = save.save_text("模板内容", save_dir=save_dir, name_pattern="prompt_{n:03d}")
assert os.path.basename(paths[0]) == "prompt_001.txt", paths
paths, count, _ = save.save_text("模板内容2", save_dir=save_dir, name_pattern="prompt_{n:03d}",
                                 continue_numbering=False, overwrite=True)
assert os.path.basename(paths[0]) == "prompt_001.txt", paths

# 14.3 前缀 / 后缀 / 补零（续号按各自命名独立计算，不与 1.txt 系列混在一起）
paths, count, _ = save.save_text("前缀", save_dir=save_dir, prefix="note_", suffix="_end")
assert os.path.basename(paths[0]) == "note_1_end.txt", paths
paths, count, _ = save.save_text("补零", save_dir=save_dir, prefix="z", number_format="00000",
                                 continue_numbering=False)
assert os.path.basename(paths[0]) == "z00001.txt", paths
paths, count, _ = save.save_text("自定义位宽", save_dir=save_dir, prefix="w", number_format="custom",
                                 number_width=4, continue_numbering=False)
assert os.path.basename(paths[0]) == "w0001.txt", paths

# 14.4 续号：不覆盖已有文件
paths, count, _ = save.save_text("续号", save_dir=save_dir, prefix="note_", suffix="_end",
                                 continue_numbering=True)
assert os.path.basename(paths[0]) == "note_2_end.txt", paths
paths, count, _ = save.save_text("模板续号", save_dir=save_dir, name_pattern="prompt_{n:03d}",
                                 continue_numbering=True)
assert os.path.basename(paths[0]) == "prompt_002.txt", paths

# 14.5 overwrite=False 时同编号不覆盖，自动顺延
before = open(os.path.join(save_dir, "1.txt"), encoding="utf-8").read()
paths, count, _ = save.save_text("不应覆盖", save_dir=save_dir, start_index=1,
                                 continue_numbering=False, overwrite=False)
assert os.path.basename(paths[0]) != "1.txt", paths
assert open(os.path.join(save_dir, "1.txt"), encoding="utf-8").read() == before

# 14.6 start_index 与 overwrite=True
paths, count, _ = save.save_text("起始编号", save_dir=save_dir, start_index=100,
                                 continue_numbering=False)
assert os.path.basename(paths[0]) == "100.txt", paths

# 14.7 编码与末尾换行
paths, count, _ = save.save_text("中文编码测试", save_dir=save_dir, prefix="gbk_",
                                 encoding="gbk", continue_numbering=False)
with open(paths[0], "rb") as fh:
    assert fh.read().decode("gbk") == "中文编码测试"
paths, count, _ = save.save_text("换行测试", save_dir=save_dir, prefix="nl_", add_newline=True,
                                 continue_numbering=False)
assert open(paths[0], encoding="utf-8").read() == "换行测试\n"

# 14.8 空字符串也要落盘（生成空文件）
paths, count, _ = save.save_text("", save_dir=save_dir, prefix="empty_", continue_numbering=False)
assert count == 1 and os.path.getsize(paths[0]) == 0

# 14.9 默认目录（不传 save_dir 时用 ComfyUI output / 当前目录，不应报错）
paths, count, out_dir = save.save_text("默认目录", prefix="defaultdir_")
assert count == 1 and os.path.isfile(paths[0])
os.remove(paths[0])

# 14.10 非法目录 -> 安全返回，不抛异常
paths, count, _ = save.save_text("x", save_dir=os.path.join(root, "01_utf8.txt", "sub"))
assert paths == [] and count == 0

print("OK 14 保存文本为 txt（新节点）: 默认 1-n 命名 / 自定义模板 / 续号 / 编码 均正常")

# 15) 新增节点：视频最后一帧（视频 -> 最后一帧图片）
VideoNode = mod.NODE_CLASS_MAPPINGS["wwdm_VideoLastFrame"]
assert "wwdm_VideoLastFrame" in mod.NODE_DISPLAY_NAME_MAPPINGS
assert VideoNode.RETURN_TYPES == ("IMAGE", "INT", "STRING", "DICT")
assert VideoNode.RETURN_NAMES == ("image", "frame_count", "filename", "video_info")
assert VideoNode.CATEGORY == "wwdm-normal"
assert VideoNode.INPUT_TYPES()["optional"]["video"][0] == "*", "video 必须是“任何”输入"

vid = importlib.import_module(PKG + ".wwdm_video")
videonode = VideoNode()

# 15.1 路径解析 / 从任意输入提取
assert vid.normalize_path('  "C:\\a b\\c.mp4"  ') == "C:\\a b\\c.mp4"
assert vid.extract_path_from_input("x.mp4") == "x.mp4"
assert vid.extract_path_from_input({"path": "y.mp4"}) == "y.mp4"
assert vid.extract_path_from_input([None, "z.mp4"]) == "z.mp4"
assert vid.extract_path_from_input(12345) is None
resolved, err = vid.resolve_video_path(os.path.join(root, "缺失.mp4"))
assert resolved == "" and "找不到" in err
resolved, err = vid.resolve_video_path(root)
assert resolved == "" and "文件夹" in err

# 15.2 真正解码一段合成的视频（末帧为纯红色，用来验证"就是最后一帧"）
FFMPEG = shutil.which("ffmpeg")
if FFMPEG:
    from PIL import Image as PILImage2
    test_mp4 = os.path.join(root, "video_last_frame.mp4")
    # 前 10 帧蓝色，最后一帧红色：最后一帧取错会明显暴露
    cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
           "-f", "lavfi", "-i", "color=c=blue:s=64x48:r=10:d=1",
           "-vf", "drawbox=x=0:y=0:w=64:h=48:color=red@1:t=fill:enable='eq(n,9)'",
           "-pix_fmt", "yuv420p", test_mp4]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
    assert os.path.isfile(test_mp4), "测试视频未生成"

    img, used = vid.read_last_frame(test_mp4)
    assert tuple(img.shape) == (1, 48, 64, 3), tuple(img.shape)
    assert 0.0 <= float(img.min()) and float(img.max()) <= 1.0
    # 末帧应为红色（R 明显大于 G/B）
    assert float(img[..., 0].mean()) > 0.7, "末帧不是红色，可能没取到最后一帧"
    assert float(img[..., 2].mean()) < 0.2, "末帧混入了蓝色"
    print("    解码器:", used, "| 末帧平均 RGB: %.3f/%.3f/%.3f" % (
        float(img[..., 0].mean()), float(img[..., 1].mean()), float(img[..., 2].mean())))

    info = vid.get_video_info(test_mp4)
    assert info.get("width") == 64 and info.get("height") == 48, info

    # 节点接口：路径输入
    image, count, filename, vinfo = videonode.last_frame(video_path=test_mp4)
    assert tuple(image.shape) == (1, 48, 64, 3), tuple(image.shape)
    assert filename == "video_last_frame.mp4"
    assert isinstance(vinfo, dict) and vinfo.get("width") == 64

    # 节点接口：任意输入（模拟 VIDEO 对象提供 get_stream_source）
    class FakeVideo:
        def __init__(self, path):
            self._path = path
        def get_stream_source(self):
            return self._path
        def get_active_trim_window(self):
            return (0.0, 0.0)

    image, count, filename, vinfo = videonode.last_frame(video=FakeVideo(test_mp4))
    assert tuple(image.shape) == (1, 48, 64, 3), tuple(image.shape)

    # frame_offset：往前退 1 帧 -> 应该是蓝色
    image, count, filename, vinfo = videonode.last_frame(video_path=test_mp4, frame_offset=1)
    assert float(image[..., 2].mean()) > 0.5, "退一帧后应为蓝色"

    # 强制 ffmpeg 解码
    img_ff, used_ff = vid.read_last_frame(test_mp4, decoder="ffmpeg")
    assert used_ff == "ffmpeg" and float(img_ff[..., 0].mean()) > 0.7

    # 15.3 失败路径：结构完整的空结果，不抛异常
    image, count, filename, vinfo = videonode.last_frame(video_path=os.path.join(root, "没有.mp4"))
    assert count == 0 and tuple(image.shape) == (1, 64, 64, 3)
    assert "找不到" in vinfo.get("error", ""), vinfo
    image, count, filename, vinfo = videonode.last_frame(video_path="", video=None)
    assert count == 0 and "没有可读取的视频" in vinfo.get("error", ""), vinfo

    not_video = os.path.join(root, "不是视频.mp4")
    open(not_video, "wb").write(b"this is not a video")
    image, count, filename, vinfo = videonode.last_frame(video_path=not_video)
    assert count == 0, "非视频文件应返回空结果"

    os.remove(not_video)
    print("OK 15 视频最后一帧（新节点）: 末帧颜色/尺寸/任意输入/回退/兜底 均正确")
else:
    print("SKIP 15 系统没有 ffmpeg，跳过视频节点解码自检")

shutil.rmtree(root, ignore_errors=True)
print("\n全部自检通过 ✔")
