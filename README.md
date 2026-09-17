# VoiceAnywhere P0

Windows 本地语音直写原型：将光标放在输入位置，按 `Ctrl+Alt+Space` 开始口述，再按一次结束。程序完成识别与忠实整理后，只在原目标仍有效时一次性插入文字，绝不发送。

## 运行

```powershell
uv sync --extra dev
uv run voiceanywhere
```

首次运行请在“设置”中保存 OpenRouter API Key，并选择可用麦克风。录音会发送到 OpenRouter 的 `openai/whisper-large-v3`；最终转写和已启用词条会发送到 `openai/gpt-5.6-luna`。本地默认只在内存保留最近一次会话；点击“保存问题案例”才会写入本地案例目录。

配置目录为 `%LOCALAPPDATA%\VoiceAnywhere`。API Key 使用当前 Windows 用户的 DPAPI 加密，不写入项目文件、普通日志或案例。

## 当前支持范围

- P0 使用录音结束后的完整 WAV 上传，尚未实现流式识别，不把延迟目标当作已通过。
- 默认“忠实整理”，可以切换为“仅转写”。周边输入框文字读取在 P0 中固定关闭。
- 已测试目标应是记事本、普通浏览器文本框和微信桌面输入框。管理员窗口、密码框、远程桌面、终端和未验证的自绘控件只保留结果供复制。
- 自动插入前会确认前台窗口、焦点控件和本次会话是否仍有效；用户切换目标或编辑后，结果会保留而不会自动插入。

## 验证与打包

```powershell
uv run pytest
./scripts/build.ps1
```

打包后将生成 `dist\VoiceAnywhere-windows-x64.zip`。**请完整解压其中的 `VoiceAnywhere` 文件夹，并只运行该文件夹内的 `VoiceAnywhere.exe`。** 这是 PyInstaller 的文件夹发布模式：同级 `_internal` 目录包含 Qt、Python 和音频运行库；只复制或移动 EXE 会导致 `QtCore` 的 DLL 载入失败。

发布版会在启动时明确登记 `_internal`、`_internal\PySide6` 和 `_internal\shiboken6` 为 DLL 搜索目录，因此不依赖启动目录或系统 PATH。

打包脚本会排除 PyInstaller 在本机可能误收集的 ICU 78 DLL；Qt 使用 Windows 自带的兼容 ICU 接口。请只使用最新 ZIP，不要将旧发布目录的 `_internal` 内容混入新目录。

首次试用前先在记事本验证录音、取消、换行、撤销和剪贴板恢复，再检查浏览器与微信。

## 文本试验台

没有麦克风时，可直接测试忠实整理的效果和模型请求耗时：

```powershell
uv run voiceanywhere-playground
```

试验台只提供输出语言和输入场景两个基础控制项。模型、提示词、推理强度、输出上限、`edit_level`、`filler_policy`、`tone`、`layout`、`punctuation`、`number_style` 和弱 `app_style` 均固定为内部自动默认策略：模型按片段决定必要的清理、改口、标点、分段或分点，不要求用户选择“润色力度”。

窗口显示对象型 `attention`、模型请求耗时和实际用量。它不录音、不插入其他程序、不保存正文；只有点击运行时才会将本框文字、附近文字和当前有效词条发送至 OpenRouter。严格保真 v2 参数模型与本地预设存储保留为内部研究能力，不显示在该窗口中。

## iPhone 测试版

原生 iOS 17 项目位于 [ios/VoiceAnywhereIOS](ios/VoiceAnywhereIOS)。它与 Windows 版共用 [自动默认策略](shared/auto_default_policy_v1.txt)，用于测试“主动录音 → OpenRouter 识别 → 自动整理 → 复制或系统分享”。

普通 Apple ID 可在 Mac 的 Xcode 通过 Personal Team 部署到自己的 iPhone；它不能导出可分发 IPA，且签名会定期到期。具体的 Xcode、设备测试和未来 IPA 分发步骤见 [iOS README](ios/VoiceAnywhereIOS/README.md)。

不使用 Mac 的 Windows 个人测试路径见 [Windows 侧载说明](ios/VoiceAnywhereIOS/WINDOWS_SIDELOAD.md)：GitHub Actions 以 macOS runner 编译未签名 IPA，你再在 Windows 本地用自己的 Apple Account 重签名安装。该路径不把 Apple 凭据或 OpenRouter API Key 上传到 GitHub。
