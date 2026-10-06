# Comfyui-wwdm-normal

ComfyUI 文本文件批量读取插件（仓库：<https://github.com/wwsmiao/ComfyUI-wwdm-normal>）。

**核心功能：输入一个文件夹路径，逐个读取该文件夹中的所有文本（默认 `.txt`），每个文本作为一个字符串，最终输出一个字符串列表。**

## 安装

### 方式一：手动安装

把整个 `Comfyui-wwdm-normal` 文件夹放入 ComfyUI 的 `custom_nodes` 目录：

```
E:\ComfyUI\custom_nodes\Comfyui-wwdm-normal
```

### 方式二：git clone

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/wwsmiao/ComfyUI-wwdm-normal.git
```

重启 ComfyUI（或刷新页面），在空白处双击 / 右键 `Add Node`，即可在 `wwdm-normal` 分类下看到节点。无第三方依赖，只用 Python 标准库。

## 节点列表

| 节点 | 显示名 | 功能 |
| --- | --- | --- |
| `wwdm_TextFolder` | 文本文件夹读取 (wwdm) | **核心节点**：文件夹路径 → 字符串列表 |
| `wwdm_TextFileList` | 文本文件列表 (wwdm) | 文件夹路径 → 文件路径列表 |
| `wwdm_TextJoin` | 文本列表连接 (wwdm) | 字符串列表 → 单个字符串 |
| `wwdm_TextPairConcat` | 双字符串拼接 (wwdm) | 两个字符串 → 一个字符串 + 一个字符串列表 |
| `wwdm_TextTrimEach` | 文本列表逐条处理 (wwdm) | 字符串列表 → 处理后的字符串列表 |
| `wwdm_TextShow` | 文本预览 (wwdm) | 打印预览并原样传递 |
| `wwdm_ImageFolder` | 图片文件夹读取 (wwdm) | 文件夹路径 → **图片列表** |
| `wwdm_AudioPlay` | 播放音频 (wwdm) | **任意输入** → 播放指定位置的音效/音乐 |
| `wwdm_SaveText` | 保存文本 (wwdm) | 字符串 → 保存为 txt，**文件名可自定义，默认 1.txt、2.txt……** |
| `wwdm_VideoLastFrame` | 视频最后一帧 (wwdm) | **视频 → 该视频的最后一帧图片** |

## 核心节点：文本文件夹读取（wwdm_TextFolder）

### 输入

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `folder_path` | STRING | 空 | 文件夹路径，如 `E:\ComfyUI\input\prompts`。支持 `/` 或 `\`、支持 `%VAR%` 与 `~` 展开 |
| `extensions` | STRING | `txt` | 参与读取的扩展名，逗号分隔，如 `txt, md`；填 `*` 表示读取全部文件 |
| `sort_mode` | 下拉 | `name_asc` | `name_asc` / `name_desc`（按文件名）、`fullpath_asc` / `fullpath_desc`（按完整路径）、`mtime_asc` / `mtime_desc`（按修改时间） |
| `recursive` | BOOLEAN | false | 是否递归读取子文件夹 |
| `encoding_mode` | 下拉 | `auto` | `auto`（自动识别） / `utf-8` / `gb18030` / `utf-8-sig` / `utf-16` |
| `strip_mode` | 下拉 | `rstrip` | `none` 原样 / `rstrip` 去末尾空白 / `strip` 去首尾空白（含换行） |
| `remove_empty` | BOOLEAN | false | 跳过内容为空的文件 |
| `skip_hidden` | BOOLEAN | true | 跳过隐藏文件与 `.git`、`__pycache__` 等系统目录 |
| `max_files` | INT | 0 | 最多读取文件数，0 = 不限制 |
| `filename_in_list` | BOOLEAN | false | 是否给每条文本加上 `文件名: ` 前缀 |

### 输出

| 输出 | 类型 | 说明 |
| --- | --- | --- |
| `texts` | STRING（列表） | 每个文件内容作为一个字符串，按 `sort_mode` 排序 |
| `filenames` | STRING（列表） | 对应的文件名 |
| `count` | INT | 成功读取的文件数量 |

### 示例

文件夹 `E:\ComfyUI\input\prompts` 内有 `b.txt`（内容 `第二个`）、`a.txt`（内容 `第一个`）：

```
folder_path: E:\ComfyUI\input\prompts
extensions : txt
sort_mode  : name_asc
```

输出：

```
texts     = ["第一个", "第二个"]
filenames = ["a.txt", "b.txt"]
count     = 2
```

## 节点：双字符串拼接（wwdm_TextPairConcat）

对两个字符串进行拼接，**同时输出一个字符串和一个字符串列表**。

### 输入

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `text_a` | STRING | 空 | 字符串 A（可连上游；上游是列表时取第一项） |
| `text_b` | STRING | 空 | 字符串 B（同上） |
| `connection` | STRING | 空 | A 与 B 之间的连接符，可直接写 `\n` / `\t` / `\r` / `\\` |
| `trim` | BOOLEAN | false | 拼接前是否去除 A、B 各自首尾空白 |
| `skip_empty` | BOOLEAN | false | 某侧为空时忽略它，避免产生多余连接符 |
| `uppercase_list` | BOOLEAN | false | 列表输出是否转为大写 |

### 输出

| 输出 | 类型 | 说明 |
| --- | --- | --- |
| `text` | STRING（单值） | A + connection + B 的拼接结果 |
| `texts` | STRING（**列表**） | `[A, B]` 两项，按顺序、不拼接 |

### 示例

```
text_a: "Hello"   text_b: "World"   connection: " "
text  = "Hello World"
texts = ["Hello", "World"]

