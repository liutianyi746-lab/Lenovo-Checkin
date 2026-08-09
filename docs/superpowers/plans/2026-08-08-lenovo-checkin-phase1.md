# 联想 App 自动签到第一阶段实现计划

> **面向 AI 代理的工作者：** 在当前会话中按测试驱动方式执行；当前目录不是 Git 仓库，因此跳过 worktree 与 commit。

**目标：** 创建 Windows 下可自动启动/发现雷电模拟器、连接 ADB 与 uiautomator2、导航到联想 App 签到页面并保存现场的完整 Python 项目，且绝不点击最终签到按钮。

**架构：** 配置、模拟器、设备、App 生命周期、页面导航和现场采集分别封装。入口脚本只编排流程；XML 解析与可点击父节点定位使用纯函数，以便脱离真实设备测试。

**技术栈：** Python 3.11、uiautomator2、PyYAML、pytest（开发验证）、标准库 subprocess/logging/XML。

---

### 任务 1：配置与基础模型

**文件：** `config.py`、`config.yaml`、`tests/test_config.py`

- [ ] 先测试默认配置、相对路径解析和非法值校验。
- [ ] 运行 `python -m pytest tests/test_config.py -q`，确认因模块缺失失败。
- [ ] 实现类型化配置加载，并创建输出目录。
- [ ] 重跑测试，确认通过。

### 任务 2：ADB 与雷电发现

**文件：** `emulator.py`、`device.py`、`tests/test_emulator.py`

- [ ] 先测试 `adb devices` 解析、多设备下雷电候选排序和实例索引。
- [ ] 确认测试因实现缺失失败。
- [ ] 实现可注入的 subprocess 调用、常见路径/注册表/进程发现、启动与 boot_completed 轮询。
- [ ] 重跑测试，确认通过。

### 任务 3：Hierarchy 与导航

**文件：** `navigation.py`、`utils/hierarchy.py`、`tests/test_navigation.py`、`tests/test_hierarchy.py`

- [ ] 先以固定 XML 测试页面识别、重要节点过滤和最近可点击父节点。
- [ ] 确认测试失败。
- [ ] 实现纯 XML 解析、页面状态机、选择器优先点击与安全验证检测。
- [ ] 重跑测试，确认通过。

### 任务 4：运行入口与诊断

**文件：** `app.py`、`main.py`、`inspect.py`、`checkin.py`、`utils/logger.py`、`utils/screenshot.py`

- [ ] 先测试第二阶段接口必定拒绝执行最终签到。
- [ ] 实现 App 生命周期、第一阶段编排、异常现场保存和独立检查脚本。
- [ ] 运行全部测试。

### 任务 5：文档与最终验证

**文件：** `README.md`、`requirements.txt`、`.gitignore`

- [ ] 写明安装、ADB、雷电配置、首次运行、诊断和故障材料收集。
- [ ] 运行 `python -m compileall .`、`python -m pytest -q`。
- [ ] 运行只读本机探测，判断能否进行实机测试；不可用时给出准确下一步命令。
