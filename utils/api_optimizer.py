#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
API调用优化模块
提供API调用频率限制、重试机制、批量处理等功能
"""

import asyncio
import time
import threading
from collections import defaultdict, deque
from typing import Any, Callable, Dict, List, Optional, Tuple
from dataclasses import dataclass
import json

from .logger import LoggerMixin


@dataclass
class APICall:
    """API调用记录"""
    service: str
    method: str
    timestamp: float
    duration: Optional[float] = None
    success: bool = True
    error: Optional[str] = None
    retry_count: int = 0


class RateLimiter(LoggerMixin):
    """API调用频率限制器"""
    
    def __init__(self, max_calls_per_minute: int = 60):
        """
        初始化频率限制器
        
        Args:
            max_calls_per_minute: 每分钟最大调用次数
        """
        self.max_calls_per_minute = max_calls_per_minute
        self.call_history = deque()
        self._lock = threading.Lock()
        
        # 每个服务的独立限制
        self.service_limits = {
            'llm': 30,          # LLM每分钟30次
            'image': 60,        # 图片生成每分钟60次
            'video': 20,        # 视频生成每分钟20次
            'tts': 40           # TTS每分钟40次
        }
        
        self.service_history = defaultdict(deque)
    
    async def acquire(self, service: str = 'default') -> bool:
        """
        获取API调用许可
        
        Args:
            service: 服务类型
            
        Returns:
            是否可以调用
        """
        with self._lock:
            current_time = time.time()
            window_start = current_time - 60  # 1分钟窗口
            
            # 清理过期的调用记录
            self._cleanup_expired_calls(window_start)
            
            # 检查全局限制
            if len(self.call_history) >= self.max_calls_per_minute:
                wait_time = self.call_history[0] + 60 - current_time
                if wait_time > 0:
                    self.logger.debug(f"全局API限制，等待 {wait_time:.1f}秒")
                    await asyncio.sleep(wait_time)
                    return await self.acquire(service)
            
            # 检查服务特定限制
            service_limit = self.service_limits.get(service, self.max_calls_per_minute)
            service_calls = self.service_history[service]
            
            if len(service_calls) >= service_limit:
                wait_time = service_calls[0] + 60 - current_time
                if wait_time > 0:
                    self.logger.debug(f"{service}服务限制，等待 {wait_time:.1f}秒")
                    await asyncio.sleep(wait_time)
                    return await self.acquire(service)
            
            # 记录调用
            self.call_history.append(current_time)
            service_calls.append(current_time)
            
            return True
    
    def _cleanup_expired_calls(self, window_start: float):
        """清理过期的调用记录"""
        # 清理全局历史
        while self.call_history and self.call_history[0] < window_start:
            self.call_history.popleft()
        
        # 清理服务历史
        for service_calls in self.service_history.values():
            while service_calls and service_calls[0] < window_start:
                service_calls.popleft()
    
    def get_current_usage(self) -> Dict[str, int]:
        """获取当前API使用情况"""
        with self._lock:
            current_time = time.time()
            window_start = current_time - 60
            self._cleanup_expired_calls(window_start)
            
            usage = {
                'global': len(self.call_history)
            }
            
            for service, calls in self.service_history.items():
                usage[service] = len(calls)
            
            return usage
    
    def get_estimated_wait_time(self, service: str = 'default') -> float:
        """
        估算下次调用需要等待的时间
        
        Args:
            service: 服务类型
            
        Returns:
            等待时间（秒）
        """
        with self._lock:
            current_time = time.time()
            
            # 检查全局限制
            if len(self.call_history) >= self.max_calls_per_minute:
                global_wait = self.call_history[0] + 60 - current_time
            else:
                global_wait = 0
            
            # 检查服务限制
            service_limit = self.service_limits.get(service, self.max_calls_per_minute)
            service_calls = self.service_history[service]
            
            if len(service_calls) >= service_limit:
                service_wait = service_calls[0] + 60 - current_time
            else:
                service_wait = 0
            
            return max(global_wait, service_wait, 0)


class APIRetryManager(LoggerMixin):
    """API重试管理器"""
    
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 30.0):
        """
        初始化重试管理器
        
        Args:
            max_retries: 最大重试次数
            base_delay: 基础延迟时间
            max_delay: 最大延迟时间
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        
        # 不同错误类型的重试策略
        self.retry_strategies = {
            'timeout': {'max_retries': 3, 'backoff_multiplier': 1.5},
            'rate_limit': {'max_retries': 5, 'backoff_multiplier': 2.0},
            'server_error': {'max_retries': 2, 'backoff_multiplier': 1.0},
            'network_error': {'max_retries': 3, 'backoff_multiplier': 1.2}
        }
    
    async def retry_with_backoff(
        self,
        func: Callable,
        *args,
        error_type: str = 'default',
        **kwargs
    ) -> Tuple[Any, bool]:
        """
        使用退避算法重试API调用
        
        Args:
            func: 要调用的函数
            error_type: 错误类型
            *args, **kwargs: 函数参数
            
        Returns:
            (结果, 是否成功)
        """
        strategy = self.retry_strategies.get(error_type, {
            'max_retries': self.max_retries,
            'backoff_multiplier': 2.0
        })
        
        max_retries = strategy['max_retries']
        backoff_multiplier = strategy['backoff_multiplier']
        
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                if attempt > 0:
                    self.logger.info(f"重试成功，尝试次数: {attempt + 1}")
                
                return result, True
                
            except Exception as e:
                last_exception = e
                
                if attempt < max_retries:
                    delay = min(
                        self.base_delay * (backoff_multiplier ** attempt),
                        self.max_delay
                    )
                    
                    self.logger.warning(f"API调用失败 (尝试 {attempt + 1}/{max_retries + 1}): {e}")
                    self.logger.info(f"等待 {delay:.1f}秒后重试")
                    
                    await asyncio.sleep(delay)
                else:
                    self.logger.error(f"重试次数用尽: {e}")
        
        return None, False
    
    def get_error_type(self, exception: Exception) -> str:
        """
        根据异常确定错误类型
        
        Args:
            exception: 异常对象
            
        Returns:
            错误类型
        """
        error_message = str(exception).lower()
        
        if 'timeout' in error_message:
            return 'timeout'
        elif 'rate limit' in error_message or 'too many requests' in error_message:
            return 'rate_limit'
        elif 'server error' in error_message or '500' in error_message:
            return 'server_error'
        elif 'network' in error_message or 'connection' in error_message:
            return 'network_error'
        else:
            return 'default'


