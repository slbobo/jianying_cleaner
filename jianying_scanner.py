import os
import shutil
import send2trash
from typing import Callable, Optional, List, Dict, Any, Tuple
from datetime import datetime # 新增导入

# 日志文件路径配置
USER_DATA_DIR = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'JianyingCleaner')
HISTORY_LOG_FILE = os.path.join(USER_DATA_DIR, 'cleanup_history.log')

# 确保日志目录存在
if not os.path.exists(USER_DATA_DIR):
    try:
        os.makedirs(USER_DATA_DIR)
    except Exception as e:
        print(f"警告：无法创建程序数据目录 {USER_DATA_DIR}: {e}")
        # 如果无法创建目录，可以将日志文件路径回退到程序当前目录
        USER_DATA_DIR = '.' # 当前目录
        HISTORY_LOG_FILE = os.path.join(USER_DATA_DIR, 'cleanup_history.log')

def get_user_local_appdata_path() -> Optional[str]:
    r"""获取当前用户的 AppData\Local 文件夹路径"""
    return os.environ.get('LOCALAPPDATA')

def get_folder_size(folder_path: str) -> int:
    """计算文件夹的总大小"""
    total_size = 0
    if not os.path.exists(folder_path):
        return 0
    for dirpath, dirnames, filenames in os.walk(folder_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if not os.path.islink(fp):
                try:
                    total_size += os.path.getsize(fp)
                except OSError:
                    pass
    return total_size

def format_size(size_bytes: int) -> str:
    """将字节大小格式化为易读的字符串 (KB, MB, GB)"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024**2:
        return f"{size_bytes/1024:.2f} KB"
    elif size_bytes < 1024**3:
        return f"{size_bytes/1024**2:.2f} MB"
    else:
        return f"{size_bytes/1024**3:.2f} GB"

def _log(message: str, callback: Optional[Callable[..., None]] = None, level: str = "INFO") -> None:
    """内部日志函数，如果提供了回调则使用回调，否则打印"""
    if callback:
        # 如果回调函数期望接收 level 参数，则传递它
        # 我们假设 GUI 的 log_message 会处理 level
        try:
            callback(message, level)
        except TypeError:
            # 兼容旧的回调（只接受 message）
            callback(message)
    else:
        print(f"[{level}] {message}")

# 新增函数：记录清理操作到历史文件
def log_cleanup_action(folder_name: str, folder_path: str, original_size_str: str, status: str, details: str = "") -> None:
    """记录单次清理操作到历史日志文件。"""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] 项目: {folder_name} ({folder_path}), 大小: {original_size_str}, 状态: {status}"
        if details:
            log_entry += f", 详情: {details}"
        log_entry += "\n"
        
        with open(HISTORY_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(log_entry)
    except Exception as e:
        # 使用内部日志函数报告记录历史时的错误，避免程序崩溃
        _log(f"严重错误：无法写入清理历史到 {HISTORY_LOG_FILE}: {e}", None, level="CRITICAL")

def scan_jianying_folders(
    log_callback: Optional[Callable[[str, str], None]] = None, 
    progress_callback: Optional[Callable[[float], None]] = None, 
    custom_paths: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """扫描剪映相关的文件夹或自定义路径，通过回调报告日志和进度，返回文件夹信息列表"""
    _log("Initializing scan...", log_callback, level="INFO")
    scanned_folders_info: List[Dict[str, Any]] = []
    total_found_size = 0
    item_number = 1

    paths_to_process = []
    scan_mode = "默认剪映文件夹"

    if custom_paths and isinstance(custom_paths, list) and custom_paths[0]: # 检查列表及其第一个元素
        scan_mode = "自定义路径"
        for path_str in custom_paths:
            if os.path.isdir(path_str): # 确保是目录
                # 对于自定义路径，我们将其视为一个整体进行扫描，而不是其内部的特定子文件夹
                paths_to_process.append({"name": os.path.basename(path_str) or path_str, "path": path_str, "type": "custom"})
            else:
                _log(f"警告：提供的自定义路径 '{path_str}' 不是一个有效的目录，已跳过。", log_callback, level="WARNING")
        if not paths_to_process:
            _log("错误：所有提供的自定义路径均无效。", log_callback, level="ERROR")
            if progress_callback: progress_callback(100)
            return []
    else:
        local_appdata = get_user_local_appdata_path()
        if not local_appdata:
            _log("错误：无法获取 LOCALAPPDATA 环境变量。", log_callback, level="ERROR")
            if progress_callback: progress_callback(100)
            return []
        base_jianying_path = os.path.join(local_appdata, "JianyingPro", "User Data")
        _log(f"扫描基础路径: {base_jianying_path}", log_callback, level="INFO")

        folders_to_scan_definitions = {
            "主要缓存 (Cache)": {"path_suffix": "Cache", "type": "cache"},
            "日志 (Log)": {"path_suffix": "Log", "type": "log"},
            "日志 (VELog)": {"path_suffix": "VELog", "type": "log"},
            "ByteBench": {"path_suffix": "ByteBench", "type": "cache"},
            "一起剪 (CoProduce)": {"path_suffix": "CoProduce", "type": "project"},
            "图文成片 (ArticleVideo)": {"path_suffix": "ArticleVideo", "type": "project"},
            "我的预设 (Presets)": {"path_suffix": "Presets", "type": "preset"}
        }
        for name, def_info in folders_to_scan_definitions.items():
            paths_to_process.append({"name": name, "path": os.path.join(base_jianying_path, def_info["path_suffix"]), "type": def_info["type"]})

    _log(f"开始扫描模式: {scan_mode}", log_callback, level="INFO")
    total_definitions = len(paths_to_process)
    if total_definitions == 0:
        _log("没有有效的路径可供扫描。", log_callback, level="WARNING")
        if progress_callback: progress_callback(100)
        return []

    for i, folder_def in enumerate(paths_to_process):
        path = folder_def["path"]
        name = folder_def["name"]
        folder_type = folder_def["type"]
        
        folder_info = {"id": item_number, "name": name, "path": path, "size_bytes": 0, "size_str": "0 B", "type": folder_type}
        if os.path.exists(path) and os.path.isdir(path): # 确保路径存在且是目录
            _log(f"{item_number}. 正在扫描: {name} ({path})", log_callback, level="INFO")
            size_bytes = get_folder_size(path)
            folder_info["size_bytes"] = size_bytes
            folder_info["size_str"] = format_size(size_bytes)
            total_found_size += size_bytes
            _log(f"   -> 大小: {folder_info['size_str']}", log_callback, level="INFO")
        else:
            _log(f"{item_number}. 未找到或非目录: {name} ({path})", log_callback, level="WARNING")
        scanned_folders_info.append(folder_info)
        item_number += 1
        if progress_callback:
            progress_callback((i + 1) / total_definitions * 100) # 更新进度
    
    _log(f"扫描完成 ({scan_mode})。共发现 {len(scanned_folders_info)} 个项目，总占用空间估算: {format_size(total_found_size)}", log_callback, level="SUCCESS")
    if progress_callback: # 确保扫描完成后进度条满
        progress_callback(100)
    return scanned_folders_info

def clean_selected_folders(
    folders_to_clean: List[Dict[str, Any]], 
    log_callback: Optional[Callable[[str, str], None]] = None, 
    progress_callback: Optional[Callable[[float], None]] = None
) -> Tuple[bool, List[str]]: # Modified return type
    """将选定的文件夹移动到回收站，返回操作是否整体成功及错误消息列表"""
    overall_success = True
    error_messages: List[str] = []

    if not folders_to_clean:
        _log("没有选择任何文件夹进行清理。", log_callback, level="INFO")
        if progress_callback:
            progress_callback(100)
        return True, [] # No errors, successful no-op

    _log("\n开始清理选定的文件夹...", log_callback, level="INFO")
    cleaned_count = 0
    recreated_count = 0
    recreated_subfolder_count = 0 # Initialize here
    total_to_clean = len(folders_to_clean)

    for i, folder_info in enumerate(folders_to_clean):
        path = folder_info["path"]
        name = folder_info["name"]
        original_size_str = folder_info.get("size_str", "未知大小") # 获取原始大小用于记录
        subfolders_to_recreate = []
        current_folder_recreated_subfolder_count = 0 # For logging specific to current folder
        action_status = "未知"
        action_details = ""

        if os.path.exists(path) and os.path.isdir(path):
            try:
                for dirpath, dirnames, filenames in os.walk(path):
                    for dirname in dirnames:
                        full_sub_path = os.path.join(dirpath, dirname)
                        relative_sub_path = os.path.relpath(full_sub_path, path)
                        subfolders_to_recreate.append(relative_sub_path)
            except Exception as e_walk:
                msg = f"警告：在收集 '{name}' 的子文件夹结构时发生错误: {e_walk}"
                _log(msg, log_callback, level="WARNING")
                # This is a warning, not critical for deletion itself
            
            try:
                _log(f"正在将 '{name}' ({path}) 移动到回收站...", log_callback, level="INFO")
                send2trash.send2trash(path)
                _log(f"  -> '{name}' 已成功移动到回收站。", log_callback, level="SUCCESS")
                cleaned_count += 1
                action_status = "成功移动到回收站"
                
                try:
                    os.makedirs(path, exist_ok=True)
                    _log(f"  -> 已在原位置重新创建空文件夹 '{name}'。", log_callback, level="SUCCESS")
                    recreated_count += 1
                    action_status += "并重新创建主文件夹"

                    if subfolders_to_recreate:
                        _log(f"  -> 正在为 '{name}' 重新创建内部子文件夹结构...", log_callback, level="INFO")
                        sub_creation_errors = []
                        for sub_rel_path in subfolders_to_recreate:
                            sub_abs_path = os.path.join(path, sub_rel_path)
                            try:
                                os.makedirs(sub_abs_path, exist_ok=True)
                                current_folder_recreated_subfolder_count +=1
                            except PermissionError as e_perm_sub:
                                err_msg_sub = f"重新创建 '{name}' 的子文件夹 '{sub_rel_path}' 失败: 权限不足"
                                _log(f"    -> 权限错误：重新创建子文件夹 '{sub_abs_path}' 失败。详情: {e_perm_sub}", log_callback, level="ERROR")
                                error_messages.append(err_msg_sub)
                                sub_creation_errors.append(err_msg_sub)
                                overall_success = False
                            except FileNotFoundError as e_fnf_sub: 
                                err_msg_sub = f"重新创建 '{name}' 的子文件夹 '{sub_rel_path}' 失败: 路径问题"
                                _log(f"    -> 文件未找到错误：重新创建子文件夹 '{sub_abs_path}' 失败。详情: {e_fnf_sub}", log_callback, level="ERROR")
                                error_messages.append(err_msg_sub)
                                sub_creation_errors.append(err_msg_sub)
                                overall_success = False
                            except OSError as e_os_sub:
                                err_msg_sub = f"重新创建 '{name}' 的子文件夹 '{sub_rel_path}' 失败: OS 错误"
                                _log(f"    -> OS错误：重新创建子文件夹 '{sub_abs_path}' 失败: {e_os_sub}", log_callback, level="ERROR")
                                error_messages.append(err_msg_sub)
                                sub_creation_errors.append(err_msg_sub)
                                overall_success = False
                            except Exception as e_create_sub:
                                err_msg_sub = f"重新创建 '{name}' 的子文件夹 '{sub_rel_path}' 失败: 未知错误"
                                _log(f"    -> 未知错误：重新创建子文件夹 '{sub_abs_path}' 失败: {e_create_sub}", log_callback, level="WARNING")
                                error_messages.append(err_msg_sub)
                                sub_creation_errors.append(err_msg_sub)
                        recreated_subfolder_count += current_folder_recreated_subfolder_count
                        _log(f"  -> 已为 '{name}' 尝试重新创建 {len(subfolders_to_recreate)} 个子文件夹中的 {current_folder_recreated_subfolder_count} 个。", log_callback, level="INFO")
                        if sub_creation_errors:
                            action_details += f"子文件夹重新创建问题: {'; '.join(sub_creation_errors)}. "

                except PermissionError as e_perm_create:
                    msg = f"权限错误：重新创建空文件夹 '{name}' ({path}) 失败。详情: {e_perm_create}"
                    _log(f"  -> {msg}", log_callback, level="ERROR")
                    error_messages.append(f"重新创建主文件夹 '{name}' 失败: 权限不足")
                    action_status = "移动成功但主文件夹重新创建失败"
                    action_details = msg
                    overall_success = False
                except OSError as e_os_create:
                    msg = f"OS错误：重新创建空文件夹 '{name}' ({path}) 失败: {e_os_create}"
                    _log(f"  -> {msg}", log_callback, level="ERROR")
                    error_messages.append(f"重新创建主文件夹 '{name}' 失败: OS 错误")
                    action_status = "移动成功但主文件夹重新创建失败"
                    action_details = msg
                    overall_success = False
                except Exception as e_create:
                    msg = f"未知错误：重新创建空文件夹 '{name}' 失败: {e_create}"
                    _log(f"  -> {msg}", log_callback, level="WARNING")
                    error_messages.append(f"重新创建主文件夹 '{name}' 失败: 未知错误")
                    action_status = "移动成功但主文件夹重新创建警告"
                    action_details = msg
                    # Not setting overall_success to False for unknown warning on main folder recreation

            except PermissionError as e_perm_send:
                msg = f"权限错误：移动 '{name}' ({path}) 到回收站失败。文件可能被占用或权限不足。详情: {e_perm_send}"
                _log(f"  -> {msg}", log_callback, level="ERROR")
                error_messages.append(f"清理 '{name}' 失败: 权限不足")
                action_status = "失败：权限不足无法移动到回收站"
                action_details = msg
                overall_success = False          
            except FileNotFoundError as e_fnf_send:
                msg = f"文件未找到错误：移动 '{name}' ({path}) 到回收站失败。文件可能已被删除。详情: {e_fnf_send}"
                _log(f"  -> {msg}", log_callback, level="ERROR")
                error_messages.append(f"清理 '{name}' 失败: 文件未找到")
                action_status = "失败：文件未找到无法移动到回收站"
                action_details = msg
                overall_success = False
            except OSError as e_os_send:
                if hasattr(e_os_send, 'winerror') and e_os_send.winerror == 112: # ERROR_DISK_FULL
                    msg = f"磁盘空间不足：移动 '{name}' ({path}) 到回收站失败。详情: {e_os_send}"
                    _log(f"  -> {msg}", log_callback, level="ERROR")
                    error_messages.append(f"清理 '{name}' 失败: 目标回收站磁盘空间不足")
                    action_status = "失败：磁盘空间不足无法移动到回收站"
                else:
                    msg = f"OS错误：移动 '{name}' ({path}) 到回收站失败: {e_os_send}"
                    _log(f"  -> {msg}", log_callback, level="ERROR")
                    error_messages.append(f"清理 '{name}' 失败: OS 错误")
                    action_status = "失败：OS错误无法移动到回收站"
                action_details = msg
                overall_success = False
            except Exception as e_send:
                msg = f"错误：移动 '{name}' 到回收站失败: {e_send}"
                _log(f"  -> {msg}", log_callback, level="ERROR")
                error_messages.append(f"清理 '{name}' 失败: 未知错误 ({type(e_send).__name__})")
                action_status = f"失败：未知错误 ({type(e_send).__name__}) 无法移动到回收站"
                action_details = msg
                overall_success = False
            finally:
                # 无论成功与否，都记录操作（除非是文件不存在的情况，下面会处理）
                if action_status != "未知": # 确保至少尝试了操作
                    log_cleanup_action(name, path, original_size_str, action_status, action_details)

        elif os.path.exists(path) and not os.path.isdir(path):
            # 初始化文件操作的状态和详情变量
            file_action_status = "未知(文件)" # 在此初始化
            file_action_details = ""      # 在此初始化
            try:
                _log(f"正在将文件 '{name}' ({path}) 移动到回收站...", log_callback, level="INFO")
                send2trash.send2trash(path)
                _log(f"  -> 文件 '{name}' 已成功移动到回收站。", log_callback, level="SUCCESS")
                cleaned_count += 1
                file_action_status = "成功移动文件到回收站"
            except PermissionError as e_perm_send_file:
                msg = f"权限错误：移动文件 '{name}' ({path}) 到回收站失败。详情: {e_perm_send_file}"
                _log(f"  -> {msg}", log_callback, level="ERROR")
                error_messages.append(f"清理文件 '{name}' 失败: 权限不足")
                file_action_status = "失败(文件)：权限不足"
                file_action_details = msg
                overall_success = False
            except OSError as e_os_send_file:
                msg = f"OS错误：移动文件 '{name}' ({path}) 到回收站失败: {e_os_send_file}"
                _log(f"  -> {msg}", log_callback, level="ERROR")
                error_messages.append(f"清理文件 '{name}' 失败: OS 错误")
                file_action_status = "失败(文件)：OS错误"
                file_action_details = msg
                overall_success = False
            except Exception as e_send_file:
                msg = f"错误：移动文件 '{name}' 到回收站失败: {e_send_file}"
                _log(f"  -> {msg}", log_callback, level="ERROR")
                error_messages.append(f"清理文件 '{name}' 失败: 未知错误")
                file_action_status = "失败(文件)：未知错误"
                file_action_details = msg
                overall_success = False
            finally:
                # 确保 file_action_status 在这里肯定有值
                log_cleanup_action(name, path, original_size_str, file_action_status, file_action_details)
        else:
            msg = f"跳过：文件夹/文件 '{name}' ({path}) 不存在或已被删除。"
            _log(f"  -> {msg}", log_callback, level="WARNING")
            # 对于不存在的项目，也记录一下，表明已检查但未操作
            log_cleanup_action(name, path, original_size_str, "跳过：不存在或已被删除")
        
        if progress_callback:
            progress_callback((i + 1) / total_to_clean * 100)
    
    if cleaned_count > 0:
        _log(f"\n清理操作尝试完毕。共 {cleaned_count} 个项目尝试移入回收站。", log_callback, level="INFO")
        if recreated_count > 0:
            _log(f"共 {recreated_count} 个主文件夹已在原位置重新创建。", log_callback, level="INFO")
        if recreated_subfolder_count > 0:
            _log(f"共 {recreated_subfolder_count} 个内部子文件夹已在原位置重新创建。", log_callback, level="INFO")
    elif not folders_to_clean:
        pass
    else:
        _log("\n没有文件被实际移动到回收站。", log_callback, level="INFO")

    if progress_callback:
        progress_callback(100)
    
    if not error_messages and cleaned_count == 0 and folders_to_clean:
        if not any("失败" in m for m in error_messages):
             _log("所有选定项目均未找到或大小为0，未执行清理操作。", log_callback, level="INFO")

    if error_messages:
        _log(f"清理过程中遇到 {len(error_messages)} 个问题。请查看详情。", log_callback, level="WARNING")

    return overall_success, error_messages

if __name__ == "__main__":
    # 命令行版本的逻辑保持不变，不使用 log_callback
    scanned_info = scan_jianying_folders()

    if not scanned_info:
        print("未能扫描到任何剪映相关文件夹信息。程序退出。")
    else:
        print("\n--- 可清理项目列表 ---")
        for folder in scanned_info:
            # 对预设文件夹进行特别提示
            warning = " (重要数据，请谨慎清理！)" if folder["type"] == "preset" else ""
            print(f"{folder['id']}. {folder['name']} - {folder['size_str']}{warning}")
        
        print("\n请输入您想要清理的项目编号 (多个编号请用逗号隔开，例如 1,3,5)，或者输入 'all' 清理所有已扫描到的项目，输入 'none' 或直接回车则不清理：")
        user_input = input("> ").strip().lower()

        folders_to_process = []
        if user_input == 'none' or not user_input:
            print("用户选择不进行清理。程序退出。")
        elif user_input == 'all':
            # 排除预设文件夹，除非用户明确选择
            confirm_all_presets = False
            if any(f["type"] == "preset" and f["size_bytes"] > 0 for f in scanned_info):
                preset_items = [f"{f['id']}({f['name']})" for f in scanned_info if f["type"] == "preset" and f["size_bytes"] > 0]
                confirm_preset_str = input(f"警告：选择 'all' 将包括预设文件夹 {', '.join(preset_items)}。这些包含您的自定义设置，删除后无法恢复！\n是否确定要清理这些预设文件夹？(yes/no): ").strip().lower()
                if confirm_preset_str == 'yes':
                    confirm_all_presets = True
                else:
                    print("取消清理预设文件夹。")
            
            for folder in scanned_info:
                if folder["size_bytes"] > 0: # 只处理实际有大小的文件夹
                    if folder["type"] == "preset" and not confirm_all_presets:
                        continue # 跳过未确认的预设
                    folders_to_process.append(folder)
        else:
            try:
                selected_ids = [int(i.strip()) for i in user_input.split(',')]
                for folder_id in selected_ids:
                    found = False
                    for folder in scanned_info:
                        if folder['id'] == folder_id:
                            if folder["size_bytes"] > 0: # 只处理实际有大小的文件夹
                                folders_to_process.append(folder)
                            else:
                                print(f"提示：项目 {folder_id} ({folder['name']}) 大小为0，将跳过。")
                            found = True
                            break
                    if not found:
                        print(f"警告：未找到编号为 {folder_id} 的项目，已忽略。")
            except ValueError:
                print("输入无效。请输入数字编号、'all' 或 'none'。程序退出。")
                folders_to_process = [] # 清空以防部分解析

        if folders_to_process:
            print("\n--- 您已选择清理以下项目 ---")
            total_selected_size = 0
            for folder in folders_to_process:
                warning = " (重要数据！)" if folder["type"] == "preset" else ""
                print(f"- {folder['name']} ({folder['size_str']}){warning}")
                total_selected_size += folder['size_bytes']
            print(f"预计释放空间: {format_size(total_selected_size)}")
            
            confirm = input("\n确认要将以上选定项目移动到回收站吗？(yes/no): ").strip().lower()
            if confirm == 'yes':
                clean_selected_folders(folders_to_process)
            else:
                print("操作已取消。没有文件被清理。")
        elif user_input and user_input != 'none': # 如果用户有输入但列表为空（比如选了空文件夹或无效编号）
             print("没有有效的文件或文件夹被选中进行清理。")

def get_disk_free_space(path: str) -> Optional[int]:
    """获取指定路径所在磁盘的可用空间（字节）"""
    drive_for_log = path # 用于日志记录的驱动器或路径
    try:
        # 获取路径的绝对路径，并提取驱动器号
        abs_path = os.path.abspath(path)
        drive = os.path.splitdrive(abs_path)[0] + os.sep # 例如 'C:\'
        drive_for_log = drive # 如果成功获取驱动器，更新日志中使用的名称
        if not os.path.exists(drive):
             _log(f"警告：无法确定路径 '{path}' 所在的驱动器 '{drive}'。", None, level="WARNING")
             return None
        usage = shutil.disk_usage(drive)
        return usage.free
    except Exception as e:
        _log(f"错误：获取磁盘 '{drive_for_log}' 可用空间失败: {e}", None, level="ERROR")
        return None