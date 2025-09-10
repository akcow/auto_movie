#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
命令行界面模块
提供友好的用户交互界面和进度显示
"""

import os
import sys
import time
import threading
from typing import Any, Dict, List, Optional, Union, Callable
from dataclasses import dataclass
from enum import Enum
import argparse

from .logger import LoggerMixin


class ProgressStyle(Enum):
    """进度条样式"""
    BAR = "bar"
    SPINNER = "spinner" 
    DOTS = "dots"
    PERCENTAGE = "percentage"


@dataclass
class CLITheme:
    """CLI主题配置"""
    primary_color: str = "cyan"
    success_color: str = "green"
    warning_color: str = "yellow"
    error_color: str = "red"
    info_color: str = "blue"
    
    # 字符样式
    progress_char: str = "█"
    empty_char: str = "░"
    spinner_chars: List[str] = None
    
    def __post_init__(self):
        if self.spinner_chars is None:
            self.spinner_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


class ProgressBar(LoggerMixin):
    """进度条组件"""
    
    def __init__(self, 
                 total: int,
                 title: str = "进度",
                 style: ProgressStyle = ProgressStyle.BAR,
                 width: int = 50,
                 theme: CLITheme = None):
        """
        初始化进度条
        
        Args:
            total: 总数
            title: 标题
            style: 进度条样式
            width: 进度条宽度
            theme: 主题配置
        """
        self.total = total
        self.current = 0
        self.title = title
        self.style = style
        self.width = width
        self.theme = theme or CLITheme()
        
        self._start_time = time.time()
        self._last_update = 0
        self._is_finished = False
        self._lock = threading.Lock()
        
        # 动画相关
        self._spinner_index = 0
        self._dots_count = 0
    
    def update(self, amount: int = 1, description: str = ""):
        """
        更新进度
        
        Args:
            amount: 增加的数量
            description: 当前操作描述
        """
        with self._lock:
            self.current = min(self.current + amount, self.total)
            self._render(description)
    
    def set_progress(self, current: int, description: str = ""):
        """
        设置当前进度
        
        Args:
            current: 当前进度值
            description: 当前操作描述
        """
        with self._lock:
            self.current = min(max(current, 0), self.total)
            self._render(description)
    
    def _render(self, description: str = ""):
        """渲染进度条"""
        if self._is_finished:
            return
        
        current_time = time.time()
        if current_time - self._last_update < 0.1:  # 限制更新频率
            return
        
        self._last_update = current_time
        
        if self.style == ProgressStyle.BAR:
            self._render_bar(description)
        elif self.style == ProgressStyle.SPINNER:
            self._render_spinner(description)
        elif self.style == ProgressStyle.DOTS:
            self._render_dots(description)
        elif self.style == ProgressStyle.PERCENTAGE:
            self._render_percentage(description)
    
    def _render_bar(self, description: str = ""):
        """渲染条形进度条"""
        percentage = self.current / self.total if self.total > 0 else 0
        filled_width = int(self.width * percentage)
        
        bar = (self.theme.progress_char * filled_width + 
               self.theme.empty_char * (self.width - filled_width))
        
        # 计算估计剩余时间
        elapsed_time = time.time() - self._start_time
        if self.current > 0 and percentage < 1.0:
            eta = elapsed_time * (1 - percentage) / percentage
            eta_str = self._format_time(eta)
        else:
            eta_str = "--:--"
        
        progress_line = f"\r{self.title}: [{bar}] {percentage:.1%} ({self.current}/{self.total}) ETA: {eta_str}"
        
        if description:
            progress_line += f" - {description}"
        
        # 确保行不会太长
        progress_line = progress_line[:120]
        
        print(progress_line, end="", flush=True)
    
    def _render_spinner(self, description: str = ""):
        """渲染旋转进度指示"""
        spinner = self.theme.spinner_chars[self._spinner_index]
        self._spinner_index = (self._spinner_index + 1) % len(self.theme.spinner_chars)
        
        percentage = self.current / self.total if self.total > 0 else 0
        progress_line = f"\r{spinner} {self.title}: {percentage:.1%} ({self.current}/{self.total})"
        
        if description:
            progress_line += f" - {description}"
        
        print(progress_line, end="", flush=True)
    
    def _render_dots(self, description: str = ""):
        """渲染点状进度指示"""
        self._dots_count = (self._dots_count + 1) % 4
        dots = "." * self._dots_count + " " * (3 - self._dots_count)
        
        percentage = self.current / self.total if self.total > 0 else 0
        progress_line = f"\r{self.title}{dots} {percentage:.1%} ({self.current}/{self.total})"
        
        if description:
            progress_line += f" - {description}"
        
        print(progress_line, end="", flush=True)
    
    def _render_percentage(self, description: str = ""):
        """渲染百分比进度指示"""
        percentage = self.current / self.total if self.total > 0 else 0
        progress_line = f"\r{self.title}: {percentage:.1%} ({self.current}/{self.total})"
        
        if description:
            progress_line += f" - {description}"
        
        print(progress_line, end="", flush=True)
    
    def finish(self, message: str = "完成"):
        """完成进度条"""
        with self._lock:
            if self._is_finished:
                return
            
            self._is_finished = True
            self.current = self.total
            
            elapsed_time = time.time() - self._start_time
            elapsed_str = self._format_time(elapsed_time)
            
            if self.style == ProgressStyle.BAR:
                bar = self.theme.progress_char * self.width
                print(f"\r{self.title}: [{bar}] 100% ({self.total}/{self.total}) {message} - 用时: {elapsed_str}")
            else:
                print(f"\r{self.title}: 100% ({self.total}/{self.total}) {message} - 用时: {elapsed_str}")
    
    def _format_time(self, seconds: float) -> str:
        """格式化时间显示"""
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            return f"{seconds//60:.0f}m{seconds%60:.0f}s"
        else:
            return f"{seconds//3600:.0f}h{(seconds%3600)//60:.0f}m"
    
    def close(self):
        """关闭进度条"""
        if not self._is_finished:
            self.finish()
        print()  # 换行


class CLIMenu:
    """CLI菜单组件"""
    
    def __init__(self, title: str = "请选择操作", theme: CLITheme = None):
        """
        初始化菜单
        
        Args:
            title: 菜单标题
            theme: 主题配置
        """
        self.title = title
        self.theme = theme or CLITheme()
        self.options = []
    
    def add_option(self, key: str, description: str, action: Callable = None):
        """
        添加菜单选项
        
        Args:
            key: 选项键
            description: 选项描述
            action: 选项对应的动作
        """
        self.options.append({
            'key': key,
            'description': description,
            'action': action
        })
    
    def display(self) -> str:
        """
        显示菜单并获取用户选择
        
        Returns:
            用户选择的选项键
        """
        print(f"\n{'='*50}")
        print(f"{self.title}")
        print(f"{'='*50}")
        
        for option in self.options:
            print(f"  {option['key']}. {option['description']}")
        
        print(f"{'='*50}")
        
        while True:
            try:
                choice = input("请输入选项编号: ").strip()
                
                # 查找匹配的选项
                for option in self.options:
                    if option['key'] == choice:
                        return choice
                
                print("无效选项，请重新输入")
                
            except KeyboardInterrupt:
                print("\n操作已取消")
                return ""
            except EOFError:
                return ""
    
    def execute(self, choice: str) -> Any:
        """
        执行选定的动作
        
        Args:
            choice: 选择的选项键
            
        Returns:
            动作执行结果
        """
        for option in self.options:
            if option['key'] == choice and option['action']:
                return option['action']()
        return None


class FriendlyCLI(LoggerMixin):
    """友好的CLI界面"""
    
    def __init__(self, app_name: str = "小说转视频工具", theme: CLITheme = None):
        """
        初始化CLI界面
        
        Args:
            app_name: 应用名称
            theme: 主题配置
        """
        self.app_name = app_name
        self.theme = theme or CLITheme()
        self.current_progress = None
    
    def print_banner(self):
        """打印应用横幅"""
        banner = f"""