text_a: "第一行"  text_b: "第二行"  connection: "\n"
text  = "第一行\n第二行"
texts = ["第一行", "第二行"]

text_a: "只有这一句"  text_b: ""  connection: " | "  skip_empty: true
text  = "只有这一句"
texts = ["只有这一句"]
```

> 注意：`texts` 是列表输出。接到普通 STRING 输入时会按 ComfyUI 规则逐项广播（下游执行 2 次）；要合并成一条文本，请接 `文本列表连接 (wwdm)` 节点。

## 节点：图片文件夹读取（wwdm_ImageFolder）

输入文件夹路径，**依次按顺序获取文件夹中的所有图片，输出一个图片列表**。

### 输入

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `folder_path` | STRING | 空 | 文件夹路径 |
| `extensions` | STRING | `png, jpg, jpeg, webp, bmp, gif, tif, tiff` | 图片扩展名；填 `*` 读取全部文件（非图片会跳过） |
| `sort_mode` | 下拉 | `name_natural` | 图片顺序，见下表 |
| `recursive` | BOOLEAN | false | 是否递归子文件夹 |
| `skip_hidden` | BOOLEAN | true | 跳过隐藏文件与系统目录 |
| `start_index` | INT | 0 | **从第几张开始取**（1 = 第一张；0 与 1 等价） |
| `end_index` | INT | 0 | **取到第几张为止（含这一张）**；0 = 一直取到最后 |
| `slice_index` | INT | 0 | **只取某一张**（如 5 = 只要第 5 张）；0 = 不启用 |
| `max_images` | INT | 0 | 最多读取数量，0 = 不限制 |
| `max_megapixels` | INT | 0 | 单张百万像素上限，超过等比缩小，0 = 不限制 |

序号按 `sort_mode` **排序后的顺序**计算，从 1 开始。组合效果：

| 设置 | 取到的图片 |
| --- | --- |
| 都不填（默认） | 全部图片（与旧版本行为完全一致） |
| `start_index=3, end_index=7` | 第 3、4、5、6、7 张（共 5 张） |
| `start_index=20` | 第 20 张到最后 |
| `end_index=5` | 第 1 张到第 5 张 |
| `start_index=6, end_index=6` | 只取第 6 张 |
| `slice_index=5` | 只取第 5 张（优先级高于 start/end） |
| 序号超出总张数 | 输出空列表并在控制台提示，不报错 |

`sort_mode` 取值：

| 值 | 说明 |
| --- | --- |
| `name_natural` | 按文件名自然排序（**默认**）：`1.png → 2.png → 10.png` |
| `name_asc` / `name_desc` | 按文件名字符串排序：`1.png → 10.png → 2.png` |
| `fullpath_asc` / `fullpath_desc` | 按完整路径 |
| `mtime_asc` / `mtime_desc` | 按修改时间 |

### 输出

| 输出 | 类型 | 说明 |
| --- | --- | --- |
| `images` | **IMAGE（列表）** | 每张图一个元素，`[1, H, W, C]` float32，0~1 |
| `filenames` | STRING（列表） | 对应的文件名 |
| `masks` | MASK（列表） | 有透明通道的图片给出遮罩，其余为 `None` |
| `count` | INT | 成功读取的图片数量 |

### 说明

- 支持 `png / jpg / jpeg / webp / bmp / gif / tif / tiff / jfif / avif`；GIF 取第一帧。
- 单张图片损坏或非法时**只跳过该张**，控制台打印原因，不影响其余图片。
- 读取时自动应用 EXIF 方向校正（手机竖拍照不会横过来）。
- **可按序列选择**：`start_index` / `end_index` 取第几张到第几张，`slice_index` 只取某一张；序号从 1 开始，越界返回空列表。
- `images` 是列表输出：接图片预览节点会逐张显示；接批次类节点即按顺序合并成一批。

### 示例

```
folder_path: "E:\ComfyUI\input\images"   sort_mode: name_natural   recursive: false
images    = [图1, 图2, 图10, 图alpha]
filenames = ["1.png", "2.png", "10.png", "alpha.png"]
count     = 4
```

```
只取第 3 张到第 7 张：
    start_index: 3   end_index: 7
    filenames = ["3.png", "4.png", "5.png", "6.png", "7.png"]