class BatchProcessor(LoggerMixin):
    """批量处理器"""
    
    def __init__(self, batch_size: int = 5, max_concurrent: int = 3):
        """
        初始化批量处理器
        
        Args:
            batch_size: 批量大小
            max_concurrent: 最大并发数
        """
        self.batch_size = batch_size
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_batch(
        self,
        items: List[Any],
        processor_func: Callable,
        **kwargs
    ) -> List[Tuple[Any, bool, Optional[str]]]:
        """
        批量处理项目
        
        Args:
            items: 要处理的项目列表
            processor_func: 处理函数
            **kwargs: 额外参数
            
        Returns:
            处理结果列表 [(结果, 是否成功, 错误信息)]
        """
        results = []
        
        # 分批处理
        for i in range(0, len(items), self.batch_size):
            batch = items[i:i + self.batch_size]
            batch_results = await self._process_single_batch(batch, processor_func, **kwargs)
            results.extend(batch_results)
            
            # 批次间延迟
            if i + self.batch_size < len(items):
                await asyncio.sleep(0.1)
        
        return results
    
    async def _process_single_batch(
        self,
        batch: List[Any],
        processor_func: Callable,
        **kwargs
    ) -> List[Tuple[Any, bool, Optional[str]]]:
        """处理单个批次"""
        async def process_item(item):
            async with self.semaphore:
                try:
                    if asyncio.iscoroutinefunction(processor_func):
                        result = await processor_func(item, **kwargs)
                    else:
                        result = processor_func(item, **kwargs)
                    return result, True, None
                except Exception as e:
                    self.logger.warning(f"处理项目失败: {e}")
                    return None, False, str(e)
        
        # 并发处理批次中的项目
        tasks = [process_item(item) for item in batch]
        return await asyncio.gather(*tasks)


