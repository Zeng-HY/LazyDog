# Windows 安装到 iPhone 测试

Windows 不需要安装 Xcode，但不能自行编译 Swift iOS App。本仓库的 GitHub Actions 使用 macOS runner 生成**未签名** IPA；该 IPA 仅用于由你在 Windows 本地重新签名后安装，不能直接点开安装。

## 1. 获取本项目的 IPA

1. 将本仓库推送到你自己的 GitHub 私有仓库。
2. 在 GitHub 的 **Actions** 运行 `Build iOS unsigned IPA`。
3. 运行成功后，下载 Artifact `VoiceAnywhereIOS-unsigned-ipa`，解压得到 `VoiceAnywhereIOS-unsigned.ipa`。

GitHub workflow 没有 Apple ID、证书或 API Key；它只编译并打包，不产生可直接安装的签名。

## 2. 在 Windows 本地重签名并安装

可使用支持 Windows 的第三方侧载工具，例如 Sideloadly。请仅从其[官网](https://sideloadly.io/)下载安装程序，并由你本人在工具中输入 Apple Account、密码和双重验证验证码；不要把这些凭据发给任何人或提交到 GitHub。

1. 通过 USB 连接 iPhone，解锁并选择“信任此电脑”。
2. 在侧载工具中选择 `VoiceAnywhereIOS-unsigned.ipa`、你的设备和 Apple Account。
3. 由侧载工具签名并安装。免费 Apple Account 的个人侧载通常约 7 天后失效，需要在 Windows 上重新签名和安装。
4. 若 iPhone 提示本地开发 App 无法运行，按系统提示开启开发者模式。Apple 说明本地开发安装可能要求 Developer Mode；若“开发者模式”开关没有出现，可能需要先将设备与 Mac 配对一次。[Apple Developer Mode 文档](https://developer.apple.com/documentation/xcode/enabling-developer-mode-on-a-device)
5. 打开 VoiceAnywhere，在 App 内保存自己的 OpenRouter API Key，再测试录音、取消、复制与分享。

不要按其他项目的指引去“信任 Orbit”或任何与 VoiceAnywhere 无关的企业证书。本项目不使用企业证书，也不要求安装描述文件。

## 3. 限制

- 这是个人测试路径，不适合向大众分发；免费 Personal Team 的配置会周期性到期。
- 加入 Apple Developer Program 后，应改用 Xcode Archive 的 Ad Hoc IPA 或 TestFlight，不再依赖第三方本地重签名。
- 如果侧载工具提示 iTunes/iCloud 组件问题，按该工具的官方文档处理；本项目不要求或提供 Apple 凭据。
