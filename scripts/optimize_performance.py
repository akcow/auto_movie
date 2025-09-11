#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
性能优化脚本
自动分析和优化系统性能
"""

import os
import gc
import psutil
import time
from typing import Dict, List, Any
from utils.logger import LoggerMixin
from utils.file_utils import FileUtils

class PerformanceOptimizer(LoggerMixin):
    """性能优化器"""
    
    def __init__(self):
        """初始化"""
        self.start_time = time.time()
        self.initial_memory = self._get_memory_usage()
        
    def _get_memory_usage(self) -> Dict[str, float]:
        """获取内存使用情况"""
        process = psutil.Process()
        memory_info = process.memory_info()
        
        return {
            'rss': memory_info.rss / 1024 / 1024,  # MB
            'vms': memory_info.vms / 1024 / 1024,  # MB
            'percent': process.memory_percent()
        }
    
    def _get_disk_usage(self, path: str = ".") -> Dict[str, float]:
        """获取磁盘使用情况"""
        usage = psutil.disk_usage(path)
        
        return {
            'total': usage.total / 1024 / 1024 / 1024,  # GB
            'used': usage.used / 1024 / 1024 / 1024,    # GB
            'free': usage.free / 1024 / 1024 / 1024,    # GB
            'percent': (usage.used / usage.total) * 100
        }
    
    def analyze_system_performance(self) -> Dict[str, Any]:
        """分析系统性能"""
        self.logger.info("开始系统性能分析...")
        
        # CPU信息
        cpu_info = {
            'count': psutil.cpu_count(),
            'usage_percent': psutil.cpu_percent(interval=1),
            'load_avg': psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None
        }
        
        # 内存信息
        memory = psutil.virtual_memory()
        memory_info = {
            'total': memory.total / 1024 / 1024 / 1024,  # GB
            'available': memory.available / 1024 / 1024 / 1024,  # GB
            'percent': memory.percent,
            'used': memory.used / 1024 / 1024 / 1024,  # GB
        }
        
        # 磁盘信息
        disk_info = self._get_disk_usage()
        
        # 进程信息
        process_info = self._get_memory_usage()
        
        analysis = {
            'timestamp': time.time(),
            'cpu': cpu_info,
            'memory': memory_info,
            'disk': disk_info,
            'process': process_info,
            'python_version': psutil.__version__
        }
        
        self.logger.info(f"系统分析完成:")
        self.logger.info(f"  CPU使用率: {cpu_info['usage_percent']:.1f}%")
        self.logger.info(f"  内存使用率: {memory_info['percent']:.1f}%")
        self.logger.info(f"  磁盘使用率: {disk_info['percent']:.1f}%")
        self.logger.info(f"  进程内存: {process_info['rss']:.1f}MB")
        
        return analysis
    
    def optimize_memory(self) -> Dict[str, Any]:
        """优化内存使用"""
        self.logger.info("开始内存优化...")
        
        # 记录优化前状态
        before = self._get_memory_usage()
        
        # 强制垃圾回收
        collected = gc.collect()
        
        # 记录优化后状态
        after = self._get_memory_usage()
        
        optimization_result = {
            'collected_objects': collected,
            'memory_before': before,
            'memory_after': after,
            'memory_saved': before['rss'] - after['rss']
        }
        
        self.logger.info(f"内存优化完成:")
        self.logger.info(f"  回收对象数: {collected}")
        self.logger.info(f"  释放内存: {optimization_result['memory_saved']:.2f}MB")
        
        return optimization_result
    
    def analyze_disk_usage(self) -> Dict[str, Any]:
        """分析磁盘使用情况"""
        self.logger.info("分析磁盘使用情况...")
        
        directories_to_check = [
            './data/temp',
            './data/output', 
            './logs',
            './__pycache__',
            './.pytest_cache'
        ]
        
        disk_analysis = {}
        
        for directory in directories_to_check:
            if os.path.exists(directory):
                size = FileUtils.get_directory_size(directory)
                file_count = FileUtils.count_files_in_directory(directory)
                
                disk_analysis[directory] = {
                    'size_mb': size / 1024 / 1024,
                    'file_count': file_count,
                    'exists': True
                }
                
                self.logger.info(f"  {directory}: {size/1024/1024:.1f}MB, {file_count}个文件")
            else:
                disk_analysis[directory] = {
                    'size_mb': 0,
                    'file_count': 0,
                    'exists': False
                }
        
        return disk_analysis
    
    def clean_temporary_files(self) -> Dict[str, Any]:
        """清理临时文件"""
        self.logger.info("开始清理临时文件...")
        
        cleanup_result = {
            'temp_files_deleted': 0,
            'temp_size_freed': 0,
            'cache_files_deleted': 0,
            'cache_size_freed': 0,
            'total_size_freed': 0
        }
        
        # 清理临时文件目录
        temp_dir = './data/temp'
        if os.path.exists(temp_dir):
            temp_size_before = FileUtils.get_directory_size(temp_dir)
            
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    try:
                        file_path = os.path.join(root, file)
                        os.remove(file_path)
                        cleanup_result['temp_files_deleted'] += 1
                    except Exception as e:
                        self.logger.warning(f"无法删除临时文件 {file}: {e}")
            
            temp_size_after = FileUtils.get_directory_size(temp_dir) if os.path.exists(temp_dir) else 0
            cleanup_result['temp_size_freed'] = (temp_size_before - temp_size_after) / 1024 / 1024
        
        # 清理Python缓存
        cache_dirs = ['./__pycache__', './.pytest_cache']
        for cache_dir in cache_dirs:
            if os.path.exists(cache_dir):
                cache_size_before = FileUtils.get_directory_size(cache_dir)
                
                try:
                    FileUtils.remove_directory(cache_dir)
                    cleanup_result['cache_files_deleted'] += 1
                    cleanup_result['cache_size_freed'] += cache_size_before / 1024 / 1024
                except Exception as e:
                    self.logger.warning(f"无法删除缓存目录 {cache_dir}: {e}")
        
        cleanup_result['total_size_freed'] = cleanup_result['temp_size_freed'] + cleanup_result['cache_size_freed']
        
        self.logger.info(f"临时文件清理完成:")
        self.logger.info(f"  删除临时文件: {cleanup_result['temp_files_deleted']}个")
        self.logger.info(f"  释放空间: {cleanup_result['total_size_freed']:.2f}MB")
        
        return cleanup_result
    
    def optimize_configuration(self) -> Dict[str, Any]:
        """优化配置建议"""
        self.logger.info("生成性能优化建议...")
        
        system_info = self.analyze_system_performance()
        
        recommendations = []
        
        # 基于系统资源给出建议
        if system_info['memory']['percent'] > 80:
            recommendations.append({
                'type': 'memory',
                'priority': 'high',
                'suggestion': '内存使用率过高，建议降低并发处理数量',
                'config': {
                    'performance': {
                        'max_concurrent_requests': 1
                    }
                }
            })
        elif system_info['memory']['percent'] < 50:
            recommendations.append({
                'type': 'memory',
                'priority': 'low',
                'suggestion': '内存充足，可以适当增加并发处理数量',
                'config': {
                    'performance': {
                        'max_concurrent_requests': 4
                    }
                }
            })
        
        if system_info['cpu']['usage_percent'] > 80:
            recommendations.append({
                'type': 'cpu',
                'priority': 'high',
                'suggestion': 'CPU使用率高，建议降低处理质量或并发数',
                'config': {
                    'generation': {
                        'image_quality': 'normal'
                    }
                }
            })
        
        if system_info['disk']['percent'] > 90:
            recommendations.append({
                'type': 'disk',
                'priority': 'critical',
                'suggestion': '磁盘空间不足，建议启用自动清理',
                'config': {
                    'storage': {
                        'auto_cleanup': True,
                        'keep_days': 1
                    }
                }
            })
        
        optimization_suggestions = {
            'system_status': system_info,
            'recommendations': recommendations,
            'generated_at': time.time()
        }
        
        self.logger.info(f"生成了 {len(recommendations)} 条优化建议")
        
        return optimization_suggestions
    
    def run_full_optimization(self) -> Dict[str, Any]:
        """运行完整优化"""
        self.logger.info("开始完整性能优化...")
        
        start_time = time.time()
        
        # 1. 系统性能分析
        system_analysis = self.analyze_system_performance()
        
        # 2. 内存优化
        memory_optimization = self.optimize_memory()
        
        # 3. 磁盘分析
        disk_analysis = self.analyze_disk_usage()
        
        # 4. 清理临时文件
        cleanup_result = self.clean_temporary_files()
        
        # 5. 生成优化建议
        optimization_suggestions = self.optimize_configuration()
        
        end_time = time.time()
        
        full_result = {
            'optimization_time': end_time - start_time,
            'system_analysis': system_analysis,
            'memory_optimization': memory_optimization,
            'disk_analysis': disk_analysis,
            'cleanup_result': cleanup_result,
            'suggestions': optimization_suggestions,
            'timestamp': end_time
        }
        
        self.logger.info(f"完整优化完成，用时 {end_time - start_time:.2f}秒")
        
        return full_result

def main():
    """主函数"""
    print("开始系统性能优化...")
    
    optimizer = PerformanceOptimizer()
    result = optimizer.run_full_optimization()
    
    print("\n优化结果摘要:")
    print(f"优化用时: {result['optimization_time']:.2f}秒")
    print(f"内存释放: {result['memory_optimization']['memory_saved']:.2f}MB")
    print(f"磁盘释放: {result['cleanup_result']['total_size_freed']:.2f}MB")
    print(f"优化建议: {len(result['suggestions']['recommendations'])}条")
    
    print("\n系统状态:")
    sys_info = result['system_analysis']
    print(f"   CPU使用率: {sys_info['cpu']['usage_percent']:.1f}%")
    print(f"   内存使用率: {sys_info['memory']['percent']:.1f}%")
    print(f"   磁盘使用率: {sys_info['disk']['percent']:.1f}%")
    
    if result['suggestions']['recommendations']:
        print("\n优化建议:")
        for i, rec in enumerate(result['suggestions']['recommendations'], 1):
            priority_text = "[关键]" if rec['priority'] == 'critical' else "[高]" if rec['priority'] == 'high' else "[低]"
            print(f"   {i}. {priority_text} {rec['suggestion']}")
    
    print("\n性能优化完成！")

if __name__ == "__main__":
    main()