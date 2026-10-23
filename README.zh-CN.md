# git-portable-paths 中文说明

在检出代码前发现 Windows 非法文件名、目录大小写冲突、Unicode 规范化冲突
和路径长度预算问题。直接读取 Git 索引或提交树，支持裸仓库；不读取文件内容、
不跟随符号链接、不执行检出或重命名。需要 Python 3.11+、Git 2.31+。

```sh
git clone https://github.com/KanadeK/git-portable-paths.git
cd git-portable-paths
python -m venv .venv
```

Windows 无需激活环境即可执行：

```powershell
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\python.exe -m git_portable_paths . --ref HEAD --format json
.\.venv\Scripts\python.exe examples/demo.py
```

Linux/macOS 改用 `.venv/bin/python`。自身仓库检查应退出 0；演示故意生成 3 个
问题并退出 1。演示仅在临时裸仓库里写 Git 对象，不会创建 Windows 非法文件。

默认扫描索引，`--ref main` 扫描指定提交树（裸仓库必须指定）。支持机器可读
JSON 和 `--format github` CI 注解。检查路径的所有父目录，识别文件与目录冲突。
`--root-units 60 --max-path-units 240` 设定含检出根目录前缀的 UTF-16 长度预算。
默认根目录预算为 0，不会推测你的机器路径。`--max-issues` 只限制报告明细。

比较规则为 NFC、Unicode casefold 和去尾空格/点，属于保守策略，可能对某些
实际文件系统产生额外提示，不能保证所有文件系统兼容。不扫描未跟踪文件、
子模块内容或符号链接目标。详细边界见英文 [README](README.md)。

退出码：0 无问题，1 有问题，2 参数或 Git 故障。测试：
`python -m unittest discover -s tests -v`。卸载：
`python -m pip uninstall git-portable-paths`；无持久缓存。许可证 MIT。
