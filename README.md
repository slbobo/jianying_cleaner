# 剪映缓存清理工具 (Jianying Cleaner)

一个用于扫描和清理剪映（JianYing）桌面版产生的缓存文件和废弃项目的Python小工具，帮助用户释放磁盘空间。

## 主要功能

*   **扫描缓存**：自动扫描剪映默认的缓存目录，包括：
    *   项目草稿 (Drafts)
    *   媒体缓存 (Media Cache Files)
    *   转码缓存 (Proxy Media)
    *   备份文件 (Backup)
    *   用户数据中的部分缓存 (User Data Cache)
    *   我的预设 (User Presets) - 清理时会特别提示
*   **自定义路径扫描**：允许用户指定自定义文件夹进行扫描和清理。
*   **分类显示**：清晰列出扫描到的项目/文件夹名称、大小和类型。
*   **选择性清理**：用户可以选择一个或多个项目进行清理。
*   **安全清理**：默认将选中的文件和文件夹移动到操作系统的回收站，而不是直接永久删除。
*   **磁盘空间检查**：在清理前检查目标磁盘的可用空间，并在空间不足时发出警告。
*   **日志记录**：在界面上显示操作日志，方便追踪。
*   **清理历史**：记录每次清理操作的详细信息（时间、项目、大小、状态）到日志文件 (`%LOCALAPPDATA%\JianyingCleaner\cleanup_history.log`)，并提供查看功能。
*   **用户界面**：基于 Tkinter 和 ttkthemes 构建的图形用户界面，操作直观。
*   **错误处理**：对扫描和清理过程中的常见错误进行捕获和提示。

## 如何运行

### 依赖

*   Python 3.x
*   `ttkthemes`：用于美化 Tkinter 界面。

可以通过 pip 安装依赖：

```bash
_pip install ttkthemes
```

### 运行脚本

直接运行 `jianying_cleaner_gui.py` 文件：

```bash
python jianying_cleaner_gui.py
```

## 如何打包成 EXE (Windows)

可以使用 PyInstaller 将此工具打包成单个可执行的 EXE 文件。

1.  **安装 PyInstaller**：
    ```bash
    pip install pyinstaller
    ```

2.  **打包命令**：
    在项目根目录下打开命令行，运行以下命令：
    ```bash
    pyinstaller --name JianyingCleaner --windowed --onefile --hidden-import=ttkthemes jianying_cleaner_gui.py
    ```
    *   `--name JianyingCleaner`：指定输出的 EXE 文件名为 `JianyingCleaner.exe`。
    *   `--windowed`：指明这是一个窗口程序，运行时不显示命令行控制台。
    *   `--onefile`：将所有内容打包到单个 EXE 文件中。
    *   `--hidden-import=ttkthemes`：确保 `ttkthemes` 库被正确包含。
    *   `jianying_cleaner_gui.py`：主程序脚本。

    如果需要自定义图标，可以添加 `--icon=your_icon.ico` 参数。

3.  **获取 EXE**：
    打包成功后，EXE 文件会生成在项目目录下的 `dist` 文件夹内。

## 文件结构

*   `jianying_cleaner_gui.py`：GUI界面的实现。
*   `jianying_scanner.py`：核心的扫描和清理逻辑。
*   `README.md`：本文档。

## 注意事项

*   清理“我的预设”文件夹时请务必谨慎，这可能导致您在剪映中自定义的模板、效果等丢失。
*   程序会将文件移动到回收站。如果需要永久删除，请清空回收站。
*   建议在执行大规模清理前备份重要数据。

## 作者

壹鑫师兄
