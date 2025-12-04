# test_lfs.py
import unittest
import tempfile
import os
import shutil
import json
import sys
from pathlib import Path
from lfs import (
    LFSManager, 
    parse_size, 
    load_env_config, 
    should_save_config, 
    save_env_config
)

class TestLFSParseSize(unittest.TestCase):
    """测试parse_size函数"""
    
    def test_parse_bytes(self):
        self.assertEqual(parse_size("1024B"), 1024)
        self.assertEqual(parse_size("512"), 512 * 1024 * 1024)  # 默认MB
        
    def test_parse_kilobytes(self):
        self.assertEqual(parse_size("1K"), 1024)
        self.assertEqual(parse_size("2KB"), 2048)
        
    def test_parse_megabytes(self):
        self.assertEqual(parse_size("1M"), 1024*1024)
        self.assertEqual(parse_size("5MB"), 5*1024*1024)
        
    def test_parse_gigabytes(self):
        self.assertEqual(parse_size("1G"), 1024*1024*1024)
        self.assertEqual(parse_size("2GB"), 2*1024*1024*1024)
        
    def test_parse_terabytes(self):
        self.assertEqual(parse_size("1T"), 1024*1024*1024*1024)
        self.assertEqual(parse_size("1TB"), 1024*1024*1024*1024)
        
    def test_case_insensitive(self):
        self.assertEqual(parse_size("1m"), 1024*1024)
        self.assertEqual(parse_size("2gb"), 2*1024*1024*1024)
        
    def test_default_mb(self):
        self.assertEqual(parse_size("10"), 10*1024*1024)
        
    def test_invalid_input(self):
        self.assertEqual(parse_size("invalid"), 10*1024*1024)  # 默认10MB
        self.assertEqual(parse_size(""), 10*1024*1024)  # 默认10MB

class TestLFSConfigFunctions(unittest.TestCase):
    """测试配置相关函数"""
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.old_cwd = os.getcwd()
        os.chdir(self.test_dir)
        
    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.test_dir)
        
    def test_load_env_config_empty(self):
        config = load_env_config()
        self.assertEqual(config, {})
        
    def test_load_env_config_with_content(self):
        # 创建测试配置文件
        with open('lfs.ini', 'w', encoding='utf-8') as f:
            f.write('LFS-BASE="./test_lfs"\n')
            f.write('USR-BASE="./test_usr"\n')
            f.write('LFS-SIZE="50MB"\n')
            
        config = load_env_config()
        self.assertEqual(config['LFS-BASE'], './test_lfs')
        self.assertEqual(config['USR-BASE'], './test_usr')
        self.assertEqual(config['LFS-SIZE'], '50MB')
        
    def test_save_env_config(self):
        config = {
            'LFS-BASE': './saved_lfs',
            'USR-BASE': './saved_usr',
            'LFS-SIZE': '100MB'
        }
        
        save_env_config(config)
        
        # 验证文件是否正确保存
        self.assertTrue(os.path.exists('lfs.ini'))
        loaded_config = load_env_config()
        self.assertEqual(loaded_config, config)
        
    def test_should_save_config_new_file(self):
        class MockArgs:
            def __init__(self):
                self.lfs_base = './lfs_base'
                self.usr_base = '.'
                self.min_size = '10MB'
                
        args = MockArgs()
        result = should_save_config(False, args, {})
        self.assertTrue(result)
        
    def test_should_save_config_no_change(self):
        class MockArgs:
            def __init__(self):
                self.lfs_base = './lfs_base/'
                self.usr_base = './'
                self.min_size = '10MB'
                
        args = MockArgs()
        env_config = {
            'LFS-BASE': './lfs_base/',
            'USR-BASE': './',
            'LFS-SIZE': '10MB'
        }
        
        result = should_save_config(True, args, env_config)
        self.assertFalse(result)

