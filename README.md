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
| `max_images` | INT | 0 | 最多读取数量，0 = 不限制 |
| `max_megapixels` | INT | 0 | 单张百万像素上限，超过等比缩小，0 = 不限制 |

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
- `images` 是列表输出：接图片预览节点会逐张显示；接批次类节点即按顺序合并成一批。

### 示例

```
folder_path: "E:\ComfyUI\input\images"   sort_mode: name_natural   recursive: false
images    = [图1, 图2, 图10, 图alpha]
filenames = ["1.png", "2.png", "10.png", "alpha.png"]
count     = 4
```

## 用法说明

- `texts` 是**字符串列表**输出。想把它合并成一段文本，接到 `文本列表连接 (wwdm)` 节点即可（分隔符默认换行）。
- **核心节点**：文件夹 → 字符串列表：`wwdm_TextFolder`
- **图片节点**：文件夹 → 图片列表：`wwdm_ImageFolder`
- 想查看读取结果，接到 `文本预览 (wwdm)` 节点，控制台会打印每条内容（超长自动截断）。
- 排序默认 `name_natural`（自然排序），`1, 2, 10` 顺序正确；需要传统字符串排序时选 `name_asc`。
  （注：两个文本节点为保持原有行为，默认仍是 `name_asc`，但下拉里已提供 `name_natural` 选项。）
- 编码自动识别顺序：UTF-8(BOM) → UTF-8 → GB18030/GBK → Big5 → Shift-JIS → UTF-8(替换)。单个文件读取失败只会跳过该文件并在控制台提示，不会中断工作流。
- 目录不存在 / 没有匹配文件时，输出空列表，控制台给出中文提示。

## 目录结构

```
Comfyui-wwdm-normal/
├── __init__.py        # 节点注册
├── txt.py             # 全部节点实现
├── self_test.py       # 自检脚本（python self_test.py）
├── workflows/         # 示例工作流
├── pyproject.toml     # 插件元信息（ComfyUI Manager 识别用）
├── LICENSE            # MIT
└── README.md
```