╔══════════════════════════════════════════════════════════════╗
║                    {self.app_name}                    ║
║                                                              ║
║  将小说文本自动转换为精美短视频                                 ║
║  支持AI智能分镜、图片生成、语音合成、视频编辑                   ║
╚══════════════════════════════════════════════════════════════╝
        """
        print(banner)
    
    def print_section(self, title: str, content: str = ""):
        """
        打印章节标题
        
        Args:
            title: 章节标题
            content: 章节内容
        """
        print(f"\n{'─' * 60}")
        print(f"📋 {title}")
        print(f"{'─' * 60}")
        if content:
            print(content)
    
    def print_step(self, step: int, total: int, title: str, description: str = ""):
        """
        打印执行步骤
        
        Args:
            step: 当前步骤
            total: 总步骤数
            title: 步骤标题
            description: 步骤描述
        """
        print(f"\n🔄 步骤 {step}/{total}: {title}")
        if description:
            print(f"   {description}")
    
    def print_success(self, message: str):
        """打印成功消息"""
        print(f"\n✅ {message}")
    
    def print_warning(self, message: str):
        """打印警告消息"""
        print(f"\n⚠️  {message}")
    
    def print_error(self, message: str):
        """打印错误消息"""
        print(f"\n❌ {message}")
    
    def print_info(self, message: str):
        """打印信息消息"""
        print(f"\nℹ️  {message}")
    
    def confirm(self, message: str, default: bool = True) -> bool:
        """
        获取用户确认
        
        Args:
            message: 确认消息
            default: 默认值
            
        Returns:
            用户确认结果
        """
        suffix = " [Y/n]: " if default else " [y/N]: "
        
        while True:
            try:
                response = input(f"❓ {message}{suffix}").strip().lower()
                
                if not response:
                    return default
                elif response in ['y', 'yes', '是', '确定']:
                    return True
                elif response in ['n', 'no', '否', '取消']:
                    return False
                else:
                    print("请输入 y/yes 或 n/no")
                    
            except KeyboardInterrupt:
                print("\n操作已取消")
                return False
            except EOFError:
                return default
    
    def input_text(self, prompt: str, default: str = "", required: bool = False) -> str:
        """
        获取用户文本输入
        
        Args:
            prompt: 提示信息
            default: 默认值
            required: 是否必填
            
        Returns:
            用户输入的文本
        """
        suffix = f" [{default}]: " if default else ": "
        
        while True:
            try:
                response = input(f"📝 {prompt}{suffix}").strip()
                
                if not response and default:
                    return default
                elif not response and required:
                    print("此项为必填项，请输入内容")
                    continue
                else:
                    return response
                    
            except KeyboardInterrupt:
                print("\n操作已取消")
                return ""
            except EOFError:
                return default
    
    def select_file(self, prompt: str = "请选择文件", extensions: List[str] = None) -> str:
        """
        文件选择对话框
        
        Args:
            prompt: 提示信息
            extensions: 允许的文件扩展名
            
        Returns:
            选择的文件路径
        """
        print(f"\n📁 {prompt}")
        
        if extensions:
            print(f"支持的文件格式: {', '.join(extensions)}")
        
        while True:
            try:
                file_path = input("请输入文件路径: ").strip()
                
                if not file_path:
                    print("请输入文件路径")
                    continue
                
                # 去除引号
                file_path = file_path.strip('"\'')
                
                if not os.path.exists(file_path):
                    print("文件不存在，请重新输入")
                    continue
                
                if not os.path.isfile(file_path):
                    print("请输入文件路径，不是目录")
                    continue
                
                # 检查文件扩展名
                if extensions:
                    file_ext = os.path.splitext(file_path)[1].lower()
                    if file_ext not in extensions:
                        print(f"不支持的文件格式，支持: {', '.join(extensions)}")
                        continue
                
                return file_path
                
            except KeyboardInterrupt:
                print("\n操作已取消")
                return ""
            except EOFError:
                return ""
    
    def create_progress(self, total: int, title: str = "处理进度", 
                       style: ProgressStyle = ProgressStyle.BAR) -> ProgressBar:
        """
        创建进度条
        
        Args:
            total: 总数
            title: 标题
            style: 样式
            
        Returns:
            进度条对象
        """
        self.current_progress = ProgressBar(total, title, style, theme=self.theme)
        return self.current_progress
    
    def print_table(self, data: List[Dict[str, Any]], headers: List[str] = None):
        """
        打印表格
        
        Args:
            data: 表格数据
            headers: 表头
        """
        if not data:
            print("暂无数据")
            return
        
        if not headers:
            headers = list(data[0].keys())
        
        # 计算列宽
        col_widths = {}
        for header in headers:
            col_widths[header] = max(
                len(str(header)),
                max(len(str(row.get(header, ""))) for row in data) if data else 0
            )
        
        # 打印表头
        header_line = "│ " + " │ ".join(
            str(header).ljust(col_widths[header]) for header in headers
        ) + " │"
        
        separator = "├" + "┼".join("─" * (col_widths[header] + 2) for header in headers) + "┤"
        top_line = "┌" + "┬".join("─" * (col_widths[header] + 2) for header in headers) + "┐"
        bottom_line = "└" + "┴".join("─" * (col_widths[header] + 2) for header in headers) + "┘"
        
        print(top_line)
        print(header_line)
        print(separator)
        
        # 打印数据行
        for row in data:
            row_line = "│ " + " │ ".join(
                str(row.get(header, "")).ljust(col_widths[header]) for header in headers
            ) + " │"
            print(row_line)
        
        print(bottom_line)
    
    def show_summary(self, title: str, data: Dict[str, Any]):
        """
        显示汇总信息
        
        Args:
            title: 标题
            data: 汇总数据
        """
        print(f"\n📊 {title}")
        print("─" * 40)
        
        for key, value in data.items():
            print(f"  {key}: {value}")
    
    def wait_for_enter(self, message: str = "按 Enter 键继续..."):
        """
        等待用户按回车
        
        Args:
            message: 提示消息
        """
        try:
            input(f"\n{message}")
        except KeyboardInterrupt:
            pass
        except EOFError:
            pass
    
    def clear_screen(self):
        """清屏"""
        os.system('cls' if os.name == 'nt' else 'clear')


def create_main_cli() -> FriendlyCLI:
    """创建主CLI界面"""
    return FriendlyCLI("小说转视频自动化工具")


if __name__ == "__main__":
    # CLI界面测试
    cli = create_main_cli()
    
    # 显示横幅
    cli.print_banner()
    
    # 测试各种组件
    cli.print_section("功能测试", "测试各种CLI组件")
    
    # 测试消息显示
    cli.print_info("这是一个信息消息")
    cli.print_success("这是一个成功消息")
    cli.print_warning("这是一个警告消息")
    cli.print_error("这是一个错误消息")
    
    # 测试进度条
    progress = cli.create_progress(10, "测试进度")
    for i in range(10):
        time.sleep(0.2)
        progress.update(1, f"处理项目 {i+1}")
    progress.finish("测试完成")
    
    # 测试表格
    test_data = [
        {"名称": "测试1", "状态": "完成", "耗时": "2.5s"},
        {"名称": "测试2", "状态": "进行中", "耗时": "1.2s"},
        {"名称": "测试3", "状态": "等待", "耗时": "0s"},
    ]
    
    cli.print_section("测试结果")
    cli.print_table(test_data)
    
    print("\nCLI界面测试完成")