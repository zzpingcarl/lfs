# lfs.py
import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import List, Dict, Set

def load_env_config():
    """
    加载lfs.ini配置文件
    返回包含配置项的字典
    """
    env_config = {}
    env_file = Path('lfs.ini')
    if env_file.exists():
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        env_config[key.strip()] = value.strip().strip('"')
    return env_config

def should_save_config(env_exists: bool, args, env_config: dict) -> bool:
    """
    判断是否需要保存配置到lfs.ini文件
    当文件不存在或参数与配置不一致时返回True
    """
    # 如果lfs.ini文件不存在，则需要保存
    if not env_exists:
        return True
    
    # 检查参数是否与lfs.ini中的配置不一致
    config_changed = (
        args.lfs_base != env_config.get('LFS-BASE', './lfs_base/') or
        args.usr_base != env_config.get('USR-BASE', './') or
        args.min_size != env_config.get('LFS-SIZE', '10MB')
    )
    
    return config_changed

def save_env_config(config):
    """
    保存配置到lfs.ini文件
    """
    env_file = Path('lfs.ini')
    with open(env_file, 'w', encoding='utf-8') as f:
        for key, value in config.items():
            f.write(f'{key}="{value}"\n')

class LFSManager:
    def __init__(self, lfs_base: str):
        """
        初始化LFS管理器
        lfs_base: LFS仓库基础目录
        """
        self.lfs_base = Path(lfs_base).resolve()
        self.objects_path = self.lfs_base / "objects"
        self.manifest_file = self.lfs_base / "lfs_assets.json"
        
        # 文件大小分类规则
        self.size_categories = [
            (1*1024*1024, 10*1024*1024, "1M-10M"),           # 1M-10M
            (10*1024*1024, 100*1024*1024, "10M-100M"),       # 10M-100M
            (100*1024*1024, 500*1024*1024, "100M-500M"),     # 100M-500M
            (500*1024*1024, 1024*1024*1024, "500M-1G"),      # 500M-1G
            (1024*1024*1024, 5*1024*1024*1024, "1G-5G"),     # 1G-5G
            (5*1024*1024*1024, float('inf'), "5G-above")     # 5G以上
        ]
        
        # 在Windows上启用长路径支持
        if os.name == 'nt':
            self._enable_win_long_paths()
        
    def _enable_win_long_paths(self):
        """
        在Windows上启用长路径支持
        解决Windows系统路径长度限制问题
        """
        try:
            import ctypes
            from ctypes import wintypes
            
            # 设置SetErrorMode忽略关键错误
            SEM_NOGPFAULTERRORBOX = 0x0002
            ctypes.windll.kernel32.SetErrorMode(SEM_NOGPFAULTERRORBOX)
            
            # 启用长路径支持
            try:
                ctypes.windll.kernel32.SetDllDirectoryW(None)
            except Exception:
                pass
        except Exception:
            pass
    
    def _load_manifest(self) -> Dict:
        """
        加载清单文件
        返回包含文件信息的字典
        """
        if self.manifest_file.exists():
            try:
                with open(self.manifest_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"加载清单文件失败: {e}")
                return {}
        return {}
    
    def _save_manifest(self, manifest: Dict):
        """
        保存清单文件
        manifest: 包含文件信息的字典
        """
        try:
            # 确保目录存在
            self.lfs_base.mkdir(parents=True, exist_ok=True)
            with open(self.manifest_file, 'w', encoding='utf-8') as f:
                json.dump(manifest, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存清单文件失败: {e}")
    
    def _get_file_hash(self, file_path: Path) -> str:
        """
        计算文件SHA-256哈希值
        file_path: 文件路径
        返回文件的哈希值
        """
        hash_sha256 = hashlib.sha256()
        try:
            # 先尝试直接打开
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except (FileNotFoundError, OSError):
            # 如果失败，尝试使用Windows API
            if os.name == 'nt':
                try:
                    long_path = self._get_win_long_path(str(file_path))
                    with open(long_path, "rb") as f:
                        for chunk in iter(lambda: f.read(4096), b""):
                            hash_sha256.update(chunk)
                    return hash_sha256.hexdigest()
                except Exception:
                    pass
            # 最后尝试使用 \\?\ 前缀
            try:
                abs_path = os.path.abspath(str(file_path))
                if len(abs_path) >= 260:  # Windows MAX_PATH 限制
                    long_path = "\\\\?\\" + abs_path
                    with open(long_path, "rb") as f:
                        for chunk in iter(lambda: f.read(4096), b""):
                            hash_sha256.update(chunk)
                    return hash_sha256.hexdigest()
                else:
                    with open(file_path, "rb") as f:
                        for chunk in iter(lambda: f.read(4096), b""):
                            hash_sha256.update(chunk)
                    return hash_sha256.hexdigest()
            except Exception:
                raise
    
    def _get_win_long_path(self, path: str) -> str:
        """
        获取Windows长路径
        path: 原始路径
        返回处理后的长路径
        """
        path = os.path.abspath(path)
        # 只有在必要时才添加长路径前缀
        if len(path) >= 260 and not path.startswith('\\\\?\\'):
            return '\\\\?\\' + path
        return path
    
    def _safe_copy(self, src: Path, dst: Path):
        """
        安全复制文件，处理各种路径问题
        src: 源文件路径
        dst: 目标文件路径
        """
        # 确保目标目录存在
        dst.parent.mkdir(parents=True, exist_ok=True)
        
        copy_methods = [
            lambda: shutil.copy2(src, dst),  # 标准方法
            lambda: shutil.copy2(self._get_win_long_path(str(src)), dst),  # 长路径源
            lambda: shutil.copy2(src, self._get_win_long_path(str(dst))),  # 长路径目标
            lambda: shutil.copy2(self._get_win_long_path(str(src)), self._get_win_long_path(str(dst))),  # 双长路径
        ]
        
        for i, method in enumerate(copy_methods):
            try:
                method()
                return
            except Exception as e:
                if i == len(copy_methods) - 1:  # 最后一种方法也失败了
                    raise e
                continue
    
    def _safe_unlink(self, file_path: Path):
        """
        安全删除文件
        file_path: 要删除的文件路径
        """
        try:
            # Windows系统使用del命令
            if os.name == 'nt':
                import subprocess
                file_path_str = str(file_path.resolve())
                
                # 只有在路径很长时才使用长路径前缀
                if len(file_path_str) >= 260 and not file_path_str.startswith('\\\\?\\'):
                    file_long = '\\\\?\\' + os.path.abspath(file_path_str)
                else:
                    file_long = file_path_str
                
                # 尝试多种del方式
                commands = [
                    ['cmd', '/c', 'del', '/F', '/Q', '"' + file_long + '"'],
                    ['cmd', '/c', 'del', '/F', '/Q', '"' + file_path_str + '"'],
                    ['del', '/F', '/Q', '"' + file_path_str + '"']
                ]
                
                success = False
                for cmd in commands:
                    try:
                        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                        if result.returncode == 0:
                            success = True
                            break
                        else:
                            if os.getenv('LFS_DEBUG'):
                                print(f"del命令失败 ({cmd}): {result.stderr}")
                    except subprocess.TimeoutExpired:
                        if os.getenv('LFS_DEBUG'):
                            print(f"del命令超时 ({cmd})")
                    except Exception as e:
                        if os.getenv('LFS_DEBUG'):
                            print(f"del命令出错 ({cmd}): {e}")
                
                if not success:
                    # 回退到Python标准方法
                    try:
                        file_path.unlink()
                    except Exception:
                        raise Exception("所有删除方法都失败了")
            else:
                # Unix-like系统使用标准方法
                file_path.unlink()
        except Exception as e:
            print(f"删除文件失败 {file_path}: {e}")
            raise
        if file_path.exists():
            print(f"删除文件失败 {file_path}")
    
    def _create_relative_symlink(self, src: Path, dst: Path) -> bool:
        """
        创建相对路径软链接
        src: 源文件路径
        dst: 目标文件路径
        返回是否成功创建链接
        """
        try:
            # 先删除目标文件（如果存在）
            if dst.exists():
                self._safe_unlink(dst)
            
            # 计算相对路径
            try:
                src_abs = src.resolve()
                # 计算相对于目标文件父目录的相对路径
                relative_path = os.path.relpath(str(src_abs), str(dst.parent.resolve()))
            except ValueError as e:
                # 当两个路径不在同一驱动器上时，relpath会抛出ValueError
                if os.getenv('LFS_DEBUG'):
                    print(f"无法计算相对路径 ({dst} -> {src}): {e}")
                return False
            
            # 创建相对路径软链接
            if os.name == 'nt':
                import subprocess
                # Windows使用mklink命令创建相对路径软链接
                cmd = ['cmd', '/c', 'mklink', str(dst), relative_path]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                if result.returncode != 0:
                    if os.getenv('LFS_DEBUG'):
                        print(f"mklink失败: {result.stderr}")
                    return False
            else:
                # Unix系统使用os.symlink
                dst.parent.mkdir(parents=True, exist_ok=True)
                os.symlink(relative_path, str(dst))
            
            return True
        except Exception as e:
            # 只在调试模式下打印详细错误信息
            if os.getenv('LFS_DEBUG'):
                print(f"创建相对路径软链接失败 {dst}: {e}")
            return False
    
    def _safe_link(self, src: Path, dst: Path):
        """
        安全创建链接，只使用相对路径软链接
        src: 源文件路径
        dst: 目标文件路径
        """
        # 确保目标目录存在
        dst.parent.mkdir(parents=True, exist_ok=True)
        
        # 只尝试相对路径软链接
        if self._create_relative_symlink(src, dst):
            return
        else:
            # 如果相对路径软链接失败，回退到复制文件
            print(f"创建软链接失败，回退到复制文件: {dst}")
            try:
                # 先删除目标文件（如果存在）
                if dst.exists():
                    self._safe_unlink(dst)
                self._safe_copy(src, dst)
                print(f"已复制文件代替链接: {dst}")
            except Exception as copy_err:
                print(f"复制文件失败 {dst}: {copy_err}")
                raise
    
    def _get_size_category(self, size: int) -> str:
        """
        根据文件大小确定分类目录
        size: 文件大小（字节）
        返回对应的分类名称
        """
        for min_size, max_size, category in self.size_categories:
            if min_size <= size < max_size:
                return category
        return "5G-above"  # 默认最大类别
    
    def init_repo(self):
        """
        初始化LFS仓库
        """
        self.lfs_base.mkdir(parents=True, exist_ok=True)
        self.objects_path.mkdir(exist_ok=True)
        
        # 创建各个大小分类目录
        for _, _, category in self.size_categories:
            (self.objects_path / category).mkdir(exist_ok=True)
        
        # 初始化清单文件
        if not self.manifest_file.exists():
            self._save_manifest({})
        
        print(f"LFS仓库已初始化: {self.lfs_base}")
    
    def scan_large_files(self, directory: str, min_size: int) -> List[Path]:
        """
        扫描指定目录中的大文件，跳过包含lfs_assets.json的目录
        directory: 要扫描的目录
        min_size: 最小文件大小阈值
        返回大文件路径列表
        """
        large_files = []
        dir_path = Path(directory)
        
        if not dir_path.exists():
            raise FileNotFoundError(f"目录不存在: {dir_path.resolve()}")
        
        print(f"开始扫描目录...")
        scanned_count = 0
        large_count = 0
        
        try:
            for file_path in dir_path.rglob('*'):
                scanned_count += 1
                # 每扫描1000个文件更新一次进度
                if scanned_count % 1000 == 0:
                    print(f"\r已扫描 {scanned_count} 个文件，找到 {large_count} 个大文件", end='', flush=True)
                
                try:
                    # 检查是否应该跳过该文件
                    should_skip = False
                    
                    # 检查当前文件是否在包含lfs_assets.json的目录中
                    for parent in file_path.parents:
                        if (parent / "lfs_assets.json").exists():
                            should_skip = True
                            break
                    
                    if should_skip:
                        continue
                    
                    if file_path.is_file():
                        # 检查文件是否为软链接，如果是软链接则跳过
                        try:
                            if file_path.is_symlink():
                                should_skip = True
                                continue
                        except OSError:
                            # 权限不足等情况，继续处理
                            pass
                        
                        file_size = file_path.stat().st_size
                        if file_size >= min_size:
                            # 检查文件是否为软链接
                            if os.name == 'nt':
                                # Windows系统检查是否为符号链接
                                try:
                                    import subprocess
                                    result = subprocess.run(['cmd', '/c', 'dir', str(file_path.parent)], 
                                                        capture_output=True, text=True, timeout=10)
                                    if '<SYMLINK>' in result.stdout or '<JUNCTION>' in result.stdout:
                                        continue
                                except Exception:
                                    pass
                            else:
                                # Unix系统使用is_symlink()
                                if file_path.is_symlink():
                                    continue
                            # 跳过软链接
                            large_files.append(file_path)
                            large_count += 1
                            
                except (OSError, PermissionError) as e:
                    if os.getenv('LFS_DEBUG'):
                        print(f"\n跳过无法访问的文件 {file_path}: {e}")
                    continue
                except Exception as e:
                    if os.getenv('LFS_DEBUG'):
                        print(f"\n检查文件时出错 {file_path}: {e}")
                    continue
        except Exception as e:
            print(f"\n扫描目录时出错 {dir_path}: {e}")
        
        print(f"\r扫描完成，共扫描 {scanned_count} 个文件，找到 {large_count} 个大文件")
        return large_files
    
    
    def store_and_link_file(self, file_path: Path, manifest: Dict, no_confirm: bool = False):
        """
        存储并链接单个文件
        file_path: 文件路径
        manifest: 清单字典
        no_confirm: 是否跳过确认
        返回是否处理成功
        """
        try:
            # 生成文件标识符
            file_hash = self._get_file_hash(file_path)
            file_size = file_path.stat().st_size
            
            # 确定存储分类
            category = self._get_size_category(file_size)
            storage_dir = self.objects_path / category
            storage_path = storage_dir / file_hash
            
            file_key = f"sha256:{file_hash}"
            
            # 判断是新文件还是已有文件
            is_new_file = not storage_path.exists()
            
            # 如果文件尚未存储，则复制到仓库
            if is_new_file:
                print(f"        存储并链接到 {storage_path.relative_to(self.lfs_base)}")
                self._safe_copy(file_path, storage_path)
            else:
                print(f"        链接到 {storage_path.relative_to(self.lfs_base)}")
            
            # 更新清单
            if file_key not in manifest:
                manifest[file_key] = {
                    "hash": file_hash,
                    "size": file_size,
                    "storage_path": str(storage_path.relative_to(self.lfs_base)),
                    "source_paths": [str(file_path)],  # 只有初次存储才添加源路径
                    "link_paths": []
                }
            else:
                # 文件已存在，只更新链接路径，不更新源路径
                pass
            
            # 创建链接
            self._safe_link(storage_path, file_path)
            
            # 更新清单中的链接路径（避免重复）
            link_str = str(file_path)
            if link_str not in manifest[file_key]["link_paths"]:
                manifest[file_key]["link_paths"].append(link_str)
            
            return True
        except Exception as e:
            print(f"处理文件 {file_path} 时出错: {e}")
            return False
    
    def process_files(self, usr_base: str, min_size_bytes: int, no_confirm: bool = False):
        """
        处理用户目录中的文件
        usr_base: 用户基础目录
        min_size_bytes: 最小文件大小（字节）
        no_confirm: 是否跳过确认
        """
        usr_base_path = Path(usr_base).resolve()
        lfs_base_path = self.lfs_base.resolve()
        
        print(f"LFS目录: {lfs_base_path}")
        print(f"用户目录: {usr_base_path}")
        
        # 扫描大文件
        large_files = self.scan_large_files(usr_base, min_size_bytes)
        
        if not large_files:
            return
        
        print(f"开始处理 {len(large_files)} 个大文件...")
        
        manifest = self._load_manifest()
        processed_count = 0
        
        for i, file_path in enumerate(large_files, 1):
            try:
                # 显示处理进度和文件相对路径
                relative_path = os.path.relpath(str(file_path), str(usr_base_path))
                print(f"处理[{i}/{len(large_files)}]: {relative_path}")
                
                if self.store_and_link_file(file_path, manifest, no_confirm):
                    processed_count += 1
            except Exception as e:
                print(f"处理文件 {file_path} 时出错: {e}")
                continue  # 继续处理其他文件
        
        # 保存清单
        self._save_manifest(manifest)
        print(f"处理完成 {processed_count}/{len(large_files)} 个大文件")
    
    def clean_repo(self, no_confirm: bool = False):
        """
        清理LFS仓库
        no_confirm: 是否跳过确认
        """
        manifest = self._load_manifest()
        deleted_count = 0
        cleaned_entries = []
        
        # 检查每个清单项
        keys_to_remove = []
        for file_key, entry in manifest.items():
            storage_path = self.lfs_base / entry["storage_path"]
            
            # 检查链接地址清单中的文件是否存在
            valid_links = []
            for link_path_str in entry.get("link_paths", []):
                link_path = Path(link_path_str)
                try:
                    if link_path.exists():
                        valid_links.append(link_path_str)
                    else:
                        print(f"链接文件不存在: {link_path_str}")
                except Exception as e:
                    print(f"检查链接文件时出错 {link_path_str}: {e}")
            
            # 更新有效的链接列表
            entry["link_paths"] = valid_links
            
            # 如果没有有效的链接，则标记为待清理
            if not valid_links:
                cleaned_entries.append({
                    "file_key": file_key,
                    "storage_path": str(storage_path),
                    "source_paths": entry.get("source_paths", [])
                })
        
        # 询问是否删除没有链接的文件
        if cleaned_entries:
            print(f"\n发现 {len(cleaned_entries)} 个没有链接的文件:")
            for item in cleaned_entries:
                print(f"  - {item['storage_path']}")
            
            confirm = no_confirm
            if not confirm:
                response = input("\n是否删除这些文件? (y/N): ")
                confirm = response.lower() in ['y', 'yes']
            
            if confirm:
                for item in cleaned_entries:
                    try:
                        storage_path = Path(item['storage_path'])
                        if storage_path.exists():
                            self._safe_unlink(storage_path)
                            print(f"已删除: {storage_path}")
                            deleted_count += 1
                        # 从清单中移除
                        if item['file_key'] in manifest:
                            keys_to_remove.append(item['file_key'])
                    except Exception as e:
                        print(f"删除文件失败 {item['storage_path']}: {e}")
        
        # 移除清单中的条目
        for key in keys_to_remove:
            del manifest[key]
        
        # 保存更新后的清单
        self._save_manifest(manifest)
        print(f"清理完成，共删除 {deleted_count} 个文件")

def parse_size(size_str: str) -> int:
    """
    解析大小字符串，如 '10M', '100MB', '1G' 等
    size_str: 大小字符串
    返回字节数
    """
    size_str = size_str.upper().strip()
    
    # 定义单位映射
    units = {
        'B': 1,
        'K': 1024,
        'KB': 1024,
        'M': 1024*1024,
        'MB': 1024*1024,
        'G': 1024*1024*1024,
        'GB': 1024*1024*1024,
        'T': 1024*1024*1024*1024,
        'TB': 1024*1024*1024*1024
    }
    
    # 提取数字和单位
    num_part = ""
    unit_part = ""
    
    for i, char in enumerate(size_str):
        if char.isdigit() or char == '.':
            num_part += char
        else:
            unit_part = size_str[i:]
            break
    
    try:
        number = float(num_part)
        unit = unit_part if unit_part else 'MB'  # 默认单位为MB
        
        if unit in units:
            return int(number * units[unit])
        else:
            # 如果没有识别出单位，假设是MB
            return int(number * 1024 * 1024)
    except Exception:
        # 默认返回10MB
        return 10 * 1024 * 1024

def main():
    # 加载环境配置
    env_config = load_env_config()
    
    # 设置默认值
    default_lfs_base = env_config.get('LFS-BASE', './lfs_base/')
    default_usr_base = env_config.get('USR-BASE', './')
    default_size = env_config.get('LFS-SIZE', '10MB')
    
    parser = argparse.ArgumentParser(description="大文件管理软件(LFS)")
    parser.add_argument('-lbase', '--lfs-base', default=default_lfs_base, help=f'LFS仓库基础目录 (默认: {default_lfs_base})')
    parser.add_argument('-ubase', '--usr-base', default=default_usr_base, help=f'用户基础目录 (默认: {default_usr_base})')
    parser.add_argument('-size', '--min-size', default=default_size, help=f'最小文件大小 (默认: {default_size})')
    parser.add_argument('-clean', '--clean-mode', action='store_true', help='清理模式')
    parser.add_argument('-no-delete-confirm', '--no-confirm', action='store_true', help='不需要删除确认')
    
    args = parser.parse_args()
    
    # 检查是否需要保存配置
    env_file = Path('lfs.ini')
    env_exists = env_file.exists()
    
    if should_save_config(env_exists, args, env_config):
        config_to_save = {
            'LFS-BASE': args.lfs_base,
            'USR-BASE': args.usr_base,
            'LFS-SIZE': args.min_size
        }
        save_env_config(config_to_save)
    
    try:
        # 解析大小参数
        min_size_bytes = parse_size(args.min_size)
        
        # 初始化LFS管理器
        lfs = LFSManager(args.lfs_base)
        
        # 初始化仓库（如果不存在）
        if not lfs.lfs_base.exists():
            lfs.init_repo()
        
        if args.clean_mode:
            # 清理模式
            lfs.clean_repo(args.no_confirm)
        else:
            # 处理模式
            lfs.process_files(args.usr_base, min_size_bytes, args.no_confirm)
            
    except Exception as e:
        print(f"错误: {e}")
        if os.getenv('LFS_DEBUG'):
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    main()