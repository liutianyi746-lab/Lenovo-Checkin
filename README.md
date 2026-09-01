# 联想签到器

一个运行在 Windows 10/11 上的 Python 自动签到工具。程序通过 ADB 和 `uiautomator2` 控制雷电模拟器，启动联想 App（包名 `com.lenovo.club.app`），依次进入“首页 → 我的 → 签到领好礼”，判断当天是否已签到，并在完成后关闭模拟器。

程序只会点击真实页面中确认过的签到控件 `com.lenovo.club.app:id/img_do_sign` 一次。如果当天已经签到，就直接退出，不会重复点击。

## 功能

- 自动发现或启动雷电模拟器实例 0
- 自动连接在线的 Android 模拟器设备
- 优先通过 `ldconsole.exe` 启动指定实例；首次启动超时会清理现场并自动重试一次
- 使用进程锁阻止两个计划任务同时控制同一个模拟器
- 自动关闭已识别的广告弹窗
- 自动导航到“签到有礼”页面
- 未签到时只点击一次签到按钮
- 已签到时不执行重复操作
- 保存日志、结果截图和页面 hierarchy XML
- 遇到验证码、滑块、短信验证、设备验证、账号安全验证或风控页面时立即停止
- 无论成功、已签到或失败，运行结束后均可配置为关闭雷电模拟器

## 环境要求

- Windows 10 或 Windows 11
- Python 3.11 或更高版本
- 雷电模拟器
- 联想 App，包名必须为 `com.lenovo.club.app`
- 雷电模拟器已开启 ADB 调试

检查 Python：

```powershell
python --version
```

如果命令不存在，请先安装 Python 3.11+，并在安装界面勾选“Add Python to PATH”。

## 1. 下载项目

在 GitHub 仓库页面点击“Code → Download ZIP”，解压到一个固定目录，例如：

```text
C:\Tools\联想签到器
```

也可以使用 Git：

```powershell
git clone https://github.com/liutianyi746-lab/Lenovo-Checkin.git
cd 联想签到器
```

## 2. 安装依赖

在项目目录中打开 PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

如果 PowerShell 禁止激活脚本，可以不激活虚拟环境，直接执行：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 3. 安装并准备联想 App

本仓库不上传、不分发联想 App 的 APK。用户指定的第三方下载页面：

