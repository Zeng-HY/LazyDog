# VoiceAnywhere iOS 17 测试版

这是供实体 iPhone 测试的独立 SwiftUI App：主动录音、批量识别、自动默认策略整理、复制或系统分享。它不做自定义键盘、全局输入或自动发送。

## 在 Mac 上测试

1. 将整个仓库同步到 Mac，确保 `shared/auto_default_policy_v1.txt` 保留在仓库根目录。
2. 用 Xcode 15 或更高版本打开 `VoiceAnywhereIOS.xcodeproj`。
3. 在 App target 的 **Signing & Capabilities** 中登录你的 Apple Account，选择 Personal Team，并把 Bundle Identifier 改为自己唯一的标识，例如 `com.yourname.voiceanywhere`。
4. 将 iPhone 设为运行目标，按 Run。首次录音时允许麦克风权限；在 API Key 窗口保存你自己的 OpenRouter Key。
5. 运行 Unit Tests 后，用 2–60 秒真实口述检查识别、整理、取消、网络错误、复制与分享。

普通 Apple ID 的 Personal Team 只能在自己的设备上部署测试，签名约 7 天后需重新部署；不能导出可分发 IPA。加入 Apple Developer Program 后，再在 Xcode 选择 Product > Archive 并使用 Distribute App 导出注册设备的 IPA 或上传 TestFlight。

## 仅用 Windows 侧载

如果你不想在 Windows 上安装 Xcode，可用本仓库的 GitHub Actions macOS runner 编译未签名 IPA，再在 Windows 本地用自己的 Apple Account 重新签名并安装。完整步骤见 [Windows 侧载说明](WINDOWS_SIDELOAD.md)。

## 隐私与数据边界

- 麦克风只在用户主动点击录音后使用；音频临时存放，识别完成或取消后删除。
- OpenRouter Key 只存入 iOS Keychain，采用 `WhenUnlockedThisDeviceOnly`，不写入日志、分享结果或诊断记录。
- 转写、整理结果和附近文字默认不持久化。只有用户点击复制或系统分享时，结果才离开 App。
