#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
性能优化工具模块
提供内存管理、性能监控、资源清理等功能
"""

import gc
import os
import sys
import time
import psutil
import threading
import functools
from typing import Any, Callable, Dict, List, Optional
from contextlib import contextmanager

from .logger import LoggerMixin


class MemoryManager(LoggerMixin):
    """内存管理器"""
    
    def __init__(self, max_memory_mb: int = 2048):
        """
        初始化内存管理器
        
        Args:
            max_memory_mb: 最大内存使用量(MB)
        """
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.process = psutil.Process()
        self._memory_warnings = 0
    
    def get_memory_usage(self) -> Dict[str, float]:
        """获取当前内存使用情况"""
        try:
            memory_info = self.process.memory_info()
            memory_percent = self.process.memory_percent()
            
            return {
                'rss_mb': memory_info.rss / 1024 / 1024,
                'vms_mb': memory_info.vms / 1024 / 1024,
                'percent': memory_percent,
                'available_mb': psutil.virtual_memory().available / 1024 / 1024
            }
        except Exception as e:
            self.logger.warning(f"获取内存使用情况失败: {e}")
            return {'rss_mb': 0, 'vms_mb': 0, 'percent': 0, 'available_mb': 0}
    
    def check_memory_pressure(self) -> bool:
        """检查内存压力"""
        memory_info = self.get_memory_usage()
        
        if memory_info['rss_mb'] * 1024 * 1024 > self.max_memory_bytes:
            self._memory_warnings += 1
            self.logger.warning(f"内存使用超限: {memory_info['rss_mb']:.1f}MB")
            return True
        
        return False
    
    def force_gc(self) -> Dict[str, int]:
        """强制垃圾回收"""
        before_memory = self.get_memory_usage()['rss_mb']
        
        # 执行垃圾回收
        collected = {
            'gen0': gc.collect(0),
            'gen1': gc.collect(1), 
            'gen2': gc.collect(2)
        }
        
        after_memory = self.get_memory_usage()['rss_mb']
        freed_mb = before_memory - after_memory
        
        self.logger.debug(f"垃圾回收释放内存: {freed_mb:.1f}MB")
        
        return {
            'collected': collected,
            'freed_mb': freed_mb
        }
    
    @contextmanager
    def memory_limit_context(self):
        """内存限制上下文管理器"""
        start_memory = self.get_memory_usage()['rss_mb']
        
        try:
            yield
        finally:
            end_memory = self.get_memory_usage()['rss_mb']
            memory_delta = end_memory - start_memory
            
            if memory_delta > 100:  # 增长超过100MB
                self.logger.warning(f"内存增长: {memory_delta:.1f}MB")
                self.force_gc()
    
    def cleanup_large_objects(self):
        """清理大对象"""
        # 获取所有对象
        all_objects = gc.get_objects()
        large_objects = []
        
        for obj in all_objects:
            try:
                size = sys.getsizeof(obj)
                if size > 10 * 1024 * 1024:  # 大于10MB的对象
                    large_objects.append((type(obj).__name__, size))
            except (TypeError, AttributeError):
                continue
        
        if large_objects:
            self.logger.warning(f"发现 {len(large_objects)} 个大对象")
            for obj_type, size in large_objects[:5]:  # 显示前5个
                self.logger.warning(f"  {obj_type}: {size / 1024 / 1024:.1f}MB")


class PerformanceMonitor(LoggerMixin):
    """性能监控器"""
    
    def __init__(self):
        self.metrics = {}
        self._lock = threading.Lock()
    
    def record_timing(self, operation: str, duration: float):
        """记录操作耗时"""
        with self._lock:
            if operation not in self.metrics:
                self.metrics[operation] = {
                    'count': 0,
                    'total_time': 0.0,
                    'min_time': float('inf'),
                    'max_time': 0.0
                }
            
            metric = self.metrics[operation]
            metric['count'] += 1
            metric['total_time'] += duration
            metric['min_time'] = min(metric['min_time'], duration)
            metric['max_time'] = max(metric['max_time'], duration)
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """获取性能汇总"""
        with self._lock:
            summary = {}
            for operation, metric in self.metrics.items():
                if metric['count'] > 0:
                    summary[operation] = {
                        'count': metric['count'],
                        'avg_time': metric['total_time'] / metric['count'],
                        'min_time': metric['min_time'],
                        'max_time': metric['max_time'],
                        'total_time': metric['total_time']
                    }
            return summary
    
    def print_performance_report(self):
        """打印性能报告"""
        summary = self.get_performance_summary()
        
        if not summary:
            self.logger.info("暂无性能数据")
            return
        
        self.logger.info("=== 性能报告 ===")
        for operation, stats in summary.items():
            self.logger.info(
                f"{operation}: "
                f"执行{stats['count']}次, "
                f"平均{stats['avg_time']:.2f}s, "
                f"范围[{stats['min_time']:.2f}s - {stats['max_time']:.2f}s]"
            )


def timing_decorator(monitor: PerformanceMonitor):
    """性能监控装饰器"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                monitor.record_timing(func.__name__, duration)
        
        return wrapper
    return decorator


