#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
API调用工具模块
提供API调用的封装、重试、错误处理等功能
"""

import asyncio
import time
import json
from typing import Dict, Any, Optional, Callable, Union
import aiohttp
import requests
from tenacity import (
    retry, 
    stop_after_attempt, 
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)
from .logger import LoggerMixin, get_logger


class APIError(Exception):
    """API调用错误"""
    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[Dict] = None):
        self.message = message
        self.status_code = status_code
        self.response_data = response_data
        super().__init__(message)


class RateLimitError(APIError):
    """API限流错误"""
    pass


class APIUtils(LoggerMixin):
    """API调用工具类"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化API工具
        
        Args:
            config: 配置字典
        """
        self.config = config
        self.api_settings = config.get('api_settings', {})
        self.max_retries = self.api_settings.get('max_retries', 3)
        self.request_timeout = self.api_settings.get('request_timeout', 30)
        self.rate_limit_per_minute = self.api_settings.get('rate_limit_per_minute', 60)
        
        # 请求计数器 (用于限流)
        self._request_times = []
        
        # 会话对象
        self._session = None
        self._session_closed = False
    
    def _check_rate_limit(self) -> None:
        """检查请求频率限制"""
        current_time = time.time()
        
        # 清理1分钟前的请求记录
        self._request_times = [
            req_time for req_time in self._request_times 
            if current_time - req_time < 60
        ]
        
        # 检查是否超过频率限制
        if len(self._request_times) >= self.rate_limit_per_minute:
            sleep_time = 60 - (current_time - self._request_times[0])
            if sleep_time > 0:
                self.logger.warning(f"API调用频率限制，等待 {sleep_time:.1f} 秒")
                time.sleep(sleep_time)
                return self._check_rate_limit()
        
        # 记录本次请求时间
        self._request_times.append(current_time)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((APIError, requests.RequestException)),
        before_sleep=before_sleep_log(get_logger(), 20)
    )
    def make_request(
        self, 
        method: str, 
        url: str, 
        headers: Optional[Dict] = None,
        params: Optional[Dict] = None,
        data: Optional[Union[Dict, str]] = None,
        json_data: Optional[Dict] = None,
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        发起HTTP请求
        
        Args:
            method: 请求方法 (GET, POST, etc.)
            url: 请求URL
            headers: 请求头
            params: URL参数
            data: 请求数据
            json_data: JSON数据
            timeout: 超时时间
            
        Returns:
            响应数据
        """
        # 检查频率限制
        self._check_rate_limit()
        
        # 设置默认超时
        if timeout is None:
            timeout = self.request_timeout
        
        # 设置默认请求头
        if headers is None:
            headers = {}
        
        if 'User-Agent' not in headers:
            headers['User-Agent'] = 'auto_movie/1.0'
        
        try:
            self.logger.debug(f"发起 {method} 请求: {url}")
            
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                data=data,
                json=json_data,
                timeout=timeout
            )
            
            # 检查响应状态
            if response.status_code == 429:
                raise RateLimitError(
                    "API调用频率过高",
                    status_code=response.status_code
                )
            
            if not response.ok:
                error_msg = f"API请求失败: {response.status_code} - {response.text}"
                raise APIError(
                    error_msg, 
                    status_code=response.status_code,
                    response_data=response.json() if response.headers.get('content-type', '').startswith('application/json') else None
                )
            
            # 解析响应
            if response.headers.get('content-type', '').startswith('application/json'):
                return response.json()
            else:
                return {'content': response.content, 'text': response.text}
                
        except requests.RequestException as e:
            error_msg = f"网络请求异常: {str(e)}"
            self.logger.error(error_msg)
            raise APIError(error_msg)
        except json.JSONDecodeError as e:
            error_msg = f"JSON解析失败: {str(e)}"
            self.logger.error(error_msg)
            raise APIError(error_msg)
    
    async def make_async_request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict] = None,
        params: Optional[Dict] = None,
        data: Optional[Union[Dict, str]] = None,
        json_data: Optional[Dict] = None,
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        发起异步HTTP请求
        
        Args:
            method: 请求方法
            url: 请求URL
            headers: 请求头
            params: URL参数
            data: 请求数据
            json_data: JSON数据
            timeout: 超时时间
            
        Returns:
            响应数据
        """
        if timeout is None:
            timeout = self.request_timeout
        
        if headers is None:
            headers = {}
        
        if 'User-Agent' not in headers:
            headers['User-Agent'] = 'auto_movie/1.0'
        
        if self._session is None:
            self._session = aiohttp.ClientSession()
        
        try:
            self.logger.debug(f"发起异步 {method} 请求: {url}")
            
            async with self._session.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                data=data,
                json=json_data,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:
                
                if response.status == 429:
                    raise RateLimitError(
                        "API调用频率过高",
                        status_code=response.status
                    )
                
                if response.status >= 400:
                    error_text = await response.text()
                    error_msg = f"API请求失败: {response.status} - {error_text}"
                    raise APIError(
                        error_msg,
                        status_code=response.status
                    )
                
                # 解析响应
                content_type = response.headers.get('content-type', '')
                if content_type.startswith('application/json'):
                    return await response.json()
                else:
                    content = await response.read()
                    # 只有在不是二进制内容时才尝试解码为文本
                    try:
                        if content_type.startswith(('image/', 'video/', 'audio/', 'application/octet-stream')):
                            # 二进制内容，不解码
                            return {'content': content, 'content_type': content_type}
                        else:
                            # 文本内容，尝试解码
                            text = content.decode('utf-8')
                            return {'content': content, 'text': text, 'content_type': content_type}
                    except UnicodeDecodeError:
                        # 解码失败，当作二进制处理
                        return {'content': content, 'content_type': content_type}
                    
        except aiohttp.ClientError as e:
            error_msg = f"异步网络请求异常: {str(e)}"
            self.logger.error(error_msg)
            raise APIError(error_msg)
    
    def close_session(self):
        """关闭异步会话"""
        if self._session and not self._session_closed:
            try:
                loop = asyncio.get_running_loop()
                # 创建关闭任务
                task = asyncio.create_task(self._session.close())
                self._session_closed = True
                self._session = None
                return task
            except RuntimeError:
                # 没有运行的事件循环
                self._session_closed = True
                self._session = None
                return None
                
    async def close_session_async(self):
        """异步关闭会话"""
        if self._session and not self._session_closed:
            await self._session.close()
            self._session_closed = True
            self._session = None
    
    def download_file(
        self, 
        url: str, 
        file_path: str,
        headers: Optional[Dict] = None,
        chunk_size: int = 8192
    ) -> None:
        """
        下载文件
        
        Args:
            url: 文件URL
            file_path: 保存路径
            headers: 请求头
            chunk_size: 块大小
        """
        from .file_utils import FileUtils
        
        try:
            self.logger.info(f"开始下载文件: {url}")
            
            response = requests.get(
                url, 
                headers=headers, 
                timeout=self.request_timeout,
                stream=True
            )
            response.raise_for_status()
            
            # 确保目录存在
            FileUtils.ensure_dir(FileUtils(file_path).parent)
            
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
            
            self.logger.info(f"文件下载完成: {file_path}")
            
        except Exception as e:
            error_msg = f"文件下载失败: {str(e)}"
            self.logger.error(error_msg)
            raise APIError(error_msg)
    
    async def download_file_async(
        self,
        url: str,
        file_path: str,
        headers: Optional[Dict] = None,
        chunk_size: int = 8192
    ) -> None:
        """
        异步下载文件
        
        Args:
            url: 文件URL
            file_path: 保存路径
            headers: 请求头
            chunk_size: 块大小
        """
        from .file_utils import FileUtils
        
        if self._session is None:
            self._session = aiohttp.ClientSession()
        
        try:
            self.logger.info(f"开始异步下载文件: {url}")
            
            async with self._session.get(url, headers=headers) as response:
                response.raise_for_status()
                
                # 确保目录存在
                FileUtils.ensure_dir(Path(file_path).parent)
                
                with open(file_path, 'wb') as f:
                    async for chunk in response.content.iter_chunked(chunk_size):
                        f.write(chunk)
            
            self.logger.info(f"文件下载完成: {file_path}")
            
        except Exception as e:
            error_msg = f"异步文件下载失败: {str(e)}"
            self.logger.error(error_msg)
            raise APIError(error_msg)
    
    def __del__(self):
        """析构函数，清理资源"""
        try:
            if self._session and not self._session_closed:
                # 标记会话需要关闭，但不在析构函数中执行异步操作
                self._session_closed = True
        except:
            pass  # 忽略析构时的任何错误


class CostTracker:
    """API成本跟踪器"""
    
    def __init__(self):
        self.costs = {
            'llm': 0.0,
            'text2image': 0.0, 
            'image2video': 0.0,
            'tts': 0.0,
            'total': 0.0
        }
        self.request_counts = {
            'llm': 0,
            'text2image': 0,
            'image2video': 0, 
            'tts': 0
        }
    
    def add_cost(self, service: str, cost: float, count: int = 1):
        """
        添加成本记录
        
        Args:
            service: 服务名称
            cost: 成本金额
            count: 请求次数
        """
        if service in self.costs:
            self.costs[service] += cost
            self.costs['total'] += cost
            self.request_counts[service] += count
    
    def get_summary(self) -> Dict[str, Any]:
        """获取成本汇总"""
        return {
            'costs': self.costs.copy(),
            'request_counts': self.request_counts.copy()
        }
    
    def reset(self):
        """重置成本统计"""
        for key in self.costs:
            self.costs[key] = 0.0
        for key in self.request_counts:
            self.request_counts[key] = 0


# 全局成本跟踪器实例
cost_tracker = CostTracker()


if __name__ == "__main__":
    # 测试API工具
    config = {
        'api_settings': {
            'max_retries': 3,
            'request_timeout': 10,
            'rate_limit_per_minute': 30
        }
    }
    
    api = APIUtils(config)
    
    # 测试GET请求
    try:
        response = api.make_request('GET', 'https://httpbin.org/get')
        print("GET请求成功:", response)
    except Exception as e:
        print("GET请求失败:", e)
    
    # 测试成本跟踪
    cost_tracker.add_cost('llm', 0.05, 1)
    cost_tracker.add_cost('text2image', 0.25, 10)
    print("成本汇总:", cost_tracker.get_summary())