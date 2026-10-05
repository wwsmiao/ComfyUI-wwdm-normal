"""
Comfyui-wwdm-normal —— WWDM 文本文件批量读取插件

主要功能：
    输入文件夹路径，逐个读取文件夹中的所有 txt 文本，
    每个文本作为一个字符串，最终输出一个字符串列表。

节点列表：
    wwdm_TextFolder     / 文本文件夹读取   —— 文件夹 -> 字符串列表（核心节点）
    wwdm_TextFileList   / 文本文件列表     —— 文件夹 -> 文件路径列表
    wwdm_TextJoin       / 文本列表连接     —— 字符串列表 -> 单个字符串
    wwdm_TextPairConcat / 双字符串拼接     —— 两个字符串 -> 一个字符串 + 一个字符串列表
    wwdm_TextTrimEach   / 文本列表逐条处理 —— 字符串列表 -> 字符串列表
    wwdm_TextShow       / 文本预览         —— 打印预览并原样传递
    wwdm_ImageFolder    / 图片文件夹读取   —— 文件夹 -> 图片列表
    wwdm_AudioPlay      / 播放音频         —— 任意输入 -> 播放音效/音乐
    wwdm_SaveText       / 保存文本         —— 字符串 -> 保存为 txt（文件名可自定义）
"""

from .txt import (
    WWDMTextFolder,
    WWDMTextFileList,
    WWDMTextJoin,
    WWDMTextPairConcat,
    WWDMTextTrimEach,
    WWDMTextShow,
    WWDMImageFolder,
    WWDMAudioPlay,
    WWDMSaveText,
)

NODE_CLASS_MAPPINGS = {
    "wwdm_TextFolder": WWDMTextFolder,
    "wwdm_TextFileList": WWDMTextFileList,
    "wwdm_TextJoin": WWDMTextJoin,
    "wwdm_TextPairConcat": WWDMTextPairConcat,
    "wwdm_TextTrimEach": WWDMTextTrimEach,
    "wwdm_TextShow": WWDMTextShow,
    "wwdm_ImageFolder": WWDMImageFolder,
    "wwdm_AudioPlay": WWDMAudioPlay,
    "wwdm_SaveText": WWDMSaveText,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "wwdm_TextFolder": "文本文件夹读取 (wwdm)",
    "wwdm_TextFileList": "文本文件列表 (wwdm)",
    "wwdm_TextJoin": "文本列表连接 (wwdm)",
    "wwdm_TextPairConcat": "双字符串拼接 (wwdm)",
    "wwdm_TextTrimEach": "文本列表逐条处理 (wwdm)",
    "wwdm_TextShow": "文本预览 (wwdm)",
    "wwdm_ImageFolder": "图片文件夹读取 (wwdm)",
    "wwdm_AudioPlay": "播放音频 (wwdm)",
    "wwdm_SaveText": "保存文本 (wwdm)",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