class ResourceCleaner(LoggerMixin):
    """资源清理器"""
    
    def __init__(self, temp_dirs: List[str] = None):
        """
        初始化资源清理器
        
        Args:
            temp_dirs: 临时目录列表
        """
        self.temp_dirs = temp_dirs or []
        self.temp_files = []
        self._cleanup_on_exit = True
        
        # 注册退出时清理
        import atexit
        atexit.register(self.cleanup_all)
    
    def add_temp_file(self, file_path: str):
        """添加临时文件到清理列表"""
        if file_path not in self.temp_files:
            self.temp_files.append(file_path)
    
    def add_temp_dir(self, dir_path: str):
        """添加临时目录到清理列表"""
        if dir_path not in self.temp_dirs:
            self.temp_dirs.append(dir_path)
    
    def cleanup_temp_files(self) -> int:
        """清理临时文件"""
        cleaned_count = 0
        
        for file_path in self.temp_files[:]:  # 使用副本遍历
            try:
                if os.path.exists(file_path):
                    os.unlink(file_path)
                    cleaned_count += 1
                self.temp_files.remove(file_path)
            except Exception as e:
                self.logger.warning(f"清理临时文件失败 {file_path}: {e}")
        
        if cleaned_count > 0:
            self.logger.debug(f"清理了 {cleaned_count} 个临时文件")
        
        return cleaned_count
    
    def cleanup_temp_dirs(self) -> int:
        """清理临时目录"""
        import shutil
        cleaned_count = 0
        
        for dir_path in self.temp_dirs[:]:  # 使用副本遍历
            try:
                if os.path.exists(dir_path) and os.path.isdir(dir_path):
                    shutil.rmtree(dir_path)
                    cleaned_count += 1
                self.temp_dirs.remove(dir_path)
            except Exception as e:
                self.logger.warning(f"清理临时目录失败 {dir_path}: {e}")
        
        if cleaned_count > 0:
            self.logger.debug(f"清理了 {cleaned_count} 个临时目录")
        
        return cleaned_count
    
    def cleanup_old_files(self, directory: str, max_age_hours: int = 24) -> int:
        """清理旧文件"""
        if not os.path.exists(directory):
            return 0
        
        cleaned_count = 0
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        try:
            for filename in os.listdir(directory):
                file_path = os.path.join(directory, filename)
                
                try:
                    file_stat = os.stat(file_path)
                    file_age = current_time - file_stat.st_mtime
                    
                    if file_age > max_age_seconds:
                        if os.path.isfile(file_path):
                            os.unlink(file_path)
                            cleaned_count += 1
                        elif os.path.isdir(file_path):
                            import shutil
                            shutil.rmtree(file_path)
                            cleaned_count += 1
                            
                except Exception as e:
                    self.logger.warning(f"清理旧文件失败 {file_path}: {e}")
        
        except Exception as e:
            self.logger.warning(f"访问目录失败 {directory}: {e}")
        
        if cleaned_count > 0:
            self.logger.info(f"清理了 {cleaned_count} 个超过{max_age_hours}小时的旧文件")
        
        return cleaned_count
    
    def get_disk_usage(self, path: str = ".") -> Dict[str, float]:
        """获取磁盘使用情况"""
        try:
            import shutil
            total, used, free = shutil.disk_usage(path)
            
            return {
                'total_gb': total / (1024**3),
                'used_gb': used / (1024**3),
                'free_gb': free / (1024**3),
                'usage_percent': (used / total) * 100
            }
        except Exception as e:
            self.logger.warning(f"获取磁盘使用情况失败: {e}")
            return {'total_gb': 0, 'used_gb': 0, 'free_gb': 0, 'usage_percent': 0}
    
    def cleanup_all(self):
        """清理所有资源"""
        if not self._cleanup_on_exit:
            return
        
        total_cleaned = 0
        total_cleaned += self.cleanup_temp_files()
        total_cleaned += self.cleanup_temp_dirs()
        
        if total_cleaned > 0:
            self.logger.info(f"程序退出时清理了 {total_cleaned} 个资源")
    
    def disable_exit_cleanup(self):
        """禁用退出时清理"""
        self._cleanup_on_exit = False