- [联想社区 Android 版下载](https://www.downxia.com/downinfo/143337.html)

这是第三方下载来源，请自行判断来源可信度并在安装前进行安全检查。安装后必须先手动打开 App、登录自己的账号，并确认能够正常进入首页。

## 4. 配置雷电模拟器

1. 打开雷电模拟器设置。
2. 开启 ADB 调试或本地连接。
3. 将联想 App 安装到实例 0。
4. 手动登录联想账号。
5. 关闭可能遮挡页面的新手引导。

项目默认配置为自动查找雷电和 ADB：

```yaml
ldplayer:
  auto_start: true
  executable_path: auto
  instance_index: 0
  startup_timeout: 120
  close_after_run: true

adb:
  address: auto
  connect_timeout: 30
  executable_path: adb
```

如果自动查找失败，直接双击项目根目录的：

```text
首次配置.bat
```

把自己电脑上的 `dnplayer.exe` 拖入窗口并按回车。脚本会优先寻找同目录的 `adb.exe`，然后生成仅供这台电脑使用的 `config.local.yaml`。

需要手工配置时，也可以创建 `config.local.yaml`，复制 `config.yaml` 的全部内容后，把两个路径改成自己的实际位置，例如：

```yaml
ldplayer:
  executable_path: C:\LDPlayer\LDPlayer9\dnplayer.exe

adb:
  executable_path: C:\LDPlayer\LDPlayer9\adb.exe
```

`config.local.yaml` 不会被 Git 上传。程序会优先读取它；文件不存在时才读取公开的 `config.yaml`。

## 5. 首次检查

先启动雷电模拟器，然后检查 ADB：

```powershell
adb devices
```

如果 `adb` 没有加入 PATH，可直接使用雷电目录中的 `adb.exe`：

```powershell
& "C:\你的雷电目录\adb.exe" devices
```

设备状态应为 `device`。然后执行只读页面检查：

```powershell
python inspect.py
```

`inspect.py` 只保存当前页面的截图和 XML，不会导航，也不会点击签到。

## 6. 手动运行一次

```powershell
python main.py
```

使用虚拟环境但未激活时：

```powershell
.\.venv\Scripts\python.exe main.py
```

完整流程为：

```text
启动/连接雷电 → 启动联想 App → 首页 → 我的 → 签到领好礼
→ 判断今日状态 → 必要时点击一次签到 → 保存结果 → 关闭雷电
```

如果同一时间已经有一个签到任务在运行，新启动的任务会立即以退出码 `2` 结束，不会与前一个任务争抢模拟器。雷电首次启动在 120 秒内未就绪时，程序会关闭该实例、断开旧 ADB、等待 5 秒后再启动一次；第二次仍失败则保存日志并以非零退出码结束。

## 7. 如何判断是否成功

最方便的方式是双击项目根目录的：

```text
查看日志.bat
```

它会用记事本打开 `logs\checkin.log`；如果日志尚未生成，会提示先运行一次签到程序。也可以直接双击 `logs\checkin.log`。

需要在程序运行时实时观察日志，可在项目目录打开 PowerShell：

```powershell
Get-Content .\logs\checkin.log -Wait
```

只有程序退出码为 `0`，并且日志出现以下任意一句，才算成功：

```text
今日已经签到，无需重复操作
```

或：

```text
签到成功
```

同时可以查看最新文件：

- `screenshots\checkin_result_日期时间.png`：结果页面截图
- `dumps\checkin_result_日期时间.xml`：结果页面 hierarchy
- `screenshots\checkin_page.png`：进入签到页时的截图
- `dumps\checkin_page.xml`：进入签到页时的 hierarchy

如果只有日志但没有截图，通常表示错误发生在设备连接之前。

## 8. 设置每天 00:01 自动运行

先确认手动运行成功，然后在项目目录打开 PowerShell，执行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\安装自动任务.ps1
```

脚本会注册或更新两个本地任务：

- `联想每日自动签到`：每天 00:01 运行；如果当时关机或休眠，Windows 可用后尽快运行。
- `联想签到漏跑检查`：用户登录 Windows 时检查当天日志；只有当天没有成功记录时才调用 `main.py` 补跑，已经签到则不会启动雷电。

主任务失败后每隔 5 分钟重试一次，最多重试 3 次。两个任务都设置为已有实例运行时不启动新实例，并继续由 `main.py` 负责运行锁、幂等签到、安全验证和关闭雷电。

查看任务状态：

```powershell
Get-ScheduledTask -TaskName "联想每日自动签到", "联想签到漏跑检查"
```

手动测试漏跑检查：

```powershell
Start-ScheduledTask -TaskName "联想签到漏跑检查"
Get-ScheduledTaskInfo -TaskName "联想签到漏跑检查"
```

`LastTaskResult` 为 `0` 表示检查程序正常结束。若今天已经成功签到，这次检查不会打开雷电。

如需删除这两个任务：

```powershell
Unregister-ScheduledTask -TaskName "联想每日自动签到" -Confirm:$false
Unregister-ScheduledTask -TaskName "联想签到漏跑检查" -Confirm:$false
```

计划任务直接运行本地 Python 程序，不依赖 Codex。电脑错过 00:01 没关系，但需要在当天登录 Windows，且当前 Windows 账号需要具备启动雷电模拟器的权限。

## 9. 广告和安全验证

程序只关闭已确认 selector 的广告弹窗。如果出现未知遮挡、页面改版或无法识别的弹窗，会停止并保存现场，不会盲目点击固定坐标。

如果检测到验证码、滑块、短信验证、设备验证、账号安全验证或风控文字，程序不会尝试破解或绕过。请手动完成验证后再运行。

## 常见问题

### 找不到 Python

重新安装 Python 3.11+ 并勾选“Add Python to PATH”，关闭 PowerShell 后重新打开。

### 找不到 ADB 或雷电

先双击 `首次配置.bat`，把自己电脑上的 `dnplayer.exe` 拖入窗口。脚本会自动生成 `config.local.yaml`。路径包含中文或空格也可以正常使用。

### `adb devices` 没有设备

确认雷电已经启动、ADB 调试已开启，然后执行：

```powershell
adb kill-server
adb start-server
adb devices
```

### App 未安装

检查包名：

```powershell
adb shell pm list packages | Select-String com.lenovo.club.app
```

没有输出时，需要把联想 App 安装到当前雷电实例。

### 找不到“首页”“我的”或“签到领好礼”

保持 App 停在异常页面，运行：

```powershell
python inspect.py
```

检查新生成的 `screenshots\inspect_*.png` 和 `dumps\inspect_*.xml`。页面改版、登录失效、广告遮挡或 WebView 未加载都可能导致 selector 失效。

### 运行失败后应提供什么

排查问题时可提供以下文件，但请先检查并遮盖账号昵称、头像、手机号和设备序列号：

1. `logs\checkin.log`
2. 最新的 `screenshots\error_*.png`
3. 与截图同一时间生成的 `dumps\error_*.xml`
4. `adb devices` 输出
5. 脱敏后的配置文件

## 隐私与风险说明

- 本项目是非官方开源工具，与联想及第三方下载站无隶属或合作关系。
- 自动化操作可能违反 App 的服务规则，也可能触发账号风控；使用者需自行评估并承担风险。
- 请勿把登录信息、账号截图、日志、XML、设备序列号或个人路径提交到公开仓库。
- 本项目不收集账号密码，不破解验证码，不绕过安全验证。

## 开发与测试

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m ruff check .
```

## 许可证

源代码采用 [MIT License](LICENSE)。联想 App、商标、内容和第三方下载文件不包含在本许可证中。