只取第 5 张：
    slice_index: 5
    filenames = ["5.png"]

从第 20 张取到最后：
    start_index: 20   end_index: 0
```

## 节点：播放音频（wwdm_AudioPlay）

**输入为「任何」，播放指定位置的音效或音乐。**

### 输入

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `path` | STRING | 空 | 音频文件路径，如 `E:\sfx\ding.mp3`；也支持只写文件名（会去 `C:\Windows\Media`、`~/Music` 等目录找） |
| `audio` | **任意（`*`）** | 无 | 可接任何上游输出：路径字符串、字典（含 `path`/`filename` 等键）、或对象。解析出的路径**优先于** `path` |
| `volume` | FLOAT | 1.0 | 音量 0~1（WMP / afplay / paplay / mpv 生效） |
| `speed` | FLOAT | 1.0 | 播放速度 0.5~2（WMP / afplay / ffplay 生效） |
| `wait_mode` | 下拉 | `async` | `wait` = 播放完再继续工作流；`async` = 立即返回、后台播放 |
| `play_count` | INT | 1 | 重复播放次数 |
| `max_seconds` | INT | 0 | 最长播放秒数，0 = 不限制；`wait` 模式下超时自动停止 |

### 输出

| 输出 | 类型 | 说明 |
| --- | --- | --- |
| `played` | BOOLEAN（列表） | 是否播放成功 |
| `path` | STRING（列表） | 实际播放的文件路径 |
| `message` | STRING（列表） | 执行说明或错误原因 |

### 示例

```
示例1 - 完成时播放提示音（后台，不阻塞）：
    path: "C:\Windows\Media\notify.wav"   wait_mode: async

示例2 - 上游节点把路径传进来：
    audio <- (任意节点的字符串输出)        wait_mode: wait

示例3 - 试听一段音乐的前 10 秒：
    path: "D:\music\demo.mp3"  max_seconds: 10  wait_mode: wait