class TestLFSManager(unittest.TestCase):
    """测试LFSManager类"""
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.lfs_dir = os.path.join(self.test_dir, 'lfs')
        self.usr_dir = os.path.join(self.test_dir, 'usr')
        
        # 创建测试目录
        os.makedirs(self.lfs_dir)
        os.makedirs(self.usr_dir)
        
        self.lfs = LFSManager(self.lfs_dir)
        
    def tearDown(self):
        shutil.rmtree(self.test_dir)
        
    def test_init_repo(self):
        self.lfs.init_repo()
        
        # 验证仓库目录结构
        self.assertTrue(os.path.exists(self.lfs_dir))
        self.assertTrue(os.path.exists(os.path.join(self.lfs_dir, 'objects')))
        
        # 验证分类目录
        categories = ["1M-10M", "10M-100M", "100M-500M", "500M-1G", "1G-5G", "5G-above"]
        for category in categories:
            self.assertTrue(os.path.exists(os.path.join(self.lfs_dir, 'objects', category)))
            
        # 验证清单文件
        self.assertTrue(os.path.exists(os.path.join(self.lfs_dir, 'lfs_assets.json')))
        
    def test_get_size_category(self):
        # 测试各个分类 - 修正边界值测试
        # 注意：小于1MB的文件不会被LFS系统处理，所以不测试这类情况
        self.assertEqual(self.lfs._get_size_category(1024*1024), "1M-10M")            # 1M (下界)
        self.assertEqual(self.lfs._get_size_category(5*1024*1024), "1M-10M")          # 5M
        self.assertEqual(self.lfs._get_size_category(10*1024*1024 - 1), "1M-10M")     # 接近10M (上界)
        self.assertEqual(self.lfs._get_size_category(10*1024*1024), "10M-100M")       # 10M (下界)
        self.assertEqual(self.lfs._get_size_category(50*1024*1024), "10M-100M")       # 50M
        self.assertEqual(self.lfs._get_size_category(100*1024*1024), "100M-500M")     # 100M (下界)
        self.assertEqual(self.lfs._get_size_category(200*1024*1024), "100M-500M")     # 200M
        self.assertEqual(self.lfs._get_size_category(500*1024*1024), "500M-1G")       # 500M (下界)
        self.assertEqual(self.lfs._get_size_category(512*1024*1024), "500M-1G")       # 512M
        self.assertEqual(self.lfs._get_size_category(1024*1024*1024), "1G-5G")        # 1G (下界)
        self.assertEqual(self.lfs._get_size_category(2*1024*1024*1024), "1G-5G")      # 2G
        self.assertEqual(self.lfs._get_size_category(5*1024*1024*1024), "5G-above")   # 5G (下界)
        self.assertEqual(self.lfs._get_size_category(10*1024*1024*1024), "5G-above")  # 10G        

    def test_get_file_hash(self):
        # 创建测试文件
        test_file = os.path.join(self.usr_dir, 'test.txt')
        with open(test_file, 'w') as f:
            f.write('Hello, World!')
            
        # 计算哈希值
        file_hash = self.lfs._get_file_hash(Path(test_file))
        
        # 验证哈希值不为空且为十六进制字符串
        self.assertIsNotNone(file_hash)
        self.assertGreater(len(file_hash), 0)
        # SHA256哈希值应该是64个字符
        self.assertEqual(len(file_hash), 64)
        
    def test_safe_copy(self):
        # 创建源文件
        src_file = os.path.join(self.usr_dir, 'source.txt')
        with open(src_file, 'w') as f:
            f.write('Test content for copying')
            
        # 目标文件
        dst_file = os.path.join(self.usr_dir, 'destination.txt')
        
        # 执行复制
        self.lfs._safe_copy(Path(src_file), Path(dst_file))
        
        # 验证文件已复制
        self.assertTrue(os.path.exists(dst_file))
        
        # 验证内容相同
        with open(src_file, 'r') as src, open(dst_file, 'r') as dst:
            self.assertEqual(src.read(), dst.read())
            
    def test_store_and_link_file(self):
        # 初始化仓库
        self.lfs.init_repo()
        
        # 创建测试文件
        test_file = os.path.join(self.usr_dir, 'large_file.bin')
        with open(test_file, 'wb') as f:
            # 创建一个大于10M的文件以确保被处理
            f.write(b'0' * (15 * 1024 * 1024))  # 15MB
            
        # 创建空的manifest
        manifest = {}
        
        # 存储并链接文件
        result = self.lfs.store_and_link_file(Path(test_file), manifest)
        
        self.assertTrue(result)
        
        # 验证manifest中有条目
        self.assertEqual(len(manifest), 1)
        
        # 获取文件哈希以验证存储路径
        file_hash = list(manifest.keys())[0].replace('sha256:', '')
        expected_storage_path = os.path.join(self.lfs_dir, 'objects', '10M-100M', file_hash)
        
        # 验证文件已存储到仓库
        self.assertTrue(os.path.exists(expected_storage_path))
        
        # 验证原文件仍存在
        self.assertTrue(os.path.exists(test_file))