class AsyncTaskManager(LoggerMixin):
    """异步任务管理器"""
    
    def __init__(self, max_concurrent: int = 5):
        """
        初始化异步任务管理器
        
        Args:
            max_concurrent: 最大并发数
        """
        self.max_concurrent = max_concurrent
        self.semaphore = None
        self.active_tasks = set()
        self._lock = threading.Lock()
    
    async def get_semaphore(self):
        """获取信号量"""
        if self.semaphore is None:
            import asyncio
            self.semaphore = asyncio.Semaphore(self.max_concurrent)
        return self.semaphore
    
    async def run_with_limit(self, coro):
        """使用并发限制运行协程"""
        semaphore = await self.get_semaphore()
        
        async with semaphore:
            task_id = id(coro)
            
            with self._lock:
                self.active_tasks.add(task_id)
            
            try:
                result = await coro
                return result
            finally:
                with self._lock:
                    self.active_tasks.discard(task_id)
    
    def get_active_task_count(self) -> int:
        """获取活跃任务数量"""
        with self._lock:
            return len(self.active_tasks)


# 全局性能监控实例
performance_monitor = PerformanceMonitor()
memory_manager = MemoryManager()
resource_cleaner = ResourceCleaner()


def optimize_imports():
    """优化导入，延迟加载大模块"""
    # 这个函数可以在需要时调用来优化导入
    pass


def setup_performance_monitoring(config: Dict[str, Any]):
    """设置性能监控"""
    # 根据配置调整性能参数
    memory_limit = config.get('performance', {}).get('memory_limit_mb', 2048)
    memory_manager.max_memory_bytes = memory_limit * 1024 * 1024
    
    # 添加临时目录到清理器
    temp_dir = config.get('storage', {}).get('temp_dir')
    if temp_dir:
        resource_cleaner.add_temp_dir(temp_dir)
    
    # 启用性能监控
    memory_manager.logger.info(f"性能监控已启用，内存限制: {memory_limit}MB")


if __name__ == "__main__":
    # 性能监控工具测试
    print("测试性能监控工具...")
    
    # 测试内存管理
    memory_usage = memory_manager.get_memory_usage()
    print(f"当前内存使用: {memory_usage}")
    
    # 测试性能监控
    @timing_decorator(performance_monitor)
    def test_function():
        time.sleep(0.1)
        return "测试完成"
    
    # 运行测试函数
    for _ in range(3):
        test_function()
    
    # 显示性能报告
    performance_monitor.print_performance_report()
    
    # 测试资源清理
    disk_usage = resource_cleaner.get_disk_usage()
    print(f"磁盘使用情况: {disk_usage}")
    
    print("性能监控工具测试完成")