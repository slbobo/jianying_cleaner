import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog # 导入 filedialog
import os
import threading # 引入线程模块
from typing import Callable, Optional, List, Dict, Any, Tuple # 新增 Tuple

from ttkthemes import ThemedTk # <--- 新增导入

# 尝试从 jianying_scanner.py 导入函数
try:
    from jianying_scanner import (
        scan_jianying_folders,
        clean_selected_folders,
        format_size, # 确保导入 format_size
        get_disk_free_space # <--- 新增导入
    )
except ImportError as e:
    messagebox.showerror("导入错误", f"无法找到或导入 jianying_scanner.py 中的函数。\n错误: {e}\n请确保 jianying_scanner.py 文件与此程序在同一目录下。")
    exit()

class JianyingCleanerApp:
    def __init__(self, root_window):
        self.root = root_window
        # self.root.title("剪映缓存清理工具") # 已在 main 中通过 ThemedTk 设置
        # self.root.geometry("700x700") # 已在 main 中通过 ThemedTk 设置
        # self.root.set_theme("plastik") # 主题在创建ThemedTk实例时设置，此处无需重复

        # --- 创建菜单栏 ---
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="帮助", menu=help_menu)
        help_menu.add_command(label="关于", command=self.show_about_window)
        # --- 菜单栏结束 ---

        self.scanned_data = []
        self.sort_state = {} # 用于存储每列的排序状态 (True for reverse, False for normal)
        self.custom_scan_path = tk.StringVar()

        # --- 自定义路径框架 --- (新增)
        custom_path_frame = ttk.LabelFrame(self.root, text="自定义扫描路径 (可选)", padding="10")
        custom_path_frame.pack(fill=tk.X, padx=10, pady=(5,0))

        ttk.Label(custom_path_frame, text="路径:").pack(side=tk.LEFT, padx=(0,5))
        self.custom_path_entry = ttk.Entry(custom_path_frame, textvariable=self.custom_scan_path, width=60)
        self.custom_path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,5))
        self.browse_button = ttk.Button(custom_path_frame, text="浏览...", command=self.browse_custom_path)
        self.browse_button.pack(side=tk.LEFT)

        # --- 顶部框架 (扫描按钮、状态标签和进度条) ---
        top_frame = ttk.Frame(self.root, padding="10")
        top_frame.pack(fill=tk.X)

        self.scan_button = ttk.Button(top_frame, text="扫描缓存", command=self.start_scan_thread) # 按钮文字稍作修改
        self.scan_button.pack(side=tk.LEFT, padx=(0, 10))

        self.status_label = ttk.Label(top_frame, text="请点击扫描按钮或指定自定义路径后扫描") # 提示文字修改
        self.status_label.pack(side=tk.LEFT, padx=(0,10))

        # 进度条
        self.progress_bar = ttk.Progressbar(top_frame, orient=tk.HORIZONTAL, length=200, mode='determinate')
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # --- 中间框架 (列表和滚动条) ---
        middle_frame = ttk.Frame(self.root, padding="10")
        middle_frame.pack(fill=tk.BOTH, expand=True)

        # 使用 Treeview 替代 Listbox 以便显示多列数据
        self.tree_columns = ("id", "name", "size", "type")
        self.tree = ttk.Treeview(middle_frame, columns=self.tree_columns, show="headings", selectmode="extended")
        
        column_definitions = {
            "id": {"text": "序号", "width": 50, "anchor": tk.CENTER},
            "name": {"text": "项目名称", "width": 250, "anchor": tk.W},
            "size": {"text": "大小", "width": 100, "anchor": tk.E},
            "type": {"text": "类型", "width": 100, "anchor": tk.W}
        }

        for col_id, col_def in column_definitions.items():
            self.tree.heading(col_id, text=col_def["text"], command=lambda c=col_id: self.sort_treeview_column(c))
            self.tree.column(col_id, width=col_def["width"], anchor=col_def["anchor"])
            self.sort_state[col_id] = False # 初始为升序

        # 滚动条
        tree_scrollbar_y = ttk.Scrollbar(middle_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scrollbar_y.set)
        
        tree_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # --- 底部框架 (清理按钮和日志区域) ---
        bottom_frame = ttk.Frame(self.root, padding="10")
        bottom_frame.pack(fill=tk.X)

        self.clean_button = ttk.Button(bottom_frame, text="清理选中项", command=self.start_clean_thread, state=tk.DISABLED)
        self.clean_button.pack(side=tk.LEFT, padx=(0,10))

        self.select_all_var = tk.BooleanVar()
        self.select_all_button = ttk.Checkbutton(bottom_frame, text="全选/取消", variable=self.select_all_var, command=self.toggle_select_all, state=tk.DISABLED)
        self.select_all_button.pack(side=tk.LEFT, padx=(0,10))

        self.view_history_button = ttk.Button(bottom_frame, text="查看清理历史", command=self.show_history_window)
        self.view_history_button.pack(side=tk.LEFT, padx=(0, 10))

        # 日志区域
        log_frame = ttk.LabelFrame(self.root, text="日志", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0,10))
        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, wrap=tk.WORD, state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # 定义日志级别颜色
        self.log_text.tag_config("INFO", foreground="black")
        self.log_text.tag_config("SUCCESS", foreground="green")
        self.log_text.tag_config("WARNING", foreground="orange")
        self.log_text.tag_config("ERROR", foreground="red", font=("TkDefaultFont", 9, "bold"))
        self.log_text.tag_config("DEBUG", foreground="grey") # 备用

    def log_message(self, message: str, level: str = "INFO") -> None:
        """向日志区域追加消息，并根据级别应用样式"""
        self.log_text.config(state=tk.NORMAL)
        # 为确保每条日志独立一行且正确应用tag，先插入换行符（如果不是第一条）
        # 然后插入消息和tag，最后再插入一个换行符
        current_content = self.log_text.get("1.0", tk.END).strip()
        if current_content: # 如果日志区已有内容
            self.log_text.insert(tk.END, "\n")
        self.log_text.insert(tk.END, message, level.upper())
        self.log_text.see(tk.END) # 滚动到最新日志
        self.log_text.config(state=tk.DISABLED)
        self.root.update_idletasks() # 强制刷新界面显示日志

    def update_progress(self, value: float) -> None:
        """更新进度条的值"""
        self.progress_bar['value'] = value
        self.root.update_idletasks() # 强制刷新界面显示进度

    def set_ui_state(self, is_busy):
        """根据操作是否繁忙来设置UI控件状态"""
        state = tk.DISABLED if is_busy else tk.NORMAL
        self.scan_button.config(state=state)
        self.browse_button.config(state=state) # 控制浏览按钮状态
        self.custom_path_entry.config(state='readonly' if is_busy else tk.NORMAL) # 控制输入框状态

        # 清理按钮和全选按钮只有在扫描后且不繁忙时才启用
        if not is_busy and self.scanned_data:
            self.clean_button.config(state=tk.NORMAL)
            self.select_all_button.config(state=tk.NORMAL)
        else:
            self.clean_button.config(state=tk.DISABLED)
            self.select_all_button.config(state=tk.DISABLED)

    def start_scan_thread(self):
        """启动一个新线程来执行扫描操作，防止GUI冻结"""
        self.set_ui_state(True)
        self.status_label.config(text="正在扫描中...")
        
        custom_path = self.custom_scan_path.get().strip()
        if custom_path:
            self.log_message(f"开始扫描自定义路径: {custom_path} (线程启动)...", level="INFO")
        else:
            self.log_message("开始扫描默认剪映相关文件夹 (线程启动)...", level="INFO")
            
        self.update_progress(0) # 重置进度条
        self.select_all_var.set(False)
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        scan_thread = threading.Thread(target=self.perform_scan_in_thread, args=(custom_path,))
        scan_thread.daemon = True # 确保主程序退出时线程也退出
        scan_thread.start()

    def perform_scan_in_thread(self, custom_path: Optional[str] = None) -> None:
        """实际的扫描逻辑，在单独线程中运行"""
        try:
            # 将 update_progress 作为回调传递
            # 在扫描前重置排序状态，因为数据会刷新
            for col_id in self.tree_columns:
                self.sort_state[col_id] = False
                # 重置列标题文本 (移除排序指示符)
                original_text = self.tree.heading(col_id, "text").replace(" ▲", "").replace(" ▼", "")
                self.tree.heading(col_id, text=original_text)

            self.scanned_data = scan_jianying_folders(log_callback=self.log_message, progress_callback=self.update_progress)
            
            if not self.scanned_data:
                self.log_message("未扫描到任何剪映相关文件夹信息。", level="WARNING")
                # messagebox.showinfo 只能在主线程中调用，如果需要在线程中显示，需要特殊处理
                # self.root.after(0, lambda: messagebox.showinfo("扫描结果", "未扫描到任何剪映相关文件夹信息。"))
            else:
                total_size_bytes = 0
                for item_info in self.scanned_data:
                    self.tree.insert("", tk.END, values=(
                        item_info['id'], 
                        item_info['name'], 
                        item_info['size_str'],
                        item_info['type']
                    ))
                    total_size_bytes += item_info['size_bytes']
                
                # 使用导入的 format_size
                # scan_jianying_folders 内部已经用 SUCCESS 级别记录了总大小
                # self.log_message(f"扫描完成。共发现 {len(self.scanned_data)} 个项目，总大小: {format_size(total_size_bytes)}.", level="SUCCESS")
                pass # 扫描完成的消息由 scan_jianying_folders 内部的 _log 控制

        except Exception as e:
            self.log_message(f"扫描过程中发生错误: {e}", level="ERROR")
            self.update_progress(0) # 出错时重置进度条
            # self.root.after(0, lambda e=e: messagebox.showerror("扫描错误", f"扫描过程中发生错误: {e}"))
        finally:
            self.status_label.config(text="扫描完成。请选择要清理的项目。")
            # self.update_progress(100) # 确保扫描完成后进度条满，已在scan_jianying_folders中处理
            self.set_ui_state(False)

    def browse_custom_path(self):
        """打开文件夹选择对话框让用户选择自定义扫描路径"""
        directory = filedialog.askdirectory()
        if directory: # 如果用户选择了文件夹
            self.custom_scan_path.set(directory)
            self.log_message(f"已选择自定义扫描路径: {directory}", level="INFO")

    def toggle_select_all(self):
        if self.select_all_var.get(): # 如果复选框被选中
            for item_id in self.tree.get_children():
                self.tree.selection_add(item_id)
        else:
            for item_id in self.tree.get_children():
                self.tree.selection_remove(item_id)

    def _parse_size_to_bytes(self, size_str: str) -> float: # 之前建议是 int，但MB/GB会有小数，float更合适
        """将格式化的大小字符串 (如 '1.23 MB') 解析为字节数"""
        size_str = size_str.strip().upper()
        try:
            if "GB" in size_str:
                return float(size_str.replace("GB", "").strip()) * (1024**3)
            elif "MB" in size_str:
                return float(size_str.replace("MB", "").strip()) * (1024**2)
            elif "KB" in size_str:
                return float(size_str.replace("KB", "").strip()) * 1024
            elif "B" in size_str:
                return float(size_str.replace("B", "").strip())
            return 0 # 如果无法解析，则返回0
        except ValueError:
            return 0.0 # 解析失败也返回0

    def sort_treeview_column(self, col: str) -> None:
        """根据点击的列对Treeview中的数据进行排序"""
        if not self.scanned_data: # 如果没有数据，则不执行排序
            return

        # 获取当前列的排序状态 (True for reverse, False for normal)
        reverse_order = not self.sort_state.get(col, False)
        
        # 获取Treeview中的所有项及其值
        # items中的每个元素是 (column_value, item_id)
        items: List[Tuple[Any, str]] = [(self.tree.set(child_item, col), child_item) for child_item in self.tree.get_children('')]

        # 根据列类型进行排序
        if col == "id":
            # x 是一个 Tuple[Any, str]，x[0] 是 id 列的值，应为可转换为 int 的字符串
            items.sort(key=lambda x: int(str(x[0])), reverse=reverse_order)
        elif col == "size":
            # x[0] 是 size 列的字符串表示
            items.sort(key=lambda x: self._parse_size_to_bytes(str(x[0])), reverse=reverse_order)
        else: # name, type (字符串排序)
            # x[0] 是 name 或 type 列的值
            items.sort(key=lambda x: str(x[0]).lower(), reverse=reverse_order)

        # 重新排列Treeview中的项
        for index, (val, child_item) in enumerate(items):
            self.tree.move(child_item, '', index)

        # 更新列标题以显示排序指示符
        for c_id in self.tree_columns:
            current_text = self.tree.heading(c_id, "text").replace(" ▲", "").replace(" ▼", "")
            if c_id == col:
                indicator = " ▼" if reverse_order else " ▲"
                self.tree.heading(c_id, text=current_text + indicator)
            else:
                self.tree.heading(c_id, text=current_text)
        
        # 更新该列的排序状态
        self.sort_state[col] = reverse_order

    def start_clean_thread(self):
        """启动一个新线程来执行清理操作"""
        selected_tree_items = self.tree.selection()
        if not selected_tree_items:
            messagebox.showwarning("未选择", "请至少选择一个项目进行清理。")
            return

        folders_to_process_gui = []
        warn_preset = False
        total_size_to_clean_bytes = 0 # 用于累计待清理的总大小

        for tree_item_id in selected_tree_items:
            item_values = self.tree.item(tree_item_id, 'values')
            item_id_in_data = int(item_values[0])
            original_item_info = next((item for item in self.scanned_data if item['id'] == item_id_in_data), None)
            if original_item_info:
                folders_to_process_gui.append(original_item_info)
                total_size_to_clean_bytes += original_item_info.get('size_bytes', 0) # 累加大小
                if original_item_info['type'] == 'preset':
                    warn_preset = True
            else:
                self.log_message(f"警告: 无法在扫描数据中找到选中的项目ID {item_id_in_data}，已跳过。", level="WARNING")

        if not folders_to_process_gui:
            messagebox.showwarning("无有效项目", "没有有效的项目可供清理。")
            return

        # --- 磁盘空间检查 --- 
        if folders_to_process_gui:
            # 假设所有待清理项都在同一个驱动器，取第一个项目的路径来检查磁盘空间
            # 对于更复杂的情况（跨驱动器），可能需要分别检查或选择一个代表性的路径
            representative_path = folders_to_process_gui[0]['path']
            free_space_bytes = get_disk_free_space(representative_path)

            if free_space_bytes is not None:
                self.log_message(f"待清理总大小: {format_size(total_size_to_clean_bytes)}, "
                                 f"目标磁盘 '{os.path.splitdrive(representative_path)[0]}' 可用空间: {format_size(free_space_bytes)}", level="INFO")
                # 定义一个阈值，例如，如果可用空间小于待清理大小的1.5倍，或者小于某个固定值（如1GB）
                # 这里简单处理：如果可用空间小于待清理大小，就警告
                if free_space_bytes < total_size_to_clean_bytes:
                    if not messagebox.askyesno("磁盘空间警告", 
                                                f"警告：目标磁盘可用空间 ({format_size(free_space_bytes)}) 可能不足以容纳待清理的项目到回收站 ({format_size(total_size_to_clean_bytes)})。\n这可能导致清理失败或磁盘写满。\n\n是否仍要继续清理？"):
                        self.log_message("用户取消了清理操作（因磁盘空间警告）。", level="INFO")
                        return # 用户选择不继续
                # 可以添加更复杂的阈值判断，例如：
                # elif free_space_bytes < total_size_to_clean_bytes * 1.5 or free_space_bytes < 1024**3: # 小于1.5倍或小于1GB
                #     messagebox.showwarning("磁盘空间提示", f"目标磁盘可用空间 ({format_size(free_space_bytes)}) 相对较少，请留意。")
            else:
                self.log_message("警告：无法获取磁盘可用空间信息，将跳过空间检查。", level="WARNING")
        # --- 磁盘空间检查结束 ---

        if warn_preset:
            if not messagebox.askyesno("清理预设警告", "您选择的项目中包含 '我的预设'。清理预设可能会导致您在剪映中自定义的模板、效果等丢失。确定要继续吗？"):
                self.log_message("用户取消了清理操作（因预设警告）。", level="INFO")
                return

        confirmation_message = f"确定要将选中的 {len(folders_to_process_gui)} 个项目（总大小约 {format_size(total_size_to_clean_bytes)}）移动到回收站吗？"
        if not messagebox.askyesno("确认清理", confirmation_message):
            self.log_message("用户取消了清理操作。", level="INFO")
            return

        self.set_ui_state(True)
        self.status_label.config(text="正在清理中...")
        # ... 启动清理线程
        self.log_message("启动清理线程...", level="INFO")
        self.set_ui_state(True) # 设置UI为繁忙状态
        self.update_progress(0) # 重置进度条
        
        # 确保这里的 target 指向的是我们修改后的方法名
        clean_thread = threading.Thread(target=self.clean_thread_target, args=(folders_to_process_gui,))
        clean_thread.daemon = True
        clean_thread.start()

    def clean_thread_target(self, folders_to_clean_param: List[Dict[str, Any]]) -> None:
        """实际的清理逻辑，在单独线程中运行"""
        try:
            # 调用修改后的 clean_selected_folders，它现在返回一个元组
            overall_success, error_messages = clean_selected_folders(
                folders_to_clean_param, 
                log_callback=self.log_message, 
                progress_callback=self.update_progress
            )

            if overall_success:
                self.log_message("所有选定项目已成功处理（或按预期跳过）。", level="SUCCESS")
                # 使用 self.root.after 在主线程中显示成功消息
                self.root.after(0, lambda: messagebox.showinfo("清理完成", "选定的项目已成功清理完毕。"))
            else:
                self.log_message("清理过程中遇到一些问题。请查看日志和弹窗获取详细信息。", level="WARNING")
                # 构造错误消息详情
                error_summary = "清理操作未完全成功。遇到的问题如下：\n\n" + "\n".join(f"- {msg}" for msg in error_messages)
                # 使用 self.root.after 在主线程中显示错误消息
                self.root.after(0, lambda es=error_summary: messagebox.showerror("清理错误", es))
            
            # 清理完成后，重新扫描以更新列表状态
            self.log_message("清理操作后自动重新扫描...", level="INFO")
            # self.perform_scan_in_thread() # 直接调用，因为它内部会处理UI更新和线程安全
            # 更改为启动新的扫描线程，以保持UI一致性
            # 注意：这里直接调用 perform_scan_in_thread 是在当前（清理）线程中执行的
            # 如果 perform_scan_in_thread 内部没有正确处理好跨线程UI更新，可能会有问题
            # 更安全的做法是让主线程在清理线程结束后再触发一次扫描按钮的逻辑
            # 但考虑到 perform_scan_in_thread 已经设计为在线程中运行并回调UI，这里暂时保留
            # 为了确保UI状态正确更新，我们应该在主线程中触发扫描
            self.root.after(0, self.start_scan_thread) # 请求主线程启动扫描

        except Exception as e:
            self.log_message(f"清理过程中发生意外错误: {e}", level="ERROR")
            self.update_progress(0) # 出错时重置进度条
            self.root.after(0, lambda e=e: messagebox.showerror("清理严重错误", f"清理过程中发生意外错误: {e}"))
        finally:
            # 确保UI状态在清理线程结束后（无论成功与否）都得到更新
            # 注意：由于上面的自动重新扫描也是异步的，这里的 set_ui_state(False) 可能会过早执行
            # 扫描完成后，perform_scan_in_thread 的 finally 块会调用 set_ui_state(False)
            # 所以这里的调用可以移除，避免冲突或不必要的重复
            # self.set_ui_state(False) 
            pass # UI状态将由后续的扫描操作的 finally 块来管理
            self.update_progress(100) # 确保清理完成后进度条满，已在clean_selected_folders中处理
            self.log_message("清理线程执行完毕。", level="INFO")

    def show_about_window(self) -> None:  # <--- 将方法移到这里，作为类的一部分
        """显示关于窗口"""
        about_window = tk.Toplevel(self.root)
        about_window.title("关于 剪映缓存清理工具")
        about_window.geometry("350x200")
        about_window.resizable(False, False)

        # 让关于窗口显示在主窗口中心
        root_x = self.root.winfo_x()
        root_y = self.root.winfo_y()
        root_width = self.root.winfo_width()
        root_height = self.root.winfo_height()

        pos_x = root_x + (root_width // 2) - (350 // 2)
        pos_y = root_y + (root_height // 2) - (200 // 2)
        about_window.geometry(f"+{(pos_x)}+{(pos_y)}")

        main_frame = ttk.Frame(about_window, padding="10")
        main_frame.pack(expand=True, fill=tk.BOTH)

        ttk.Label(main_frame, text="剪映缓存清理工具", font=("TkDefaultFont", 14, "bold")).pack(pady=(0,10))
        ttk.Label(main_frame, text="版本: 1.1.0").pack()
        ttk.Label(main_frame, text="作者: 壹鑫师兄").pack() # 请替换为您的名字
        ttk.Label(main_frame, text="一个用于清理剪映桌面版缓存文件的小工具。").pack(pady=(10,0))

        close_button = ttk.Button(main_frame, text="关闭", command=about_window.destroy)
        close_button.pack(pady=(15,0))

        # 使关于窗口成为模态窗口 (可选，如果希望用户必须先关闭它)
        about_window.transient(self.root) # 依赖于主窗口
        about_window.grab_set() # 捕获所有事件
        self.root.wait_window(about_window) # 等待关于窗口关闭

    def show_history_window(self):
        """弹窗显示清理历史日志内容"""
        import os
        import tkinter.scrolledtext as scrolledtext
        # 确保从 jianying_scanner 导入 HISTORY_LOG_FILE
        try:
            from jianying_scanner import HISTORY_LOG_FILE
        except ImportError:
            self.log_message("无法导入 HISTORY_LOG_FILE 变量。", level="ERROR")
            messagebox.showerror("错误", "无法找到历史记录文件路径配置。")
            return

        history_window = tk.Toplevel(self.root)
        history_window.title("清理历史记录")
        history_window.geometry("700x400")
        history_window.resizable(True, True)
        # 居中显示
        root_x = self.root.winfo_x()
        root_y = self.root.winfo_y()
        root_width = self.root.winfo_width()
        root_height = self.root.winfo_height()
        pos_x = root_x + (root_width // 2) - (700 // 2)
        pos_y = root_y + (root_height // 2) - (400 // 2)
        history_window.geometry(f"+{(pos_x)}+{(pos_y)}")
        # 滚动文本框
        text_area = scrolledtext.ScrolledText(history_window, wrap=tk.WORD, font=("Consolas", 10))
        text_area.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)
        # 读取日志内容
        log_path = HISTORY_LOG_FILE # 使用导入的变量
        if os.path.exists(log_path):
            try:
                with open(log_path, "r", encoding="utf-8") as f:
                    text_area.insert(tk.END, f.read())
            except Exception as e:
                text_area.insert(tk.END, f"读取历史记录文件失败: {e}")
                self.log_message(f"读取历史记录文件失败: {e}", level="ERROR")
        else:
            text_area.insert(tk.END, "暂无清理历史记录。")
        text_area.config(state=tk.DISABLED)
        ttk.Button(history_window, text="关闭", command=history_window.destroy).pack(pady=5)

        history_window.transient(self.root)
        history_window.grab_set()
        self.root.wait_window(history_window)

if __name__ == "__main__":
    # root = tk.Tk() # <--- 注释掉或删除这行
    root = ThemedTk(theme="plastik")  # <--- 修改这里，创建 ThemedTk 实例并预设主题
    root.title("剪映缓存清理工具") # 设置标题
    root.geometry("700x700")   # 设置窗口大小

    app = JianyingCleanerApp(root)
    root.mainloop()