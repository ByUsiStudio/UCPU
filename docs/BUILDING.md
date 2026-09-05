# UCPU 开发者编译文档 (BUILDING)

> 本文档面向开发者: 环境搭建、Go 原生库编译、字节码/CROM 构建产物、独立可执行文件打包、日志与调试、扩展指南。
> CIN 语言使用方法见 [CIN 编程指南](CIN_GUIDE.md)。

---

## 目录

- [1. 项目结构](#1-项目结构)
- [2. 环境要求](#2-环境要求)
- [3. 从源码运行](#3-从源码运行)
- [4. 构建 Go 原生加速库](#4-构建-go-原生加速库)
- [5. 构建产物: .bin 字节码与 .crom 镜像](#5-构建产物-bin-字节码与-crom-镜像)
- [6. 打包独立可执行文件](#6-打包独立可执行文件)
- [7. 日志系统 (rich) 与 debug 超详细输出](#7-日志系统-rich-与-debug-超详细输出)
- [8. 回归验证](#8-回归验证)
- [9. 扩展指南: 新增指令 / 系统调用](#9-扩展指南-新增指令--系统调用)
- [10. 常见问题](#10-常见问题)

---

## 1. 项目结构

```
UCPU/
├── cpu.py                  # 入口 (转发到 ucpu.cli)
├── ucpu/                   # 主 Python 包
│   ├── __init__.py         # 包导出: CPU / Config / Opcode / 异常类
│   ├── cli.py              # 命令行入口: 参数解析 -> 加载 -> 运行
│   ├── config.py           # 运行配置 (dataclass) 与 CLI 参数映射
│   ├── console.py          # rich 封装: Console / Table / Panel / Colors 适配层
│   ├── logger.py           # rich 日志: DEBUG/INFO/WARNING/ERROR + trace/dump/hexdump
│   ├── isa.py              # 指令集定义: Opcode(112) / Syscall / Cond / Constants
│   ├── assembler.py        # ASM / PL 汇编器 (统一入口, PL 关键字映射)
│   ├── cin.py              # CIN 高级语言编译器 (词法/语法/代码生成)
│   ├── cpu.py              # CPU 核心: 解释执行 + 逐指令追踪
│   ├── jit.py              # Python JIT: 基本块动态编译 (exec 缓存)
│   ├── memory.py           # FastMemory: 内存 + 保护 + 读写日志
│   ├── registers.py        # RegisterFile (X0-X31 + XZR) / VectorRegisterFile
│   ├── cache.py            # LRU 缓存 (可配置行数/关联度)
│   ├── stats.py            # 统计: 指令/周期/缓存/分支/JIT
│   ├── crom.py             # CROM v3 内存镜像 存/取 + .bin 字节码
│   ├── native.py           # Go 原生库 ctypes 桥接 (自动回退纯 Python)
│   ├── debugger.py         # 交互式调试器 (--step)
│   └── errors.py           # 异常层次: CPUSimulatorError 及子类
│   └── native/             # Go 原生库源码
│       ├── go.mod          # Go 模块定义
│       ├── main.go         # 导出符号: ucpu_run / ucpu_crom_pack / ...
│       ├── vm.go           # 原生字节码 VM
│       ├── crom.go         # CROM 压缩/解压 (Go 端)
│       ├── build.ps1       # Windows 构建脚本
│       └── build.sh        # Linux / Termux / macOS 构建脚本
├── basic.cin               # CIN 综合示例 (回归基准)
├── test_asm.asm            # 汇编测试样例
├── ucpu.spec               # PyInstaller 打包配置
└── docs/                   # 文档 (本目录)
```

三条执行路径共享同一套 ISA / 汇编器 / 编译器:

| 路径 | 说明 | 选择方式 |
|------|------|----------|
| 解释执行 | 纯 Python, 逐指令 dispatch, 支持全部 debug 功能 | 默认; `--no-native --jit 不加` |
| JIT | 基本块动态编译为 Python 机器码, 与 debug 互斥 | `--jit` |
| Go 原生 | 整程序交给 c-shared VM 一次执行, 速度最快 | 默认优先; `--no-native` 强制关闭 |

回退顺序: 原生库缺失或加载失败 -> 自动回退 JIT (若启用) -> 纯 Python 解释执行。

---

## 2. 环境要求

| 组件 | 版本 | 必需 | 用途 |
|------|------|------|------|
| Python | 3.8+ | 是 | 解释器 / JIT / 工具链 |
| rich | 任意近期版本 | 是* | 终端输出、日志、表格、错误面板与彩色 traceback |
| Go | 1.21+ | 否** | 编译原生加速库 |
| C 编译器 | gcc / clang | 随 Go | Go cgo (c-shared 模式) 需要 |
| PyInstaller | 任意 | 否 | 打包独立 exe |

\* rich 为唯一第三方依赖, 未安装时可尝试运行但输出/日志功能受限。
\** 不编译原生库也可运行, 会自动回退纯 Python (性能下降)。

安装依赖:

```bash
pip install rich
```

---

## 3. 从源码运行

```bash
git clone https://github.com/ByUsiStudio/ucpu.git
cd ucpu

python cpu.py basic.cin              # CIN 程序 (优先尝试 Go 原生)
python cpu.py basic.cin --no-native  # 强制纯 Python 解释执行
python cpu.py basic.cin --jit --no-native
python cpu.py test_asm.asm           # 汇编程序
python cpu.py program.pl             # PL 关键字风格汇编
python cpu.py --help                 # 完整帮助
```

常用命令行选项 (完整列表见 `python cpu.py --help`):

| 选项 | 作用 |
|------|------|
| `--no-native` | 禁用 Go 原生库, 强制纯 Python |
| `--jit` | 启用 Python JIT (基本块编译) |
| `--debug` | **超详细 rich 调试**: 逐指令/寄存器/内存/栈/缓存追踪 (强制 DEBUG 日志级别) |
| `--step` | 交互式单步调试器 |
| `--profile` | 结束后输出性能统计表 |
| `--compile` / `--compile-only` | 编译为 .bin 字节码 |
| `--crom <file>` | 加载 .crom 内存镜像 |
| `--save` / `--no-compress` | 保存 .crom / 关闭 zlib 压缩 |
| `-o, --output <file>` | 指定 .crom / .bin 输出路径 |
| `--mem-size <bytes>` | 内存大小 (默认 65536) |
| `--max-instructions <n>` | 指令数上限 (防死循环) |
| `--cache-size <n>` | 缓存行数 |
| `--no-io` | 禁止 IN/OUT 宿主 I/O |
| `--strict` | 严格汇编模式 |
| `--log-level <lvl>` | DEBUG / INFO / WARNING / ERROR |
| `--log-file <file>` | 日志重定向到文件 |

> 注意: `--debug` 与 `--jit` 互斥 (debug 需要逐指令解释追踪); 同时给出时 debug 优先。

---

## 4. 构建 Go 原生加速库

原生库通过 Go `-buildmode=c-shared` 编译为共享库, 由 `ucpu/native.py` 用 ctypes 加载。导出接口:

| 符号 | 功能 |
|------|------|
| `ucpu_run` | 原生字节码 VM, 一次载入整程序执行, 返回完整状态快照 |
| `ucpu_free` | 释放返回缓冲区 |
| `ucpu_crom_pack` | CROM 打包 (含 zlib 压缩) |
| `ucpu_crom_unpack` | CROM 解包校验 |
| `ucpu_version` | 版本字符串 |

### Windows (PowerShell)

依赖: Go 1.21+ 与 cgo 可用的 C 编译器 (MinGW-w64 / TDM-GCC 的 `gcc`, 需在 PATH)。

```powershell
cd ucpu\native
.\build.ps1
```

产物: `ucpu/ucpu_native.dll` (c-shared 附带的 `ucpu_native.h` 会被脚本自动删除)。

### Linux

```bash
sudo apt install golang gcc    # 或使用发行版等价命令
cd ucpu/native
sh build.sh
```

产物: `ucpu/libucpu_native.so`

### Termux (Android)

```bash
pkg install golang
cd ucpu/native
sh build.sh    # Termux 自带 cgo 工具链, 支持 c-shared
```

### macOS

```bash
xcode-select --install   # clang
brew install go
cd ucpu/native
sh build.sh
```

产物: `ucpu/libucpu_native.dylib`

### 验证

```bash
python -c "from ucpu import native; print(native.load_native_library())"
```

输出非 `None` 即加载成功。之后运行程序时日志会出现原生库路径; 若失败可看到回退 warning, 加 `--no-native` 可复现纯 Python 行为。

> 手动编译等价命令: `go build -buildmode=c-shared -o ../ucpu_native.dll .` (在 `ucpu/native/` 目录)。

---

## 5. 构建产物: .bin 字节码与 .crom 镜像

### .bin (UCBC 字节码)

汇编/CIN 统一编译产物, 头部 `UCBC`。格式:

```
头部: magic[4]='UCBC' | version u8 | entry u32 | instr_count u32
指令: opcode u8 | argc u8
操作数: kind u8 | value i64 | extra i64   (小端, 每操作数 17 字节)
```

操作数 kind: `0=reg 1=imm 2=vec 3=veclane 4=mem 5=cond 6=float(bits) 7=str`。

生成与执行:

```bash
python cpu.py basic.cin --compile-only -o basic.bin   # 仅编译
python cpu.py basic.cin --compile                     # 编译并继续执行
python cpu.py basic.bin                               # 直接运行字节码
```

### .crom (内存镜像, v3)

| 偏移 | 大小 | 字段 | 说明 |
|------|------|------|------|
| 0x00 | 4 | Magic | `'CROM'` |
| 0x04 | 1 | Version | `0x03` |
| 0x05 | 4 | Memory Size | 内存字节数 |
| 0x09 | 1 | Flags | bit0: zlib 压缩 |
| 0x0A | 4 | Checksum | CRC32 |
| 0x0E | 2 | Reserved | 保留 |
| 0x10 | N | Data | 压缩/原始内存 |

```bash
python cpu.py basic.cin --save                  # 运行后保存 basic.crom (zlib)
python cpu.py basic.cin --save --no-compress    # 不压缩
python cpu.py --crom basic.crom                 # 加载镜像运行
```

镜像由原生库 (Go) 或纯 Python (zlib) 打包, 两种实现二进制兼容。

---

## 6. 打包独立可执行文件

使用 PyInstaller (配置见 `ucpu.spec`):

```bash
pip install pyinstaller
pyinstaller cpu.py --name ucpu          # 等价 build_win.bat
# 或使用 spec:
pyinstaller ucpu.spec
```

产物在 `dist/ucpu/`。注意:

- 分发包时应同时附带编译好的原生库 (`ucpu_native.dll` / `libucpu_native.so`), 或接受纯 Python 回退。
- `--debug`/`--step` 的 rich 输出在无终端环境 (windowed) 下不可用, spec 中保持 `console=True`。

---

## 7. 日志系统 (rich) 与 debug 超详细输出

### 架构

- `ucpu/console.py`: rich 的适配层。所有模块禁止直接 `print`, 统一经 `Console.print` / `Panel` / `Table` / `Colors` 输出。
- `ucpu/logger.py`: 基于 `rich.logging.RichHandler` 的日志器, 级别 `DEBUG < INFO < WARNING < ERROR`, 支持 `--log-file` 重定向。
- 错误统一 rich 面板化: 加载/汇编/编译/运行错误均输出红色 `Panel`; debug 模式下附带 `rich` 彩色完整 traceback (`Console.print_exception`)。

### 日志级别行为

| 级别 | 内容 |
|------|------|
| `ERROR` | 仅错误面板 |
| `WARNING` | + 回退/降级告警 (如原生库缺失) |
| `INFO` (默认) | + 编译汇总 (指令数)、执行起止、统计表 |
| `DEBUG` | **超详细**: 全部埋点 + 逐指令追踪 |

开启方式: `--debug` (隐含 DEBUG) 或 `--log-level DEBUG`。

### DEBUG 超详细内容清单

1. **CPU 初始化 dump**: 内存大小、缓存拓扑、SP 初值、堆基址、路径选择。
2. **逐指令追踪** (每条指令前后各一行):
   ```
   PC=0x0004 #00000002 ADD X1=0x0(0) X2=0x1(1)  SP=0xfff8
     => pc=0x0005 N=0 Z=0 C=0 V=0
   ```
   含 PC、全局指令序号、操作数当前值 (十六进制+十进制)、SP、执行后 PC 与 NZCV 标志。
3. **内存读写追踪**: `MEM WR @0x000c w=1 value=0x0` / `MEM RD`, 覆盖 LOAD/STORE/PUSH/POP/STR/LDR 全家。
4. **栈操作、缓存命中/缺失、SYS 系统调用** (功能号 + 参数)。
5. **编译/汇编/JIT 埋点**: tokenize 数量、struct/global/function 统计、JIT 块源码 dump、原生库调用参数。

### 文件日志

```bash
python cpu.py basic.cin --debug --log-file ucpu.log
```

---

## 8. 回归验证

三路径输出一致性是核心约束 (合法差异: 时间戳、`rand` 序列、浮点末位舍入):

```bash
python cpu.py basic.cin --no-native            # 解释
python cpu.py basic.cin --jit --no-native      # JIT
python cpu.py basic.cin                        # Go 原生
python cpu.py test_asm.asm --debug --no-native # debug 逐指令追踪
python cpu.py basic.cin --compile-only && python cpu.py basic.bin  # 字节码路径
```

验收标准:

- [ ] 三路径 `basic.cin` 输出一致 (上述合法差异除外)
- [ ] `test_asm.asm` 三路径一致
- [ ] `--debug` 出现 `PC=0x... #...` 逐指令行与初始化 dump
- [ ] `.bin` 编译往返 (compile -> run) 与直接运行一致
- [ ] 缺失原生库时回退 warning 且结果正确

---

## 9. 扩展指南: 新增指令 / 系统调用

新增一条指令需要同步改动的位置 (以 `MINUS` 为例):

1. `ucpu/isa.py`
   - `Opcode` 枚举追加成员 (新编号);
   - `Constants.OPCODE_NAMES` / `OPCODE_NAME_TO_ENUM` 加显示名;
   - `Constants.ARG_COUNTS` 声明参数个数 (`-1` 为变长);
   - 如是分支/浮点类, 加入 `BRANCH_OPS` / `FP_OPS` 集合 (统计用)。
2. `ucpu/cpu.py` — `execute()` 的 dispatch 表加实现 (解释路径)。
3. `ucpu/jit.py` — JIT 代码生成加分支 (否则该指令所在块会回退解释执行)。
4. `ucpu/native/vm.go` — 原生 VM `switch` 加实现; 不实现时返回 `statusUnsupported`, Python 端自动回退。
5. `ucpu/assembler.py` — 若有特殊操作数语法, 在汇编器适配; 常规 `reg/imm/label/mem` 自动支持。
6. `ucpu/cin.py` — 如需暴露给 CIN, 在 `Syscall` 加功能号并在 `cpu.py`/`vm.go` 的 SYS handler 实现宿主调用。

新增系统调用 (SYS): `isa.py: Syscall` 编号 -> `cpu.py` SYS 分支 -> `vm.go` SYS 分支 -> `cin.py:_gen_call` 内建映射。四处编号必须一致。

---

## 10. 常见问题

**Q: 提示原生库加载失败?**
Go 库依赖系统 C 运行时; Windows 缺少 MinGW 运行库、Linux 未装 `gcc` 时 cgo 产物可能无法加载。检查日志 warning, 或 `--no-native` 回退纯 Python。

**Q: `--debug` 下程序明显变慢?**
正常。逐指令追踪 + 内存日志开销大; debug 与 JIT 互斥也是为了追踪完整性。生产性能测试用 `--jit` 或原生路径。

**Q: rich 未安装会怎样?**
建议始终安装 (`pip install rich`); 所有终端美化、表格、彩色 traceback 都依赖它。

**Q: .bin 与 .crom 有什么区别?**
`.bin` 是代码字节码 (UCBC), 由 VM 执行; `.crom` 是运行时内存快照 (CROM v3), 用于保存/恢复整机状态, 两者不通用。

**Q: 浮点结果与其他路径末位不一致?**
允许的差异: 不同实现中三角/超越函数库 (Python math vs Go math) 的 libm 实现可能有 1 ulp 内的舍入差异。