```

### 说明

- 播放后端：Windows 用 WMP（`WMPlayer.OCX`，支持 mp3/wav/wma 等），失败时退回 .NET `SoundPlayer`（仅 wav）；macOS 用 `afplay`；Linux 依次尝试 `paplay / aplay / ffplay / mpv / cvlc / play`。
- 路径不会拼进命令行，而是通过参数/环境变量传给播放器，避免引号、空格、特殊字符导致的注入与转义问题。
- 文件损坏或格式不支持时返回 `played = false` 并在 `message` 给出原因，**不会中断工作流**。
- 自动化测试可用环境变量 `WWDM_AUDIO_NO_PLAY=1` 只解析路径、不出声。

## 节点：保存文本（wwdm_SaveText）

**输入字符串，保存为 txt 文本；文件名可自定义，默认按 `1.txt`、`2.txt`…… 的数字顺序命名。**

### 输入

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `text` | STRING | 空 | 要保存的字符串；接字符串列表时**每个字符串保存为一个 txt** |
| `save_dir` | STRING | 空 | 保存目录。留空 = ComfyUI 的 `output` 目录；相对路径 = 相对 `output`（如 `prompts` → `output/prompts`）；也可填绝对路径 |
| `name_pattern` | STRING | 空 | 自定义文件名模板，支持 `{n}` 与 `{n:03d}`。例：`prompt_{n:03d}` → `prompt_001.txt` |
| `prefix` / `suffix` | STRING | 空 | 文件名前缀 / 后缀（`name_pattern` 留空时生效，编号在中间） |
| `number_format` | 下拉 | `plain` | `plain`=1,2,10；`00000`=00001…；`custom`=用 `number_width` 指定位数 |
| `number_width` | INT | 3 | `custom` 时的补零位数 |
| `start_index` | INT | 1 | 起始编号 |
| `continue_numbering` | BOOLEAN | true | 从目录中已有同命名文件的最大编号往后接，避免覆盖 |
| `overwrite` | BOOLEAN | false | 同名是否覆盖；关闭时自动顺延到没用过的编号 |
| `encoding` | 下拉 | `utf-8` | `utf-8` / `utf-8-sig` / `gbk` / `gb18030` |
| `add_newline` | BOOLEAN | false | 是否在文本末尾补一个换行 |

### 输出

| 输出 | 类型 | 说明 |
| --- | --- | --- |
| `file_paths` | STRING（列表） | 保存后的 txt 完整路径 |
| `count` | INT | 保存的文件数量 |
| `save_dir` | STRING | 实际保存目录 |

### 示例

```
示例1 - 默认数字命名：
    text: "你好世界"                 save_dir: (留空)
    结果: output\1.txt  →  下一批自动是 2.txt、3.txt……

示例2 - 自定义名称：
    text: "提示词内容"               name_pattern: "prompt_{n:03d}"
    结果: output\prompt_001.txt

示例3 - 前缀 + 智能续号：
    text: "第一条"                   prefix: "note_"   continue_numbering: true
    结果: 已有 note_1_end.txt 时保存为 note_2_end.txt（不覆盖）

示例4 - 字符串列表批量落盘：
    text <- 文本文件夹读取.texts     prefix: "list_"
    结果: list_1.txt、list_2.txt…… 每个字符串一个文件
