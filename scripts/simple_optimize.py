#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
简单性能优化脚本
清理临时文件和缓存
"""

import os
import gc
import shutil
import time
from utils.logger import LoggerMixin

class SimpleOptimizer(LoggerMixin):
    """简单性能优化器"""
    
    def __init__(self):
        """初始化"""
        self.start_time = time.time()
    
    def get_directory_size(self, path):
        """获取目录大小"""
        if not os.path.exists(path):
            return 0
        
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                try:
                    total_size += os.path.getsize(filepath)
                except (OSError, FileNotFoundError):
                    continue
        return total_size
    
    def count_files(self, path):
        """计算目录中的文件数"""
        if not os.path.exists(path):
            return 0
        
        count = 0
        for root, dirs, files in os.walk(path):
            count += len(files)
        return count
    
    def clean_directory(self, path, keep_directory=True):
        """清理目录内容"""
        if not os.path.exists(path):
            return 0, 0
        
        size_before = self.get_directory_size(path)
        files_deleted = 0
        
        try:
            if keep_directory:
                # 保留目录，删除内容
                for root, dirs, files in os.walk(path, topdown=False):
                    for file in files:
                        try:
                            os.remove(os.path.join(root, file))
                            files_deleted += 1
                        except Exception:
                            continue
                    for dir in dirs:
                        try:
                            shutil.rmtree(os.path.join(root, dir))
                        except Exception:
                            continue
            else:
                # 删除整个目录
                shutil.rmtree(path)
                files_deleted = self.count_files(path)
        except Exception as e:
            self.logger.warning(f"清理目录 {path} 时出错: {e}")
        
        size_after = self.get_directory_size(path) if os.path.exists(path) else 0
        size_freed = (size_before - size_after) / 1024 / 1024  # MB
        
        return files_deleted, size_freed
    
    def optimize_memory(self):
        """优化内存"""
        self.logger.info("执行内存优化...")
        collected = gc.collect()
        self.logger.info(f"回收了 {collected} 个对象")
        return collected
    
    def clean_temp_files(self):
        """清理临时文件"""
        self.logger.info("清理临时文件...")
        
        temp_dirs = [
            './data/temp',
            './__pycache__',
            './.pytest_cache'
        ]
        
        total_files_deleted = 0
        total_size_freed = 0
        
        for temp_dir in temp_dirs:
            if os.path.exists(temp_dir):
                files, size = self.clean_directory(temp_dir, keep_directory=(temp_dir == './data/temp'))
                total_files_deleted += files
                total_size_freed += size
                
                if size > 0:
                    self.logger.info(f"清理 {temp_dir}: {files}个文件, {size:.2f}MB")
        
        return total_files_deleted, total_size_freed
    
    def analyze_disk_usage(self):
        """分析磁盘使用"""
        self.logger.info("分析磁盘使用情况...")
        
        directories = [
            './data',
            './logs',
            './processors',
            './utils',
            './tests'
        ]
        
        analysis = {}
        
        for directory in directories:
            if os.path.exists(directory):
                size = self.get_directory_size(directory)
                files = self.count_files(directory)
                
                analysis[directory] = {
                    'size_mb': size / 1024 / 1024,
                    'files': files
                }
                
                self.logger.info(f"{directory}: {size/1024/1024:.1f}MB, {files}个文件")
            else:
                analysis[directory] = {'size_mb': 0, 'files': 0}
        
        return analysis
    
    def generate_optimization_tips(self):
        """生成优化建议"""
        tips = [
            "定期清理 data/temp 目录中的临时文件",
            "使用 auto_cleanup: true 配置自动清理临时文件", 
            "调整 max_concurrent_requests 参数控制并发数",
            "根据系统性能调整 image_quality 参数",
            "启用成本控制避免过度使用API资源",
            "定期运行 python simple_optimize.py 进行优化"
        ]
        
        self.logger.info("性能优化建议:")
        for i, tip in enumerate(tips, 1):
            self.logger.info(f"{i}. {tip}")
        
        return tips
    
    def run_optimization(self):
        """运行优化"""
        self.logger.info("开始性能优化...")
        
        start_time = time.time()
        
        # 1. 内存优化
        collected_objects = self.optimize_memory()
        
        # 2. 磁盘分析
        disk_analysis = self.analyze_disk_usage()
        
        # 3. 清理临时文件
        files_deleted, size_freed = self.clean_temp_files()
        
        # 4. 生成建议
        tips = self.generate_optimization_tips()
        
        end_time = time.time()
        
        result = {
            'optimization_time': end_time - start_time,
            'memory_objects_collected': collected_objects,
            'files_deleted': files_deleted,
            'disk_space_freed': size_freed,
            'disk_analysis': disk_analysis,
            'optimization_tips': tips
        }
        
        self.logger.info(f"优化完成，用时 {end_time - start_time:.2f}秒")
        
        return result

def main():
    """主函数"""
    print("开始系统性能优化...")
    
    optimizer = SimpleOptimizer()
    result = optimizer.run_optimization()
    
    print("\n优化结果:")
    print(f"优化用时: {result['optimization_time']:.2f}秒")
    print(f"回收内存对象: {result['memory_objects_collected']}个")
    print(f"删除临时文件: {result['files_deleted']}个")
    print(f"释放磁盘空间: {result['disk_space_freed']:.2f}MB")
    
    print("\n磁盘使用情况:")
    for path, info in result['disk_analysis'].items():
        print(f"  {path}: {info['size_mb']:.1f}MB ({info['files']}个文件)")
    
    print("\n优化建议:")
    for i, tip in enumerate(result['optimization_tips'], 1):
        print(f"  {i}. {tip}")
    
    print("\n性能优化完成！")

if __name__ == "__main__":
    main()