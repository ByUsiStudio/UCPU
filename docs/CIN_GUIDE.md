# CIN 编程指南

> CIN 是 UCPU 的高级语言, 语法近似 C/Go: 函数、struct、数组 (含多维)、浮点、字符串。
> CIN 编译为 UCPU 字节码后由解释器 / JIT / Go 原生 VM 三路径执行, 行为一致。
> 开发环境/构建相关见 [开发者编译文档](BUILDING.md)。

---

## 目录

- [1. 第一个程序](#1-第一个程序)
- [2. 词法规则](#2-词法规则)
- [3. 类型系统](#3-类型系统)
- [4. 变量与作用域](#4-变量与作用域)
- [5. 运算符](#5-运算符)
- [6. 控制流](#6-控制流)
- [7. 函数](#7-函数)
- [8. struct](#8-struct)
- [9. 数组](#9-数组)
- [10. 字符串](#10-字符串)
- [11. 内建函数](#11-内建函数)
- [12. 内嵌 CPU 指令语句](#12-内嵌-cpu-指令语句)
- [13. 编译与运行](#13-编译与运行)
- [14. 限制与注意事项](#14-限制与注意事项)
- [15. 常见错误](#15-常见错误)

---

## 1. 第一个程序

```cin
function main() -> int {
    println("Hello, UCPU!")
    println("2 + 3 = " + (2 + 3))
    return 0
}
```

运行:

```bash
python cpu.py hello.cin
```

`main` 为入口 (不要求必须有 `main`, 程序从第一条指令开始执行, 按源码顺序先执行全局初始化)。

**语句以换行结尾** (分号可选)。字符串用 `+` 与任意类型拼接, `println` 自动追加换行。

---

## 2. 词法规则

| 元素 | 规则 |
|------|------|
| 注释 | `// 行注释` 与 `/* 块注释 */` |
| 标识符 | 字母/`_` 开头, 字母/数字/`_` 组成, 区分大小写 |
| 整数字面量 | `42`, `-7` |
| 浮点字面量 | `3.14`, `1e-5` (支持科学计数法) |
| 字符串字面量 | `"..."`, 支持转义 `\n \t \r \" \\ \0` |
| 布尔字面量 | `true` / `false` |
| 语句分隔 | 换行 (推荐) 或 `;` |

**续行规则**: 圆括号/方括号内换行会自动连接; 行尾以运算符 (`+ - * / % = < > <= >= == != && || , . ->`) 结尾也会连接。花括号 `{}` 块内换行必须保留 (语句终止符)。

```cin
// 可行: 行尾运算符续行
int long_result = value1 + value2 +
                  value3

// 可行: 括号内续行
float x = (a + b) *
          (c + d)
```

---

## 3. 类型系统

| 类型 | 说明 | 默认值 |
|------|------|--------|
| `int` | 64 位有符号整数 | `0` |
| `float` | 64 位 IEEE754 浮点 | `0.0` |
| `bool` | 布尔 | `false` |
| `string` | NUL 结尾字符串指针 | `""` |
| `void` | 仅函数返回类型 | - |
| `StructName` | 用户定义 struct | 全零 |
| `T[n]` / `T[n][m]` | 固长数组 (值语义) | 全零 |
| `T[]` / `int[][]` | 指针形式数组 (参数/返回) | 空指针 |

类型转换规则:

- `int` / `bool` 参与浮点运算时**自动提升**为 `float` ( `/` 恒为浮点除法; 整数取模用 `%` );
- `float -> int` 显式场景需内建 (见 [内建函数](#11-内建函数));
- `bool` 打印为 `"true"` / `"false"`, 数值上下文中为 `1` / `0`。

---

## 4. 变量与作用域

```cin
// 全局变量 (文件顶层)
int counter = 0
float pi = 3.14159265
string greeting = "hello"
Person admin                 // struct 默认全零
int primes[20]               // 固长数组
float grid[7][24]            // 二维数组
int matrix[2][3] = { {1, 2, 3}, {4, 5, 6} }   // 数组字面量

function demo() -> void {
    int local = 10           // 局部变量
    int a = 1, b = 2         // 一行多声明
    string s = "x" + "y"
    local = local + a        // 赋值
}
```

- 全局变量支持数组字面量 `{...}` 初始化 (可嵌套表示多维)。
- 局部变量在进入所在块时分配, 离开释放; 同名内层变量遮蔽外层。
- 未初始化的变量为类型默认值。

---

## 5. 运算符

按优先级从低到高:

| 优先级 | 运算符 | 说明 | 适用类型 |
|--------|--------|------|----------|
| 1 | `\|\|` | 逻辑或 (短路) | bool (任意类型可转 bool) |
| 2 | `&&` | 逻辑与 (短路) | bool |
| 3 | `==` `!=` | 相等比较 | 全部 |
| 4 | `<` `>` `<=` `>=` | 关系比较 | int/float |
| 5 | `+` `-` | 加减, `+` 兼作字符串拼接 | int/float/string |
| 6 | `*` `/` `%` | 乘除取模 (`/` 浮点除, `%` 仅整数) | int/float |
| 7 | `!` `-x` | 逻辑非 / 负号 | bool / int-float |
| 8 | `[]` `.` `f()` | 下标 / 成员 / 调用 | - |

赋值 `=` 是右结合表达式: `a = b = c + 1` 合法。

字符串拼接: `+` 任意一侧为 `string` 时, 另一侧自动字符串化 (int/float/bool)。

```cin
println("Age: " + 18)            // Age: 18
println("PI: " + 3.14)           // PI: 3.14
println("OK: " + true)           // OK: true
```

---

## 6. 控制流

### if / else

```cin
if (x > 0) {
    println("positive")
} else if (x == 0) {
    println("zero")
} else {
    println("negative")
}

// 单语句体可省略花括号
if (done) return
```

### while

```cin
while (n > 0) {
    sum = sum + n
    n = n - 1
}
```

### for

```cin
for (int i = 0; i < 10; i = i + 1) {
    println("i = " + i)
}
```

三段均可省略: `for (;;) { break }`。init 段支持类型声明; update 段为赋值表达式。

### break / continue

```cin
while (true) {
    x = x + 1
    if (x >= 10) {
        break
    }
    if (x % 2 == 0) {
        continue
    }
    println("odd: " + x)
}
```

条件短路求值: `&&` 左侧为假时右侧不求值; `||` 左侧为真时右侧不求值。

---

## 7. 函数

```cin
// 定义: function 名(参数表) -> 返回类型 { ... }
function add(int a, int b) -> int {
    return a + b
}

function swap(int[] arr, int i, int j) -> void {
    int t = arr[i]
    arr[i] = arr[j]
    arr[j] = t
}

// 无返回值时 -> 可省略 (默认 void)
function greet() {
    println("hi")
}
```

- 参数按值传递; 数组参数 (`int[]` / `T[]`) 与 struct 退化为引用传递 (修改可见)。
- 固长数组作参数写 `int[5]`, 传入后衰减为指针形式。
- 递归支持 (调用栈由 VM 栈承载, 默认栈深有限, 见 [限制](#14-限制与注意事项))。
- 返回值通过 `X0` 传递, `void` 函数 `return` 可省略。

---

## 8. struct

```cin
struct Point {
    float x
    float y
}

struct Rectangle {
    Point top_left        // 嵌套 struct (值内嵌)
    Point bottom_right
    float area
}

function area(Rectangle r) -> float {
    float w = r.bottom_right.x - r.top_left.x
    float h = r.bottom_right.y - r.top_left.y
    return w * h
}
```

- 成员访问用 `.`, 支持链式: `r.bottom_right.x`。
- struct 可整体赋值/传参/返回 (值语义拷贝); 数组字段为值内嵌。

```cin
struct Student {
    Person info
    int grades[5]         // 固长数组字段
    float gpa
}

function make(string name, int age) -> Student {
    Student s
    s.info.name = name
    s.info.age = age
    s.grades[0] = 95
    s.gpa = 88.5
    return s
}
```

> struct 字段不能是变长指针数组 (`T[]`); 只允许标量、嵌套 struct 与固长数组。

---

## 9. 数组

```cin
int a[5]                        // 一维, 全零
float m[3][4]                   // 二维 (行主序)
int init[4] = {1, 2, 3, 4}      // 字面量初始化
int ident[2][2] = { {1, 0}, {0, 1} }

function sum(int[] arr, int n) -> int {
    int s = 0
    for (int i = 0; i < n; i = i + 1) {
        s = s + arr[i]
    }
    return s
}

function zeros(int n) -> int[] {   // 指针数组作返回值
    int[] r
    for (int i = 0; i < n; i = i + 1) {
        r[i] = 0
    }
    return r
}
```

- 下标从 0 开始; 多维逐维下标: `m[day][hour]`。
- 数组名作表达式使用时是指针 (基址); `arr[i]` 即基址偏移取值。
- 局部声明中 `int[] r` 为指针形式, 指向堆/数据区由运行时分配。

---

## 10. 字符串

字符串是 NUL 结尾的字节序列, `string` 变量持有指针。

```cin
string s = "hello"
string t = s + " " + "world"    // 拼接产生新堆块
println(t)                      // hello world
println(strlen(t))              // 11

if (strcmp(s, "hello") == 0) {
    println("equal")
}

string copy = strcpy(s)         // 拷贝为新堆块
```

- `+` 拼接右侧任意类型: `"n = " + 42`、`"pi = " + 3.14`、`"ok = " + true`。
- 不支持 `s[i]` 单字符下标访问; 单字符用拼接/比较等内建操作间接处理。
- 字符串内建: `strlen` / `strcmp` / `strcpy` / `input` (见下表)。

---

## 11. 内建函数

| 函数 | 签名 | 说明 |
|------|------|------|
| `print(x)` | void | 输出不换行 (自动字符串化) |
| `println(x)` | void | 输出并换行; 无参输出空行 |
| `input()` | int | 读入一行并解析为整数 (失败为 0) |
| `abs(x)` | int | 整数绝对值 |
| `sqrt(x)` | float | 平方根 |
| `pow(x, y)` | float | x 的 y 次幂 |
| `sin(x)` / `cos(x)` / `tan(x)` | float | 三角函数 (弧度) |
| `rand()` | int | 非负随机整数 |
| `srand(n)` | void | 设置随机种子 |
| `time()` | int | Unix 时间戳 (秒) |
| `strlen(s)` | int | 字符串长度 |
| `strcmp(a, b)` | int | 字典序比较 (<0 / 0 / >0) |
| `strcpy(s)` | string | 复制为新堆块 |

内建在表达式任意位置可用; 数值参数按需自动提升为 float。

示例:

```cin
function math_demo() -> void {
    float angle = pi / 4
    println("sin(45°): " + sin(angle))
    println("sqrt(16): " + sqrt(16))
    println("pow(2, 8): " + pow(2, 8))
    println("abs(-42): " + abs(-42))
}
```

---

## 12. 内嵌 CPU 指令语句

CIN 保留了 7 条 CPU 风格语句, 直接对变量/立即数做寄存器级操作 (以当前语句所在变量的栈槽为操作数):

| 语句 | 等价含义 |
|------|----------|
| `set x 30` | `x = 30` |
| `add x y` | `x = x + y` |
| `subtract x 5` | `x = x - 5` |
| `multiply x 2` | `x = x * 2` |
| `divide x 4` | `x = x / 4` |
| `increment x` | `x = x + 1` |
| `decrement x` | `x = x - 1` |

```cin
function cpu_ops() -> void {
    int x = 10
    set x 30
    add x 12          // x = 42
    multiply x 2      // x = 84
    subtract x 42     // x = 42
    divide x 6        // x = 7
    increment x       // x = 8
    println("x = " + x)
}
```

第二操作数可为变量或立即数。这组语句是低级特性, 一般场景用常规表达式即可。

---

## 13. 编译与运行

```bash
python cpu.py prog.cin                    # 编译并运行 (自动选择原生/JIT/解释)
python cpu.py prog.cin --no-native        # 强制纯 Python
python cpu.py prog.cin --debug            # 超详细逐指令追踪 (rich)
python cpu.py prog.cin --profile          # 性能统计
python cpu.py prog.cin --compile-only     # 仅编译为 prog.bin (UCBC 字节码)
python cpu.py prog.bin                    # 运行字节码
python cpu.py prog.cin --save             # 运行后保存 prog.crom 内存镜像
```

编译错误输出红色 rich 面板, 带 `文件:行号` 定位:

```
┌──────────────────────── Load Error ────────────────────────┐
│ prog.cin:12: Compiler error: Unknown function: printline   │
└────────────────────────────────────────────────────────────┘
```

---

## 14. 限制与注意事项

1. **无指针/取地址运算**: `&` `*` 不是运算符; "引用" 仅通过数组/struct 传参隐式实现。
2. **无位运算符**: CIN 层没有 `&` `|` `<<` `>>` (避免与逻辑运算混淆); 需要位操作时用内嵌 CPU 语句或汇编。
3. **`/` 恒为浮点除**: 想要整数除法语义请组合使用; `%` 仅支持整数, 浮点取模报错。
4. **递归深度**: 每层调用消耗栈槽 (默认内存 64KB, 栈区约 1024 槽); 过深递归触发栈溢出错误, 可用 `--mem-size` 加大内存。
5. **struct 字段**: 不支持变长指针数组字段; 字符串字段是指针, 拼接/复制会产生新堆块。
6. **全局初始化顺序**: 按声明顺序写入数据区; 数组字面量长度超过声明维度会报错。
7. **函数先定义后使用不强制**: 同文件内的函数可互相调用 (两遍编译); 但变量必须先声明后使用。
8. **字符串不可原位修改**: `strcpy` 返回新堆块; 没有可变的原地字符替换。

---

## 15. 常见错误

| 错误信息 | 原因 | 修正 |
|----------|------|------|
| `Unknown function: xxx` | 调用了未定义/拼错的函数 | 检查函数名或自定义该函数 |
| `Unsupported int operator: xx` | 对整数使用了不支持的运算 | 使用 `+ - * / %` |
| `Float modulo not supported` | 浮点使用 `%` | 先取整或改用整数 |
| `Expected RBRACE ... at line N` | 花括号不配对 / 块内缺换行 | 检查第 N 行附近括号 |
| `Undefined variable: xxx` | 使用未声明变量 | 先声明 |
| `Type mismatch ...` | 赋值/传参类型不匹配 | 显式转换或修改类型 |
| `Stack overflow` | 递归过深 / 栈耗尽 | 减少深度或 `--mem-size` 扩容 |

**调试技巧**:

```bash
python cpu.py prog.cin --debug           # 逐指令 rich 追踪, 定位崩溃点 PC
python cpu.py prog.cin --step            # 交互式单步, print regs / mem / cache
python cpu.py prog.cin --log-level DEBUG --log-file ucpu.log   # 全量日志落盘
```
