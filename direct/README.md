# 联想签到器 · 直连版

日常签到直接连接联想 App 接口，无需模拟器、ADB、Python、Java 或 npm 依赖。只使用你自己的联想 App 登录态。

流程：查询今天是否已签 → 未签时提交一次 → 再次查询确认。只有服务器明确返回已签到才报告成功；超时或状态不明确会退出，不在同次运行里重发签到。

## 运行要求

- Windows 10/11，已安装 Node.js 并将 `node.exe` 加入 PATH。
- 本项目已验证 Node.js **24.14.1**。其他版本的 Node/OpenSSL 可能不支持本协议使用的 RSA 解密方式，遇到加密兼容错误时请使用已验证版本。
- 你自己的有效 App 登录配置。目前**没有独立短信、扫码登录，也没有自动提取登录态工具**。

不熟悉登录配置、尚未取得自己配置的用户，可以先使用仓库根目录的 Python 模拟器版。下载直连版压缩包本身不会获得已登录账号。

检查环境：

```powershell
node --version
```

## 1. 下载并解压

从 [Releases](https://github.com/liutianyi746-lab/Lenovo-Checkin/releases) 下载直连版 ZIP，解压到固定目录。后续命令均在包含 `checkin.mjs` 的目录中执行。

如果下载整个源码仓库，先进入 `direct` 子目录。

## 2. 导入自己的登录配置

复制 `credentials.example.json` 为 `credentials.local.json`，使用 UTF-8 编码，填入自己 App 的真实字段：

| 字段 | 含义 |
| --- | --- |
| `authorization` | 自己的完整登录态，格式为 `Lenovo ...` |
| `imei` | 自己 App 请求使用的客户端标识 |
| `uid` | 自己的账号 UID，填写数字字符串 |
| `flags.enE`、`flags.enR`、`flags.enF` | 自己 App 请求中的实际 boolean 值，不能保留模板的 `null` |

模板故意留空，不含可用登录态。不要填写他人的配置，也不要根据模板猜测实际字段。

然后执行：

```powershell
node configure.mjs
```

导入器会验证字段，使用 Windows 当前用户的 DPAPI 加密，写入同目录的 `credentials.dpapi`，不会输出登录态。导入成功后可删除明文 `credentials.local.json`。

`credentials.dpapi` 只能由原电脑、原 Windows 用户解密。朋友或其他电脑需要导入各自的配置，不能复制你的凭据文件。

## 3. 手动检查与签到

- 双击 `查询状态.cmd`：只查询，不提交。
- 双击 `一键签到.cmd`：已签直接退出；未签才提交一次并查询确认。

也可以运行：

```powershell
node checkin.mjs --status
node checkin.mjs
```

只查询模式输出“今日尚未签到”并退出 0，表示查询成功，不表示已签到。完整签到模式只有输出“签到成功”或“今日已签到”且退出码为 0 才算成功。

参数错误、登录失效、接口错误或确认失败时退出码为 1。为防止不确定的重复提交，程序在发送签到前创建当天的防重标记。提交超时或确认不明确时，后续运行仍可查询状态，但若服务器显示未签，会停止再次提交并提示人工检查。请在 App 中确认并处理；即使程序在发送前意外退出，也可能需要人工处理。防重仅覆盖同一安装目录和 Windows 本地日期。

## 4. 安装每天 00:01 自动运行

先确认手动查询和签到正常，再执行本目录的安装脚本：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\安装自动任务.ps1
```

脚本会设置：

- 每天本机时间 00:01，以及当前用户登录 Windows 时检查。
- 另在 08:01、12:01、18:01、22:01 用独立任务补查；补查隐藏窗口运行，且不主动唤醒睡眠中的电脑。
- 同目录的并发运行通过当天防重标记阻止重复提交；不要随意删除防重标记。
- 关机错过后，在登录 Windows、系统可运行时尽快补跑。
- 主任务配置为失败后间隔 5 分钟重跑，最多 3 次；补查时先查询状态。实际重试仍受电脑和 Windows 任务计划程序状态影响。
- 允许电池供电，任务直接运行本地脚本，无需 Codex。

脚本会更新“联想每日自动签到”和“联想签到定时补查”任务，并禁用旧的“联想签到漏跑检查”任务。隐藏运行只适用于补查，00:01 和登录时的主任务仍使用原启动方式。请勿同时运行根目录模拟器版的安装脚本，否则会切回模拟器版。

电脑必须登录到导入配置的 Windows 用户并联网；关机时无法签到。需要北京时间 00:01 时，请将 Windows 时区设为北京时间。

查看任务：

```powershell
Get-ScheduledTaskInfo -TaskName "联想每日自动签到"
Get-ScheduledTaskInfo -TaskName "联想签到定时补查"
```

卸载任务：

```powershell
Unregister-ScheduledTask -TaskName "联想每日自动签到" -Confirm:$false
Unregister-ScheduledTask -TaskName "联想签到定时补查" -Confirm:$false
```

安装后请勿移动目录；移动后需要重新安装任务。

## 日志与结果

定时任务通过 `定时签到.cmd` 启动，结果追加到同目录的 `checkin.log`，包含开始时间、结果、退出码。双击 `查看日志.cmd` 即可打开。

例如：

```text
[日期 时间] START
签到成功；连续签到 ... 天。
[日期 时间] EXIT_CODE=0
```

手动运行的结果直接显示在窗口，只有定时启动器会追加日志。直连版没有模拟器页面，因此不生成截图或页面 XML。

## 验证、限制与隐私

2026-10-18 已通过 Windows 计划任务完成真实联网签到，并再次向服务器查询确认成功。离线测试包含 RSA/AES 往返、跨运行及并发防重、状态不明停止和安全错误日志：

```powershell
node --test checkin.test.mjs configure.test.mjs
```

发布包仅含源码、示例和指南，不包含登录态、日志、个人配置、APK 或设备备份。不要将任何真实配置、App 原始请求或账号日志上传到公开仓库。

登录态过期时，需要重新登录 App 并导入新配置；服务端协议升级也可能导致失效。遇到安全验证或账号限制，请回到 App 手动处理。

这是非官方工具，无法保证服务端永久兼容。源代码遵循仓库的 MIT License。
