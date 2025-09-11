#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
错误处理模块
提供友好的错误信息、异常处理和恢复机制
"""

import sys
import traceback
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
import json

from .logger import LoggerMixin


class ErrorLevel(Enum):
    """错误级别"""
    INFO = "信息"
    WARNING = "警告"  
    ERROR = "错误"
    CRITICAL = "严重错误"


class ErrorCategory(Enum):
    """错误类别"""
    SYSTEM = "系统错误"
    NETWORK = "网络错误"
    API = "API错误"
    FILE = "文件错误"
    CONFIG = "配置错误"
    DATA = "数据错误"
    USER = "用户错误"


@dataclass
class ErrorInfo:
    """错误信息"""
    level: ErrorLevel
    category: ErrorCategory
    code: str
    message: str
    details: str = ""
    suggestions: List[str] = None
    technical_info: str = ""
    timestamp: float = 0.0
    
    def __post_init__(self):
        if self.suggestions is None:
            self.suggestions = []
        
        if self.timestamp == 0.0:
            import time
            self.timestamp = time.time()


class FriendlyErrorHandler(LoggerMixin):
    """友好错误处理器"""
    
    def __init__(self):
        self.error_registry = self._build_error_registry()
        self.recovery_handlers = {}
        
    def _build_error_registry(self) -> Dict[str, ErrorInfo]:
        """构建错误信息注册表"""
        return {
            # 文件错误
            "FILE_NOT_FOUND": ErrorInfo(
                level=ErrorLevel.ERROR,
                category=ErrorCategory.FILE,
                code="FILE_NOT_FOUND",
                message="找不到指定的文件",
                suggestions=[
                    "请检查文件路径是否正确",
                    "确认文件是否存在",
                    "检查文件权限设置"
                ]
            ),
            
            "FILE_READ_ERROR": ErrorInfo(
                level=ErrorLevel.ERROR,
                category=ErrorCategory.FILE,
                code="FILE_READ_ERROR", 
                message="文件读取失败",
                suggestions=[
                    "检查文件权限",
                    "确认文件未被其他程序占用",
                    "检查磁盘空间是否充足"
                ]
            ),
            
            "FILE_ENCODING_ERROR": ErrorInfo(
                level=ErrorLevel.WARNING,
                category=ErrorCategory.FILE,
                code="FILE_ENCODING_ERROR",
                message="文件编码识别失败",
                suggestions=[
                    "尝试使用UTF-8编码保存文件",
                    "确认文件不包含特殊字符",
                    "可以尝试转换文件编码格式"
                ]
            ),
            
            # API错误
            "API_KEY_INVALID": ErrorInfo(
                level=ErrorLevel.CRITICAL,
                category=ErrorCategory.API,
                code="API_KEY_INVALID",
                message="API密钥无效或已过期",
                suggestions=[
                    "检查config.yaml中的API密钥配置",
                    "确认密钥没有过期",
                    "重新生成API密钥",
                    "查看火山引擎控制台确认服务状态"
                ]
            ),
            
            "API_QUOTA_EXCEEDED": ErrorInfo(
                level=ErrorLevel.ERROR,
                category=ErrorCategory.API,
                code="API_QUOTA_EXCEEDED",
                message="API调用配额已用完",
                suggestions=[
                    "等待配额重置（通常每日重置）",
                    "升级API服务套餐",
                    "优化调用频率",
                    "检查费用余额是否充足"
                ]
            ),
            
            "API_RATE_LIMIT": ErrorInfo(
                level=ErrorLevel.WARNING,
                category=ErrorCategory.API,
                code="API_RATE_LIMIT",
                message="API调用频率过高",
                suggestions=[
                    "程序会自动重试，请稍等",
                    "可以在配置中调整调用频率",
                    "如频繁出现，联系服务提供商提升限制"
                ]
            ),
            
            # 网络错误
            "NETWORK_TIMEOUT": ErrorInfo(
                level=ErrorLevel.WARNING,
                category=ErrorCategory.NETWORK,
                code="NETWORK_TIMEOUT",
                message="网络连接超时",
                suggestions=[
                    "检查网络连接状态",
                    "尝试稍后重试",
                    "可以增加超时时间设置",
                    "检查防火墙设置"
                ]
            ),
            
            "NETWORK_CONNECTION_ERROR": ErrorInfo(
                level=ErrorLevel.ERROR,
                category=ErrorCategory.NETWORK,
                code="NETWORK_CONNECTION_ERROR",
                message="无法连接到服务器",
                suggestions=[
                    "检查网络连接",
                    "确认服务器地址正确",
                    "检查代理设置",
                    "稍后重试"
                ]
            ),
            
            # 配置错误
            "CONFIG_MISSING": ErrorInfo(
                level=ErrorLevel.CRITICAL,
                category=ErrorCategory.CONFIG,
                code="CONFIG_MISSING",
                message="缺少必要的配置文件",
                suggestions=[
                    "复制config.yaml.example为config.yaml",
                    "填写API密钥等必要配置",
                    "参考README文档进行配置"
                ]
            ),
            
            "CONFIG_INVALID": ErrorInfo(
                level=ErrorLevel.ERROR,
                category=ErrorCategory.CONFIG,
                code="CONFIG_INVALID",
                message="配置文件格式错误",
                suggestions=[
                    "检查YAML语法是否正确",
                    "确认缩进格式",
                    "参考配置文件示例",
                    "使用在线YAML验证工具检查"
                ]
            ),
            
            # 数据错误
            "DATA_FORMAT_ERROR": ErrorInfo(
                level=ErrorLevel.ERROR,
                category=ErrorCategory.DATA,
                code="DATA_FORMAT_ERROR",
                message="数据格式不正确",
                suggestions=[
                    "检查输入数据格式",
                    "确认数据完整性",
                    "参考格式要求",
                    "尝试重新生成数据"
                ]
            ),
            
            "DATA_EMPTY": ErrorInfo(
                level=ErrorLevel.WARNING,
                category=ErrorCategory.DATA,
                code="DATA_EMPTY",
                message="输入数据为空",
                suggestions=[
                    "检查输入文件是否包含内容",
                    "确认文件不是空文件",
                    "检查数据生成过程"
                ]
            ),
            
            # 系统错误
            "MEMORY_ERROR": ErrorInfo(
                level=ErrorLevel.CRITICAL,
                category=ErrorCategory.SYSTEM,
                code="MEMORY_ERROR",
                message="内存不足",
                suggestions=[
                    "关闭其他不必要的程序",
                    "减少处理文件大小",
                    "增加虚拟内存设置",
                    "升级系统内存"
                ]
            ),
            
            "DISK_SPACE_ERROR": ErrorInfo(
                level=ErrorLevel.ERROR,
                category=ErrorCategory.SYSTEM,
                code="DISK_SPACE_ERROR",
                message="磁盘空间不足",
                suggestions=[
                    "清理临时文件",
                    "删除不需要的文件",
                    "更换到其他磁盘",
                    "增加存储空间"
                ]
            ),
            
            # 依赖错误
            "DEPENDENCY_MISSING": ErrorInfo(
                level=ErrorLevel.CRITICAL,
                category=ErrorCategory.SYSTEM,
                code="DEPENDENCY_MISSING",
                message="缺少必要的依赖程序",
                suggestions=[
                    "安装FFmpeg并添加到系统PATH",
                    "运行pip install -r requirements.txt",
                    "检查系统依赖是否完整",
                    "参考安装文档"
                ]
            ),
        }
    
    def handle_exception(
        self, 
        exception: Exception, 
        context: str = "",
        user_friendly: bool = True
    ) -> ErrorInfo:
        """
        处理异常并返回友好的错误信息
        
        Args:
            exception: 异常对象
            context: 上下文信息
            user_friendly: 是否返回用户友好信息
            
        Returns:
            错误信息对象
        """
        error_code = self._classify_exception(exception)
        error_info = self.error_registry.get(error_code)
        
        if not error_info:
            # 创建通用错误信息
            error_info = ErrorInfo(
                level=ErrorLevel.ERROR,
                category=ErrorCategory.SYSTEM,
                code="UNKNOWN_ERROR",
                message=f"未知错误: {type(exception).__name__}",
                suggestions=["请联系技术支持", "提供错误详情以便排查"]
            )
        
        # 填充详细信息
        error_info.details = str(exception)
        if context:
            error_info.details = f"{context}: {error_info.details}"
        
        # 添加技术信息（仅在调试模式下）
        if not user_friendly:
            error_info.technical_info = traceback.format_exc()
        
        return error_info
    
    def _classify_exception(self, exception: Exception) -> str:
        """
        根据异常类型和消息分类错误
        
        Args:
            exception: 异常对象
            
        Returns:
            错误代码
        """
        exception_type = type(exception).__name__
        error_message = str(exception).lower()
        
        # 文件相关错误
        if isinstance(exception, FileNotFoundError):
            return "FILE_NOT_FOUND"
        elif isinstance(exception, PermissionError):
            return "FILE_READ_ERROR"
        elif isinstance(exception, UnicodeDecodeError):
            return "FILE_ENCODING_ERROR"
        
        # 网络相关错误
        elif "timeout" in error_message:
            return "NETWORK_TIMEOUT"
        elif "connection" in error_message or "network" in error_message:
            return "NETWORK_CONNECTION_ERROR"
        
        # API相关错误  
        elif "api key" in error_message or "unauthorized" in error_message:
            return "API_KEY_INVALID"
        elif "quota" in error_message or "limit exceeded" in error_message:
            return "API_QUOTA_EXCEEDED"
        elif "rate limit" in error_message or "too many requests" in error_message:
            return "API_RATE_LIMIT"
        
        # 内存错误
        elif isinstance(exception, MemoryError) or "memory" in error_message:
            return "MEMORY_ERROR"
        
        # 磁盘空间错误
        elif "no space" in error_message or "disk full" in error_message:
            return "DISK_SPACE_ERROR"
        
        # 配置错误
        elif "config" in error_message:
            if "not found" in error_message:
                return "CONFIG_MISSING"
            else:
                return "CONFIG_INVALID"
        
        # 数据错误
        elif "json" in error_message or "format" in error_message:
            return "DATA_FORMAT_ERROR"
        elif "empty" in error_message:
            return "DATA_EMPTY"
        
        # 依赖错误
        elif "ffmpeg" in error_message or "command not found" in error_message:
            return "DEPENDENCY_MISSING"
        
        return "UNKNOWN_ERROR"
    
    def format_error_message(self, error_info: ErrorInfo, detailed: bool = False) -> str:
        """
        格式化错误消息
        
        Args:
            error_info: 错误信息
            detailed: 是否显示详细信息
            
        Returns:
            格式化的错误消息
        """
        lines = []
        
        # 错误标题
        level_prefix = {
            ErrorLevel.INFO: "[信息]",
            ErrorLevel.WARNING: "[警告]", 
            ErrorLevel.ERROR: "[错误]",
            ErrorLevel.CRITICAL: "[严重]"
        }.get(error_info.level, "[错误]")
        
        lines.append(f"{level_prefix} {error_info.message}")
        
        # 错误详情
        if detailed and error_info.details:
            lines.append(f"详情: {error_info.details}")
        
        # 建议解决方案
        if error_info.suggestions:
            lines.append("建议解决方案:")
            for i, suggestion in enumerate(error_info.suggestions, 1):
                lines.append(f"  {i}. {suggestion}")
        
        # 技术信息（仅调试模式）
        if detailed and error_info.technical_info:
            lines.append(f"\n技术详情:\n{error_info.technical_info}")
        
        return "\n".join(lines)
    
    def print_error(self, error_info: ErrorInfo, detailed: bool = False):
        """
        打印友好的错误信息
        
        Args:
            error_info: 错误信息
            detailed: 是否显示详细信息
        """
        message = self.format_error_message(error_info, detailed)
        
        # 根据错误级别选择输出方式
        if error_info.level == ErrorLevel.CRITICAL:
            self.logger.critical(message)
        elif error_info.level == ErrorLevel.ERROR:
            self.logger.error(message)
        elif error_info.level == ErrorLevel.WARNING:
            self.logger.warning(message)
        else:
            self.logger.info(message)
        
        # 控制台输出（简化版本）
        print(f"\n{message}\n")
    
    def register_recovery_handler(self, error_code: str, handler: callable):
        """
        注册错误恢复处理器
        
        Args:
            error_code: 错误代码
            handler: 恢复处理函数
        """
        self.recovery_handlers[error_code] = handler
    
    def attempt_recovery(self, error_info: ErrorInfo, *args, **kwargs) -> Tuple[bool, Any]:
        """
        尝试错误恢复
        
        Args:
            error_info: 错误信息
            *args, **kwargs: 恢复函数参数
            
        Returns:
            (是否恢复成功, 恢复结果)
        """
        handler = self.recovery_handlers.get(error_info.code)
        
        if handler:
            try:
                result = handler(*args, **kwargs)
                return True, result
            except Exception as e:
                self.logger.error(f"错误恢复失败: {e}")
                return False, None
        
        return False, None
    
    def create_error_report(self, errors: List[ErrorInfo]) -> Dict[str, Any]:
        """
        创建错误报告
        
        Args:
            errors: 错误信息列表
            
        Returns:
            错误报告
        """
        if not errors:
            return {"status": "success", "errors": []}
        
        error_counts = {}
        for error in errors:
            category = error.category.value
            error_counts[category] = error_counts.get(category, 0) + 1
        
        critical_errors = [e for e in errors if e.level == ErrorLevel.CRITICAL]
        
        return {
            "status": "error" if critical_errors else "warning",
            "total_errors": len(errors),
            "critical_errors": len(critical_errors),
            "error_categories": error_counts,
            "errors": [
                {
                    "code": error.code,
                    "message": error.message,
                    "level": error.level.value,
                    "category": error.category.value,
                    "suggestions": error.suggestions,
                    "timestamp": error.timestamp
                }
                for error in errors
            ]
        }


# 全局错误处理器实例
error_handler = FriendlyErrorHandler()


def handle_error(
    exception: Exception, 
    context: str = "", 
    print_error: bool = True,
    detailed: bool = False
) -> ErrorInfo:
    """
    便捷的错误处理函数
    
    Args:
        exception: 异常对象
        context: 上下文信息
        print_error: 是否打印错误
        detailed: 是否显示详细信息
        
    Returns:
        错误信息对象
    """
    error_info = error_handler.handle_exception(exception, context)
    
    if print_error:
        error_handler.print_error(error_info, detailed)
    
    return error_info


def safe_execute(func, *args, **kwargs) -> Tuple[bool, Any, Optional[ErrorInfo]]:
    """
    安全执行函数，捕获并处理异常
    
    Args:
        func: 要执行的函数
        *args, **kwargs: 函数参数
        
    Returns:
        (是否成功, 结果, 错误信息)
    """
    try:
        result = func(*args, **kwargs)
        return True, result, None
    except Exception as e:
        error_info = handle_error(e, f"执行函数 {func.__name__}")
        return False, None, error_info


if __name__ == "__main__":
    # 错误处理器测试
    print("测试错误处理器...")
    
    # 测试不同类型的错误
    test_exceptions = [
        FileNotFoundError("测试文件不存在"),
        ValueError("Invalid API key"),
        ConnectionError("Network timeout occurred"),
        MemoryError("Out of memory"),
    ]
    
    for i, exception in enumerate(test_exceptions, 1):
        print(f"\n--- 测试 {i}: {type(exception).__name__} ---")
        error_info = handle_error(exception, f"测试场景 {i}")
    
    print("\n错误处理器测试完成")