class APICallTracker(LoggerMixin):
    """API调用追踪器"""
    
    def __init__(self):
        self.calls = []
        self._lock = threading.Lock()
    
    def record_call(self, call: APICall):
        """记录API调用"""
        with self._lock:
            self.calls.append(call)
            
            # 只保留最近1000次调用
            if len(self.calls) > 1000:
                self.calls = self.calls[-1000:]
    
    def get_statistics(self, time_window_minutes: int = 60) -> Dict[str, Any]:
        """
        获取API调用统计
        
        Args:
            time_window_minutes: 时间窗口（分钟）
            
        Returns:
            统计信息
        """
        with self._lock:
            current_time = time.time()
            window_start = current_time - (time_window_minutes * 60)
            
            # 过滤时间窗口内的调用
            recent_calls = [
                call for call in self.calls
                if call.timestamp >= window_start
            ]
            
            if not recent_calls:
                return {'total_calls': 0, 'success_rate': 0, 'services': {}}
            
            # 计算统计信息
            total_calls = len(recent_calls)
            successful_calls = sum(1 for call in recent_calls if call.success)
            success_rate = successful_calls / total_calls if total_calls > 0 else 0
            
            # 按服务分组统计
            service_stats = defaultdict(lambda: {
                'calls': 0, 'successes': 0, 'avg_duration': 0, 'total_duration': 0
            })
            
            for call in recent_calls:
                stats = service_stats[call.service]
                stats['calls'] += 1
                if call.success:
                    stats['successes'] += 1
                if call.duration is not None:
                    stats['total_duration'] += call.duration
            
            # 计算平均时长
            for service, stats in service_stats.items():
                if stats['calls'] > 0:
                    stats['success_rate'] = stats['successes'] / stats['calls']
                    stats['avg_duration'] = stats['total_duration'] / stats['calls']
                else:
                    stats['success_rate'] = 0
                    stats['avg_duration'] = 0
                
                del stats['total_duration']  # 移除临时字段
            
            return {
                'total_calls': total_calls,
                'successful_calls': successful_calls,
                'success_rate': success_rate,
                'time_window_minutes': time_window_minutes,
                'services': dict(service_stats)
            }
    
    def export_to_file(self, file_path: str):
        """导出调用记录到文件"""
        with self._lock:
            data = []
            for call in self.calls:
                data.append({
                    'service': call.service,
                    'method': call.method,
                    'timestamp': call.timestamp,
                    'duration': call.duration,
                    'success': call.success,
                    'error': call.error,
                    'retry_count': call.retry_count
                })
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"导出 {len(data)} 条API调用记录到 {file_path}")


# 全局实例
rate_limiter = RateLimiter()
retry_manager = APIRetryManager()
batch_processor = BatchProcessor()
call_tracker = APICallTracker()


async def optimized_api_call(
    func: Callable,
    service: str,
    method: str,
    *args,
    **kwargs
) -> Tuple[Any, bool]:
    """
    优化的API调用包装函数
    
    Args:
        func: API调用函数
        service: 服务名称
        method: 方法名称
        *args, **kwargs: 函数参数
        
    Returns:
        (结果, 是否成功)
    """
    # 获取调用许可
    await rate_limiter.acquire(service)
    
    # 记录开始时间
    start_time = time.time()
    
    # 创建调用记录
    call_record = APICall(
        service=service,
        method=method,
        timestamp=start_time
    )
    
    try:
        # 使用重试机制调用
        result, success = await retry_manager.retry_with_backoff(func, *args, **kwargs)
        
        # 更新调用记录
        call_record.duration = time.time() - start_time
        call_record.success = success
        
        if not success:
            call_record.error = "重试次数用尽"
        
        return result, success
        
    except Exception as e:
        # 记录异常
        call_record.duration = time.time() - start_time
        call_record.success = False
        call_record.error = str(e)
        
        return None, False
        
    finally:
        # 记录调用
        call_tracker.record_call(call_record)


if __name__ == "__main__":
    # API优化工具测试
    import asyncio
    
    async def test_api_call():
        """测试API调用"""
        await asyncio.sleep(0.1)
        return "测试结果"
    
    async def main():
        print("测试API优化工具...")
        
        # 测试频率限制
        print("1. 测试频率限制...")
        for i in range(5):
            await rate_limiter.acquire('test')
            print(f"  调用 {i+1} 获得许可")
        
        # 测试优化调用
        print("2. 测试优化调用...")
        result, success = await optimized_api_call(test_api_call, 'test', 'test_method')
        print(f"  调用结果: {result}, 成功: {success}")
        
        # 显示统计
        print("3. 显示统计...")
        stats = call_tracker.get_statistics()
        print(f"  统计: {stats}")
        
        print("API优化工具测试完成")
    
    asyncio.run(main())