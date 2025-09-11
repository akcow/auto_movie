#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
文件处理工具模块
提供文件操作、路径处理等工具函数
"""

import os
import shutil
import hashlib
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
import yaml
import json
from .logger import LoggerMixin


class FileUtils(LoggerMixin):
    """文件处理工具类"""
    
    @staticmethod
    def ensure_dir(path: Union[str, Path]) -> Path:
        """
        确保目录存在，如果不存在则创建
        
        Args:
            path: 目录路径
            
        Returns:
            Path对象
        """
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @staticmethod
    def path_exists(path: Union[str, Path]) -> bool:
        """
        检查路径是否存在
        
        Args:
            path: 文件或目录路径
            
        Returns:
            是否存在
        """
        return Path(path).exists()
    
    @staticmethod
    def read_text_file(file_path: Union[str, Path], encoding: str = 'utf-8') -> str:
        """
        读取文本文件
        
        Args:
            file_path: 文件路径
            encoding: 文件编码
            
        Returns:
            文件内容
        """
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            # 尝试其他编码
            encodings = ['gbk', 'gb2312', 'utf-8-sig', 'latin1']
            for enc in encodings:
                try:
                    with open(file_path, 'r', encoding=enc) as f:
                        content = f.read()
                        return content
                except UnicodeDecodeError:
                    continue
            raise ValueError(f"无法识别文件编码: {file_path}")
    
    @staticmethod
    def write_text_file(
        file_path: Union[str, Path], 
        content: str, 
        encoding: str = 'utf-8',
        ensure_dir: bool = True
    ) -> None:
        """
        写入文本文件
        
        Args:
            file_path: 文件路径
            content: 文件内容
            encoding: 文件编码
            ensure_dir: 是否自动创建目录
        """
        file_path = Path(file_path)
        
        if ensure_dir:
            FileUtils.ensure_dir(file_path.parent)
        
        with open(file_path, 'w', encoding=encoding) as f:
            f.write(content)
    
    @staticmethod
    def load_yaml(file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        加载YAML配置文件
        
        Args:
            file_path: YAML文件路径
            
        Returns:
            解析后的配置字典
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            raise ValueError(f"加载YAML文件失败 {file_path}: {e}")
    
    @staticmethod
    def save_yaml(data: Dict[str, Any], file_path: Union[str, Path]) -> None:
        """
        保存数据到YAML文件
        
        Args:
            data: 要保存的数据
            file_path: YAML文件路径
        """
        FileUtils.ensure_dir(Path(file_path).parent)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
    
    @staticmethod
    def load_json(file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        加载JSON文件
        
        Args:
            file_path: JSON文件路径
            
        Returns:
            解析后的JSON数据
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    @staticmethod
    def save_json(
        data: Dict[str, Any], 
        file_path: Union[str, Path],
        indent: int = 2
    ) -> None:
        """
        保存数据到JSON文件
        
        Args:
            data: 要保存的数据
            file_path: JSON文件路径
            indent: 缩进空格数
        """
        FileUtils.ensure_dir(Path(file_path).parent)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
    
    @staticmethod
    def get_file_hash(file_path: Union[str, Path], algorithm: str = 'md5') -> str:
        """
        计算文件哈希值
        
        Args:
            file_path: 文件路径
            algorithm: 哈希算法 (md5, sha1, sha256)
            
        Returns:
            文件哈希值
        """
        hash_func = hashlib.new(algorithm)
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_func.update(chunk)
        
        return hash_func.hexdigest()
    
    @staticmethod
    def get_file_size(file_path: Union[str, Path]) -> int:
        """
        获取文件大小(字节)
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件大小
        """
        return Path(file_path).stat().st_size
    
    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """
        格式化文件大小
        
        Args:
            size_bytes: 文件大小(字节)
            
        Returns:
            格式化的大小字符串
        """
        if size_bytes == 0:
            return "0B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        import math
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s}{size_names[i]}"
    
    @staticmethod
    def clean_filename(filename: str) -> str:
        """
        清理文件名，移除非法字符
        
        Args:
            filename: 原始文件名
            
        Returns:
            清理后的文件名
        """
        # 移除非法字符
        illegal_chars = r'<>:"/\|?*'
        for char in illegal_chars:
            filename = filename.replace(char, '_')
        
        # 移除首尾空格和点
        filename = filename.strip('. ')
        
        return filename
    
    @staticmethod
    def move_file(src: Union[str, Path], dst: Union[str, Path]) -> None:
        """
        移动文件
        
        Args:
            src: 源文件路径
            dst: 目标文件路径
        """
        src_path = Path(src)
        dst_path = Path(dst)
        
        # 确保目标目录存在
        FileUtils.ensure_dir(dst_path.parent)
        
        shutil.move(str(src_path), str(dst_path))
    
    @staticmethod
    def copy_file(src: Union[str, Path], dst: Union[str, Path]) -> None:
        """
        复制文件
        
        Args:
            src: 源文件路径
            dst: 目标文件路径
        """
        src_path = Path(src)
        dst_path = Path(dst)
        
        # 确保目标目录存在
        FileUtils.ensure_dir(dst_path.parent)
        
        shutil.copy2(str(src_path), str(dst_path))
    
    @staticmethod
    def delete_file(file_path: Union[str, Path]) -> None:
        """
        删除文件
        
        Args:
            file_path: 文件路径
        """
        path = Path(file_path)
        if path.exists():
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(path)
    
    @staticmethod
    def list_files(
        directory: Union[str, Path], 
        pattern: str = "*",
        recursive: bool = False
    ) -> List[Path]:
        """
        列出目录中的文件
        
        Args:
            directory: 目录路径
            pattern: 文件匹配模式
            recursive: 是否递归搜索
            
        Returns:
            文件路径列表
        """
        dir_path = Path(directory)
        
        if recursive:
            return list(dir_path.rglob(pattern))
        else:
            return list(dir_path.glob(pattern))
    
    @staticmethod
    def cleanup_temp_files(
        temp_dir: Union[str, Path], 
        max_age_hours: int = 24
    ) -> int:
        """
        清理临时文件
        
        Args:
            temp_dir: 临时目录路径
            max_age_hours: 文件最大保留时间(小时)
            
        Returns:
            清理的文件数量
        """
        import time
        
        temp_path = Path(temp_dir)
        if not temp_path.exists():
            return 0
        
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        cleaned_count = 0
        
        for file_path in temp_path.rglob('*'):
            if file_path.is_file():
                file_age = current_time - file_path.stat().st_mtime
                if file_age > max_age_seconds:
                    try:
                        file_path.unlink()
                        cleaned_count += 1
                    except Exception:
                        pass  # 忽略删除失败的文件
        
        return cleaned_count


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """
    加载配置文件的便捷函数
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        配置字典
    """
    return FileUtils.load_yaml(config_path)


if __name__ == "__main__":
    # 测试文件工具
    utils = FileUtils()
    
    # 测试目录创建
    test_dir = "./test_output"
    utils.ensure_dir(test_dir)
    print(f"创建目录: {test_dir}")
    
    # 测试文件写入和读取
    test_file = f"{test_dir}/test.txt"
    utils.write_text_file(test_file, "测试内容")
    content = utils.read_text_file(test_file)
    print(f"文件内容: {content}")
    
    # 清理测试文件
    utils.delete_file(test_dir)