# example_usage.py
"""
LFS使用示例
"""

import os
import tempfile
import shutil
from lfs import LFSManager

def demo_basic_usage():
    """演示基本用法"""
    print("=== LFS 基本使用演示 ===")
    
    # 创建临时目录用于演示
    test_root = tempfile.mkdtemp(prefix='lfs_demo_')
    lfs_dir = os.path.join(test_root, 'lfs_repository')
    usr_dir = os.path.join(test_root, 'user_files')
    
    try:
        # 创建目录
        os.makedirs(usr_dir)
        
        # 创建一些测试文件
        print("创建测试文件...")
        
        # 小文件 (< 1MB)
        with open(os.path.join(usr_dir, 'small_document.txt'), 'w') as f:
            f.write('这是一个小文件。\n' * 100)
            
        # 中等文件 (5MB)
        with open(os.path.join(usr_dir, 'medium_binary.dat'), 'wb') as f:
            f.write(b'Medium file content. ' * (5 * 1024 * 1024 // 20))
            
        # 大文件 (50MB)
        with open(os.path.join(usr_dir, 'large_archive.zip'), 'wb') as f:
            f.write(b'Large file content. ' * (50 * 1024 * 1024 // 20))
            
        # 在子目录中创建文件
        subdir = os.path.join(usr_dir, 'documents')
        os.makedirs(subdir)
        with open(os.path.join(subdir, 'huge_presentation.pptx'), 'wb') as f:
            f.write(b'Presentation data. ' * (30 * 1024 * 1024 // 20))
            
        print(f"测试文件已创建在: {usr_dir}")
        print(f"LFS仓库将创建在: {lfs_dir}")
        
        # 初始化LFS管理器
        lfs = LFSManager(lfs_dir)
        
        # 初始化仓库
        print("\n初始化LFS仓库...")
        lfs.init_repo()
        
        # 处理文件（最小大小设置为10MB）
        print("\n处理大于10MB的文件...")
        lfs.process_files(usr_dir, 10 * 1024 * 1024)  # 10MB
        
        # 显示结果
        print("\n处理完成!")
        print(f"- LFS仓库: {lfs_dir}")
        print(f"- 用户目录: {usr_dir}")
        print("- 处理了以下大文件:")
        print("  1. large_archive.zip (50MB)")
        print("  2. documents/huge_presentation.pptx (30MB)")
        print("- 小文件未被处理")
        
        # 演示清理功能
        print("\n演示清理功能...")
        print("(实际使用时，只有当链接断开的文件才会被清理)")
        lfs.clean_repo(no_confirm=True)
        
    finally:
        # 清理临时目录
        shutil.rmtree(test_root)
        print(f"\n清理临时目录: {test_root}")

def demo_advanced_features():
    """演示高级功能"""
    print("\n=== LFS 高级功能演示 ===")
    
    test_root = tempfile.mkdtemp(prefix='lfs_advanced_')
    lfs_dir = os.path.join(test_root, 'advanced_lfs')
    usr_dir = os.path.join(test_root, 'advanced_usr')
    
    try:
        # 创建目录
        os.makedirs(usr_dir)
        
        # 创建不同大小的测试文件以展示分类功能（去除超过1G的文件）
        files_info = [
            ('tiny.txt', 100 * 1024),           # 100KB - 不处理
            ('1m_file.dat', 2 * 1024 * 1024),   # 2MB - 分类到1M-10M
            ('25m_file.dat', 25 * 1024 * 1024), # 25MB - 分类到10M-100M
            ('150m_file.dat', 150 * 1024 * 1024), # 150MB - 分类到100M-500M
            ('600m_file.dat', 600 * 1024 * 1024), # 600MB - 分类到500M-1G
        ]
        
        print("创建不同大小的测试文件...")
        for filename, size in files_info:
            filepath = os.path.join(usr_dir, filename)
            with open(filepath, 'wb') as f:
                f.write(b'Test data. ' * (size // 10))
            print(f"  创建 {filename} ({size / (1024*1024):.1f}MB)")
        
        # 初始化LFS
        lfs = LFSManager(lfs_dir)
        lfs.init_repo()
        
        # 处理所有大于1MB的文件
        print("\n处理大于1MB的文件...")
        lfs.process_files(usr_dir, 1024 * 1024)
        
        # 显示仓库结构
        print("\nLFS仓库结构:")
        objects_dir = os.path.join(lfs_dir, 'objects')
        for category in os.listdir(objects_dir):
            category_path = os.path.join(objects_dir, category)
            if os.path.isdir(category_path):
                files_count = len(os.listdir(category_path)) if os.path.exists(category_path) else 0
                print(f"  {category}: {files_count} 个文件")
                
    finally:
        shutil.rmtree(test_root)
        print(f"\n清理临时目录: {test_root}")

def demo_cleanup_functionality():
    """演示清理功能"""
    print("\n=== LFS 清理功能演示 ===")
    
    test_root = tempfile.mkdtemp(prefix='lfs_cleanup_')
    lfs_dir = os.path.join(test_root, 'cleanup_lfs')
    usr_dir = os.path.join(test_root, 'cleanup_usr')
    
    try:
        # 创建目录
        os.makedirs(usr_dir)
        
        # 创建测试文件
        large_file = os.path.join(usr_dir, 'large_file.dat')
        with open(large_file, 'wb') as f:
            f.write(b'Large test data. ' * (20 * 1024 * 1024 // 10))  # 20MB
            
        print("创建20MB测试文件...")
        
        # 初始化LFS并处理文件
        lfs = LFSManager(lfs_dir)
        lfs.init_repo()
        lfs.process_files(usr_dir, 10 * 1024 * 1024)  # 处理大于10MB的文件
        
        print("文件已处理并存储到LFS仓库")
        
        # 删除原始文件以模拟链接断开
        print("删除原始文件以模拟链接断开...")
        os.remove(large_file)
        
        # 清理仓库
        print("清理仓库中无链接的文件...")
        lfs.clean_repo(no_confirm=True)
        
        print("清理完成！无链接的文件已被删除")
        
    finally:
        shutil.rmtree(test_root)
        print(f"\n清理临时目录: {test_root}")

if __name__ == '__main__':
    demo_basic_usage()
    demo_advanced_features()
    demo_cleanup_functionality()
    print("\n演示完成!")