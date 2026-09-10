# Knowledge Debt

**代码变了。用两分钟，确认你接得住。**

Knowledge Debt 是一个本地 Python CLI：找出值得检查的代码行为，提出一个有源码依据的问题，
并把你的自查结果与代码版本关联起来。

[English](README.md) · [设计](docs/design.md) · [Agent 接入](docs/agent-integration.md) · [路线图](docs/roadmap.md)

> Knowledge Debt = 代码已经进入你的责任范围，但理解可能尚未同步。
>
> 没有理解证据，不等于不理解；Git 作者身份，也不等于理解。

## 先体验一次

需要 Python 3.10+ 和 Git。当前从源码安装，不依赖已经存在的 PyPI 发布。

```bash
git clone https://github.com/LaJarjan/Knowledge-Debt.git
cd Knowledge-Debt
python -m pip install .
kdebt scan examples
kdebt drill examples/worker.py
```

程序会问：在 `fetch_batch` 中，传给 semaphore 的值是多少？在哪里获取和释放？
这个限制是否覆盖多次独立调用？

先回答，再看源码事实清单，自己勾选原回答覆盖了哪些事实。结果是“本次自查覆盖 2/3 个事实”，
不会显示“你的理解程度从 31% 提升到 57%”。当前命令行问题为英文，Agent 可以翻译。

## 在自己的仓库使用

```bash
kdebt init --scope src          # 可选；不配置则假设负责整个仓库
kdebt scan                     # 最多显示 5 个候选
kdebt scan --since HEAD         # 暂存、未暂存和未跟踪的新代码
kdebt scan --since HEAD~3       # 从一个历史提交比较到当前工作区
kdebt explain src/worker.py     # 查看原因、源码事实和推断边界
kdebt drill src/worker.py       # 一次只问一个问题
```

直接运行 `kdebt` 等同 `kdebt scan`。多个责任目录重复传 `--scope`。
路径都相对于 Git 仓库根目录；在外部使用 `kdebt --repo 仓库路径 scan`。

## 第一版的取舍

**已经实现：**

- Git 工作区读取、指定版本比较、责任范围过滤。
- Python AST 提取三类候选：semaphore 构造、包含异常处理与 sleep 的重试形态循环、finally 中的清理调用。
- 每个事实带行号和源码表达式。
- 单题交接、自查清单、SQLite 本地回答记录。
- 函数语法变化后提醒重新检查，注释和格式化不使记录失效。
- JSON 输出和仓库内 Agent Skill，便于以后接 IDE 插件。

**暂未实现：**

- AI 生成比例检测、自动理解评分、自然语言语义匹配。
- 全量工程概念识别、跨文件调用图、完整语义等价分析。
- 自动定时提醒、IDE 插件、MCP 服务、云端账户和团队评分。

当前版本是可运行的 alpha。AST 只能提供有限的结构事实：看到 `close()` 不意味着一定完成清理；
看到 `Semaphore(32)` 不意味着已经证明并发请求被限制。每类题都会标明边界。

## 指标不装懂

| 状态 | 含义 |
| --- | --- |
| unrecorded | 未记录回答，理解状态未知 |
| answer_recorded | 有回答，未自查事实 |
| self_checked | 当前指纹至少有一个用户自查事实 |
| stale | 最新回答对应的代码指纹已变化 |

HIGH 表示已记录回答过期，或与指定基线相比发生变化且没有当前自查；MEDIUM 是待检查；
LOW 表示当前至少有一条自查事实。部分自查就降低优先级是第一版的简化规则，不能解释为掌握全部逻辑。

`--since` 的统计分母只包含筛选出的变化概念。工具未支持的代码不会计为“已理解”。
文件或函数改名会创建新实例；模块声明变化可能保守地使多个记录过期，跨文件依赖变化暂未追踪。

## 隐私与接入

CLI 零第三方运行时依赖，无 API Key、网络请求和遥测，也不会执行被分析的代码。
扫描不创建状态，初始化或回答后将记录存入 `.kdebt/`，目录自带 Git 忽略规则。
记录没有加密，不要强制加入 Git 或放入公开压缩包。

随仓库提供的 [Skill](skills/knowledge-debt/SKILL.md) 负责对话，CLI 负责分析和存储。
它尚未自动安装。Agent 读取 JSON 后的数据处理遵循其自身规则，JSON 会包含源码表达式。
Agent 不能替用户答题并将自己的解释记成用户理解证据。

## 开发

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
```

最欢迎的反馈：一个真实代码片段，以及“这道题哪里问得好／哪里不准确”。
先让维护者觉得问题值得回答，再扩大概念覆盖范围。
