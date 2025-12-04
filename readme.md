# LFS (Large File System)

LFS (Large File System)，是一个Python实现的大文件管理系统(LFS)项目。

## 项目概述

LFS（Large File System）旨在优化大型文件的存储和管理。它通过将大文件存储到专门的仓库中，并在原位置创建链接的方式，有效节省磁盘空间并简化文件管理。

## 主要功能

### 1. 大文件识别与处理
- 自动扫描指定目录下的大文件
- 支持自定义文件大小阈值
- 忽略已存在的软链接文件

### 2. 文件存储与链接
- 将大文件存储到统一的LFS仓库中
- 在原位置创建指向仓库文件的软链接
- 使用SHA-256哈希值唯一标识文件

### 3. 文件分类管理
- 根据文件大小将文件分类存储:
  - 1M-10M
  - 10M-100M
  - 100M-500M
  - 500M-1G
  - 1G-5G
  - 5G以上

### 4. 仓库清理
- 自动检测并清理无链接指向的仓库文件
- 避免存储空间浪费

## 安装与配置

### 系统要求
- Python 3.8 或更高版本
- Windows/Linux/macOS 操作系统

### 配置文件
系统会在首次运行时创建 [lfs.ini](file://d:\Projects\Python\lfs\lfs.ini) 配置文件，包含以下参数：
```
LFS-BASE="./lfs_base/"    # LFS仓库根目录
USR-BASE="./"             # 用户文件根目录  
LFS-SIZE="10MB"           # 默认最小处理文件大小
```

## 使用方法

### 命令行参数

```bash
python lfs.py [选项]
```

常用选项：
- `-lbase, --lfs-base`: 指定LFS仓库目录 (默认: ./lfs_base/)
- `-ubase, --usr-base`: 指定用户文件目录 (默认: ./)
- `-size, --min-size`: 指定最小处理文件大小 (默认: 10MB)
- `-clean, --clean-mode`: 启用清理模式
- `-no-delete-confirm, --no-confirm`: 跳过删除确认

### 基本使用流程

1. **初始化和处理文件**：
   ```bash
   python lfs.py -ubase "/path/to/files" -size "50MB"
   ```

2. **清理无链接文件**：
   ```bash
   python lfs.py -clean -no-delete-confirm
   ```

### 编程接口

可以直接在Python代码中使用LFS功能：

```python
from lfs import LFSManager

# 创建LFS管理器实例
lfs = LFSManager('/path/to/lfs/repository')

# 初始化仓库
lfs.init_repo()

# 处理大于10MB的文件
lfs.process_files('/path/to/user/files', 10 * 1024 * 1024)

# 清理无链接文件
lfs.clean_repo(no_confirm=True)
```

## 工作原理

1. **文件扫描**: 递归扫描指定目录，找出大于设定阈值的文件
2. **哈希计算**: 为每个大文件计算SHA-256哈希值作为唯一标识
3. **文件存储**: 将文件按大小分类存储到LFS仓库对应目录中
4. **链接创建**: 在原位置创建指向仓库文件的软链接
5. **清单维护**: 更新 `lfs_assets.json` 清单文件记录文件信息

## 注意事项

- 系统会自动跳过包含 `lfs_assets.json` 的目录
- 不会对已存在的软链接文件进行处理
- Windows系统上启用了长路径支持以处理路径过长的问题
- 清理功能只会删除没有有效链接指向的仓库文件

## 文件结构

```
lfs_repository/
├── objects/              # 文件存储目录
│   ├── 1M-10M/          # 1MB-10MB文件
│   ├── 10M-100M/        # 10MB-100MB文件
│   ├── 100M-500M/       # 100MB-500MB文件
│   ├── 500M-1G/         # 500MB-1GB文件
│   ├── 1G-5G/           # 1GB-5GB文件
│   └── 5G-above/        # 5GB以上文件
└── lfs_assets.json      # 文件清单
```

## 故障排除

### 常见问题

1. **权限问题**: 确保对LFS仓库目录和用户文件目录有足够的读写权限
2. **软链接创建失败**: 在某些文件系统或操作系统上可能不支持软链接，系统会自动回退到文件复制
3. **路径过长**: Windows系统上已启用长路径支持，但仍需注意极端情况

### 调试模式

设置环境变量 `LFS_DEBUG=1` 可以启用调试输出，获取更多详细信息。