```

### 说明

- 本节点是**输出节点**（`OUTPUT_NODE = True`）：下游不连线也会执行保存。
- 续号按**各自命名规则独立计算**：`1.txt` 系列与 `note_*.txt` 系列互不影响。
- 目录不存在会自动创建；某个文件写入失败只跳过该文件并打印原因，不中断工作流。

## 节点：视频最后一帧（wwdm_VideoLastFrame）

**输入视频，输出该视频的最后一帧图片。**

### 输入

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `video_path` | STRING | 空 | 视频文件路径，如 `E:\video\a.mp4`；也支持相对 ComfyUI `input` 目录的相对路径 |
| `video` | **任意（`*`）** | 无 | 可接 ComfyUI 原生「加载视频」节点的 **VIDEO** 输出，也可接路径字符串/字典/对象。带裁剪区间的视频会取该区间的最后一帧 |
| `frame_offset` | INT | 0 | 从最后一帧往前退几张（0 = 最后一帧，1 = 倒数第二张……） |
| `decoder` | 下拉 | `auto` | `auto` = 先用 PyAV，失败自动退回 ffmpeg；也可强制 `pyav` / `ffmpeg` |
| `timeout` | INT | 0 | 解码超时秒数，0 = 不限制 |

### 输出

| 输出 | 类型 | 说明 |
| --- | --- | --- |
| `image` | IMAGE | 最后一帧图片，`[1, H, W, C]` float32，0~1 |
| `frame_count` | INT | 从最接近结尾处解出的帧数（成功时为 1，失败为 0） |
| `filename` | STRING | 视频文件名 |
| `video_info` | DICT | 视频信息：`codec` / `width` / `height` / `fps` / `duration` / `total_frames` / `decoder` 等 |

### 示例

```
示例1 - 直接接原生加载视频节点：
    video <- Load Video.video

示例2 - 用路径：
    video_path: "E:\video\demo.mp4"
    image 结果: 该视频最后一帧

示例3 - 结尾有一帧黑场，想避开：
    video_path: "E:\video\demo.mp4"   frame_offset: 1
```

### 说明

- 优先用 **PyAV**（ComfyUI 自带依赖）解码；解码失败或强制指定时退回 **ffmpeg** 命令行（不需要额外 Python 包）。
- `frame_offset` 会取「结尾若干帧里的倒数第 N 张」，与 ffmpeg 逐帧导出的结果一致（已用 14 帧测试视频逐帧比对验证）。
- 视频不存在、不是视频文件、没有视频流时，输出一张占位图并保持输出结构完整，同时在 `video_info.error` 给出原因，**不会中断工作流**。

## 用法说明

- `texts` 是**字符串列表**输出。想把它合并成一段文本，接到 `文本列表连接 (wwdm)` 节点即可（分隔符默认换行）。
- **核心节点**：文件夹 → 字符串列表：`wwdm_TextFolder`
- **图片节点**：文件夹 → 图片列表：`wwdm_ImageFolder`
- **音频节点**：任意输入 → 播放音效/音乐：`wwdm_AudioPlay`
- **保存节点**：字符串 → txt（文件名自定义，默认 1-n）：`wwdm_SaveText`
- **视频节点**：视频 → 最后一帧图片：`wwdm_VideoLastFrame`（可接原生 VIDEO 输出，也可用路径）
- 想查看读取结果，接到 `文本预览 (wwdm)` 节点，控制台会打印每条内容（超长自动截断）。
- 排序默认 `name_natural`（自然排序），`1, 2, 10` 顺序正确；需要传统字符串排序时选 `name_asc`。
  （注：两个文本节点为保持原有行为，默认仍是 `name_asc`，但下拉里已提供 `name_natural` 选项。）
- 编码自动识别顺序：UTF-8(BOM) → UTF-8 → GB18030/GBK → Big5 → Shift-JIS → UTF-8(替换)。单个文件读取失败只会跳过该文件并在控制台提示，不会中断工作流。
- 目录不存在 / 没有匹配文件时，输出空列表，控制台给出中文提示。

## 目录结构

```
Comfyui-wwdm-normal/
├── __init__.py        # 节点注册
├── txt.py             # 文本 / 图片 / 音频 / 保存 / 视频节点实现
├── wwdm_audio.py      # 音频路径解析与系统播放器调用
├── wwdm_video.py      # 视频路径解析、最后一帧解码（PyAV + ffmpeg 兜底）
├── self_test.py       # 自检脚本（python self_test.py）
├── workflows/         # 示例工作流
├── pyproject.toml     # 插件元信息（ComfyUI Manager 识别用）
├── LICENSE            # MIT
└── README.md
```