class TestIntegration(unittest.TestCase):
    """集成测试"""
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.lfs_dir = os.path.join(self.test_dir, 'lfs')
        self.usr_dir = os.path.join(self.test_dir, 'usr')
        
        # 创建测试目录
        os.makedirs(self.lfs_dir)
        os.makedirs(self.usr_dir)
        
    def tearDown(self):
        shutil.rmtree(self.test_dir)
        
    def test_full_workflow(self):
        """测试完整工作流程"""
        # 初始化LFS管理器
        lfs = LFSManager(self.lfs_dir)
        
        # 初始化仓库
        lfs.init_repo()
        
        # 创建测试文件（包括大文件和小文件）
        small_file = os.path.join(self.usr_dir, 'small.txt')
        with open(small_file, 'w') as f:
            f.write('Small file content')
            
        large_file1 = os.path.join(self.usr_dir, 'large1.bin')
        with open(large_file1, 'wb') as f:
            f.write(b'1' * (15 * 1024 * 1024))  # 15MB
            
        large_file2 = os.path.join(self.usr_dir, 'subdir', 'large2.bin')
        os.makedirs(os.path.dirname(large_file2))
        with open(large_file2, 'wb') as f:
            f.write(b'2' * (25 * 1024 * 1024))  # 25MB
            
        # 处理文件（最小大小设为10MB）
        lfs.process_files(self.usr_dir, 10*1024*1024)
        
        # 验证清单文件存在且有内容
        manifest_file = os.path.join(self.lfs_dir, 'lfs_assets.json')
        self.assertTrue(os.path.exists(manifest_file))
        
        with open(manifest_file, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
            
        # 应该有两个大文件被处理
        self.assertEqual(len(manifest), 2)
        
        # 验证存储的文件
        for entry in manifest.values():
            storage_path = os.path.join(self.lfs_dir, entry['storage_path'])
            self.assertTrue(os.path.exists(storage_path))
            
        # 验证原始大文件仍存在
        self.assertTrue(os.path.exists(large_file1))
        self.assertTrue(os.path.exists(large_file2))
        
    def test_clean_repo(self):
        """测试仓库清理功能"""
        lfs = LFSManager(self.lfs_dir)
        lfs.init_repo()
        
        # 创建测试文件
        large_file = os.path.join(self.usr_dir, 'large.bin')
        with open(large_file, 'wb') as f:
            f.write(b'test' * (15 * 1024 * 1024))  # 15MB
            
        # 处理文件
        lfs.process_files(self.usr_dir, 10*1024*1024)
        
        # 验证文件已存储
        manifest_file = os.path.join(self.lfs_dir, 'lfs_assets.json')
        with open(manifest_file, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
            
        self.assertEqual(len(manifest), 1)
        
        # 清理仓库（自动确认）
        lfs.clean_repo(no_confirm=True)
        
        # 验证清理功能至少能正常运行而不报错
        
    def test_clean_repo_after_file_deletion(self):
        
        """测试删除文件后清理仓库的功能"""
        lfs = LFSManager(self.lfs_dir)
        lfs.init_repo()
        
        # 创建测试文件
        large_file = os.path.join(self.usr_dir, 'large.bin')
        with open(large_file, 'wb') as f:
            f.write(b'test' * (15 * 1024 * 1024))  # 15MB
            
        # 处理文件
        lfs.process_files(self.usr_dir, 10*1024*1024)
        
        # 验证文件已存储
        manifest_file = os.path.join(self.lfs_dir, 'lfs_assets.json')
        with open(manifest_file, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
            
        self.assertEqual(len(manifest), 1)
        
        # 删除原始文件（模拟链接断开的情况）
        os.remove(large_file)
        
        # 清理仓库（自动确认）
        lfs.clean_repo(no_confirm=True)
        
        # 验证文件在仓库中已被删除
        # 获取存储路径
        entry = list(manifest.values())[0]
        storage_path = os.path.join(self.lfs_dir, entry['storage_path'])
        
        # 验证存储文件已被清理
        self.assertFalse(os.path.exists(storage_path))
        
        # 验证清单已更新
        with open(manifest_file, 'r', encoding='utf-8') as f:
            updated_manifest = json.load(f)
            
        self.assertEqual(len(updated_manifest), 0)

def create_test_environment():
    """创建用于手动测试的环境"""
    test_root = tempfile.mkdtemp(prefix='lfs_test_')
    print(f"创建测试环境: {test_root}")
    
    # 创建目录结构
    lfs_dir = os.path.join(test_root, 'lfs_repo')
    usr_dir = os.path.join(test_root, 'user_files')
    os.makedirs(lfs_dir)
    os.makedirs(usr_dir)
    
    # 创建测试文件
    # 小文件
    with open(os.path.join(usr_dir, 'small.txt'), 'w') as f:
        f.write('Small file content')
        
    # 中等文件
    with open(os.path.join(usr_dir, 'medium.bin'), 'wb') as f:
        f.write(b'M' * (5 * 1024 * 1024))  # 5MB
        
    # 大文件
    with open(os.path.join(usr_dir, 'large.bin'), 'wb') as f:
        f.write(b'L' * (50 * 1024 * 1024))  # 50MB
        
    # 嵌套目录中的文件
    subdir = os.path.join(usr_dir, 'subdir')
    os.makedirs(subdir)
    with open(os.path.join(subdir, 'nested_large.bin'), 'wb') as f:
        f.write(b'N' * (25 * 1024 * 1024))  # 25MB
        
    print(f"LFS仓库目录: {lfs_dir}")
    print(f"用户文件目录: {usr_dir}")
    print("测试环境创建完成")
    
    return test_root, lfs_dir, usr_dir

if __name__ == '__main__':
    # 如果直接运行此脚本，创建测试环境供手动测试
    if len(sys.argv) > 1 and sys.argv[1] == 'setup':
        create_test_environment()
    else:
        # 运行单元测试
        unittest.main()