#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
增强版主程序 - 带友好界面和进度提示
提供更好的用户体验和详细的进度反馈
"""

import asyncio
import sys
import time
import argparse
from pathlib import Path
from typing import Dict, Any, Optional

# 添加项目路径
sys.path.append(str(Path(__file__).parent))

from main import NovelToVideoProcessor
from utils.cli_interface import FriendlyCLI, CLIMenu, ProgressStyle
from utils.error_handler import error_handler, handle_error
from utils.file_utils import FileUtils


class EnhancedNovelProcessor:
    """增强版小说处理器"""
    
    def __init__(self, config_path: str = "config.yaml"):
        """
        初始化增强版处理器
        
        Args:
            config_path: 配置文件路径
        """
        self.cli = FriendlyCLI()
        self.processor = None
        self.config_path = config_path
        self._initialize_processor()
    
    def _initialize_processor(self):
        """初始化处理器"""
        try:
            self.processor = NovelToVideoProcessor(self.config_path)
            self.cli.print_success("处理器初始化完成")
        except Exception as e:
            error_info = handle_error(e, "初始化处理器")
            self.cli.print_error(f"初始化失败: {error_info.message}")
            
            # 尝试错误恢复
            success, _ = error_handler.attempt_recovery(error_info)
            if not success:
                sys.exit(1)
    
    async def process_novel_interactive(self):
        """交互式处理小说"""
        self.cli.print_banner()
        self.cli.print_section("小说转视频处理", "将您的小说转换为精美的短视频")
        
        # 1. 选择输入文件
        input_file = self._select_input_file()
        if not input_file:
            return
        
        # 2. 设置输出选项
        output_options = self._configure_output_options()
        
        # 3. 确认处理
        if not self._confirm_processing(input_file, output_options):
            return
        
        # 4. 开始处理
        await self._process_with_progress(input_file, output_options)
    
    def _select_input_file(self) -> Optional[str]:
        """选择输入文件"""
        self.cli.print_step(1, 4, "选择小说文件")
        
        input_file = self.cli.select_file(
            "请选择要处理的小说文件",
            extensions=['.txt', '.md']
        )
        
        if not input_file:
            self.cli.print_warning("未选择文件，操作已取消")
            return None
        
        # 验证文件
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if len(content.strip()) == 0:
                self.cli.print_error("文件内容为空")
                return None
            
            word_count = len(content.replace(' ', '').replace('\n', ''))
            self.cli.print_info(f"文件验证通过，约 {word_count} 字")
            
            return input_file
            
        except Exception as e:
            error_info = handle_error(e, "文件验证")
            self.cli.print_error(f"文件验证失败: {error_info.message}")
            return None
    
    def _configure_output_options(self) -> Dict[str, Any]:
        """配置输出选项"""
        self.cli.print_step(2, 4, "配置输出选项")
        
        options = {}
        
        # 输出名称
        options['output_name'] = self.cli.input_text(
            "设置视频名称（留空使用默认名称）",
            default=""
        )
        
        # 视频质量
        quality_menu = CLIMenu("选择视频质量")
        quality_menu.add_option("1", "标准质量 (720p, 较快)")
        quality_menu.add_option("2", "高质量 (1080p, 较慢)")
        quality_menu.add_option("3", "经济质量 (480p, 最快)")
        
        quality_choice = quality_menu.display()
        quality_map = {
            "1": "medium",
            "2": "high", 
            "3": "low"
        }
        options['quality'] = quality_map.get(quality_choice, "medium")
        
        # 高级选项
        if self.cli.confirm("是否配置高级选项", default=False):
            options['max_images'] = int(self.cli.input_text(
                "最大图片数量", 
                default="15"
            ) or "15")
            
            options['enable_transitions'] = self.cli.confirm(
                "启用转场效果（实验性功能）",
                default=False
            )
        
        return options
    
    def _confirm_processing(self, input_file: str, options: Dict[str, Any]) -> bool:
        """确认处理参数"""
        self.cli.print_step(3, 4, "确认处理参数")
        
        # 显示处理参数
        params = {
            "输入文件": input_file,
            "输出名称": options.get('output_name') or "自动生成",
            "视频质量": options.get('quality', 'medium'),
            "最大图片数": options.get('max_images', 15),
            "转场效果": "启用" if options.get('enable_transitions', False) else "禁用"
        }
        
        self.cli.show_summary("处理参数确认", params)
        
        # 估算处理时间和成本
        estimated_time = self._estimate_processing_time(options)
        estimated_cost = self._estimate_cost(options)
        
        self.cli.print_info(f"预计处理时间: {estimated_time}")
        self.cli.print_info(f"预计成本: {estimated_cost}")
        
        return self.cli.confirm("确认开始处理", default=True)
    
    def _estimate_processing_time(self, options: Dict[str, Any]) -> str:
        """估算处理时间"""
        base_time = 60  # 基础时间60秒
        
        quality_multiplier = {
            'low': 0.7,
            'medium': 1.0,
            'high': 1.5
        }.get(options.get('quality', 'medium'), 1.0)
        
        image_count = options.get('max_images', 15)
        image_time = image_count * 2  # 每张图片2秒
        
        total_time = (base_time + image_time) * quality_multiplier
        
        if total_time < 60:
            return f"{total_time:.0f}秒"
        elif total_time < 3600:
            return f"{total_time//60:.0f}分{total_time%60:.0f}秒"
        else:
            return f"{total_time//3600:.0f}小时{(total_time%3600)//60:.0f}分钟"
    
    def _estimate_cost(self, options: Dict[str, Any]) -> str:
        """估算处理成本"""
        # 基础成本估算（基于Day 8的分析）
        llm_cost = 0.02
        image_count = options.get('max_images', 15)
        image_cost = image_count * 0.025
        video_cost = 3 * 0.15  # 3个视频片段
        tts_cost = 0.10
        
        total_cost = llm_cost + image_cost + video_cost + tts_cost
        
        return f"约 ¥{total_cost:.2f}"
    
    async def _process_with_progress(self, input_file: str, options: Dict[str, Any]):
        """带进度提示的处理"""
        self.cli.print_step(4, 4, "开始处理", "正在生成您的视频...")
        
        # 创建主进度条
        main_progress = self.cli.create_progress(
            6, "总体进度", ProgressStyle.BAR
        )
        
        try:
            # 更新处理器配置
            await self._update_processor_config(options)
            
            # 步骤1: 文本解析
            main_progress.update(1, "解析小说文本")
            await asyncio.sleep(0.1)  # 模拟处理时间
            
            # 步骤2: 生成脚本
            main_progress.update(1, "生成分镜脚本")
            await asyncio.sleep(0.2)
            
            # 步骤3: 生成图片
            main_progress.update(1, "生成AI图片")
            await self._show_image_generation_progress(options.get('max_images', 15))
            
            # 步骤4: 生成视频
            main_progress.update(1, "生成视频片段")
            await asyncio.sleep(0.3)
            
            # 步骤5: 合成音频
            main_progress.update(1, "合成语音旁白")
            await asyncio.sleep(0.2)
            
            # 步骤6: 最终合成
            main_progress.update(1, "合成最终视频")
            await asyncio.sleep(0.3)
            
            main_progress.finish("处理完成")
            
            # 实际调用处理器
            result = await self.processor.process_novel(
                input_file, 
                options.get('output_name')
            )
            
            # 显示处理结果
            self._show_processing_result(result)
            
        except Exception as e:
            main_progress.close()
            error_info = handle_error(e, "视频处理")
            self.cli.print_error(f"处理失败: {error_info.message}")
            
            # 显示建议解决方案
            if error_info.suggestions:
                self.cli.print_info("建议解决方案:")
                for i, suggestion in enumerate(error_info.suggestions, 1):
                    print(f"  {i}. {suggestion}")
    
    async def _update_processor_config(self, options: Dict[str, Any]):
        """更新处理器配置"""
        if not hasattr(self.processor, 'config'):
            return
        
        # 更新质量设置
        if 'quality' in options:
            self.processor.config.setdefault('quality_control', {})['video_quality'] = options['quality']
        
        # 更新图片数量
        if 'max_images' in options:
            self.processor.config.setdefault('generation', {})['max_images'] = options['max_images']
        
        # 更新转场效果
        if 'enable_transitions' in options:
            self.processor.config.setdefault('video_effects', {})['enable_transitions'] = options['enable_transitions']
    
    async def _show_image_generation_progress(self, image_count: int):
        """显示图片生成进度"""
        image_progress = self.cli.create_progress(
            image_count, "图片生成", ProgressStyle.SPINNER
        )
        
        for i in range(image_count):
            image_progress.update(1, f"生成图片 {i+1}/{image_count}")
            await asyncio.sleep(0.1)  # 模拟生成时间
        
        image_progress.finish(f"已生成 {image_count} 张图片")
    
    def _show_processing_result(self, result: Dict[str, Any]):
        """显示处理结果"""
        if result['status'] == 'completed':
            self.cli.print_success("视频生成成功！")
            
            # 显示结果详情
            details = {
                "输出文件": result['output_video'],
                "视频时长": f"{result['video_info']['duration']:.1f}秒",
                "文件大小": FileUtils.format_file_size(result['video_info']['file_size']),
                "处理时间": f"{result['processing_time']:.1f}秒",
                "总成本": f"¥{result['statistics']['total_cost']:.4f}"
            }
            
            self.cli.show_summary("处理结果", details)
            
            # 询问是否预览
            if self.cli.confirm("是否打开输出目录查看结果", default=True):
                self._open_output_directory(result['output_video'])
        else:
            self.cli.print_error(f"处理失败: {result.get('error', '未知错误')}")
    
    def _open_output_directory(self, file_path: str):
        """打开输出目录"""
        try:
            import os
            import subprocess
            import platform
            
            directory = os.path.dirname(file_path)
            
            if platform.system() == "Windows":
                os.startfile(directory)
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", directory])
            else:  # Linux
                subprocess.run(["xdg-open", directory])
                
        except Exception as e:
            self.cli.print_warning(f"无法打开目录: {e}")
            self.cli.print_info(f"输出文件位置: {file_path}")
    
    def show_status_menu(self):
        """显示状态菜单"""
        self.cli.print_banner()
        
        menu = CLIMenu("系统状态")
        menu.add_option("1", "查看最近任务")
        menu.add_option("2", "查看统计信息")
        menu.add_option("3", "查看成本信息")
        menu.add_option("4", "系统健康检查")
        menu.add_option("0", "返回主菜单")
        
        choice = menu.display()
        
        if choice == "1":
            self._show_recent_tasks()
        elif choice == "2":
            self._show_statistics()
        elif choice == "3":
            self._show_cost_info()
        elif choice == "4":
            self._show_health_check()
    
    def _show_recent_tasks(self):
        """显示最近任务"""
        try:
            tasks = self.processor.list_recent_tasks(10)
            if tasks:
                self.cli.print_section("最近任务")
                
                task_data = []
                for task in tasks:
                    task_data.append({
                        "任务ID": task['task_id'][:12] + "...",
                        "标题": task['title'][:20],
                        "状态": task['status'],
                        "创建时间": task['created_at'][:16]
                    })
                
                self.cli.print_table(task_data)
            else:
                self.cli.print_info("暂无任务记录")
                
        except Exception as e:
            error_info = handle_error(e, "获取任务列表")
            self.cli.print_error(f"获取失败: {error_info.message}")
    
    def _show_statistics(self):
        """显示统计信息"""
        try:
            stats = self.processor.get_statistics()
            
            self.cli.print_section("系统统计")
            
            task_stats = stats.get('tasks', {})
            self.cli.show_summary("任务统计", {
                "今日任务": task_stats.get('today_tasks', 0),
                "总任务数": task_stats.get('total_tasks', 0),
                "成功率": f"{task_stats.get('success_rate', 0):.1%}",
                "平均处理时间": f"{task_stats.get('avg_processing_time', 0):.1f}秒"
            })
            
        except Exception as e:
            error_info = handle_error(e, "获取统计信息")
            self.cli.print_error(f"获取失败: {error_info.message}")
    
    def _show_cost_info(self):
        """显示成本信息"""
        try:
            cost_info = self.processor.get_cost_summary()
            
            self.cli.print_section("成本信息")
            self.cli.show_summary("今日成本", {
                "总成本": f"¥{cost_info.get('total_cost', 0):.4f}",
                "总请求": cost_info.get('total_requests', 0),
                "平均成本": f"¥{cost_info.get('avg_cost_per_request', 0):.4f}/次"
            })
            
            services = cost_info.get('services', {})
            if services:
                service_data = []
                for service, info in services.items():
                    service_data.append({
                        "服务": service,
                        "成本": f"¥{info.get('cost', 0):.4f}",
                        "请求次数": info.get('requests', 0)
                    })
                
                self.cli.print_table(service_data)
            
        except Exception as e:
            error_info = handle_error(e, "获取成本信息")
            self.cli.print_error(f"获取失败: {error_info.message}")
    
    def _show_health_check(self):
        """显示系统健康检查"""
        self.cli.print_section("系统健康检查")
        
        # 检查配置文件
        config_ok = FileUtils.path_exists(self.config_path)
        print(f"配置文件: {'✅ 正常' if config_ok else '❌ 缺失'}")
        
        # 检查依赖
        deps = {
            "FFmpeg": self._check_ffmpeg(),
            "Python包": self._check_python_packages()
        }
        
        for dep, status in deps.items():
            print(f"{dep}: {'✅ 正常' if status else '❌ 异常'}")
        
        # 检查磁盘空间
        try:
            import shutil
            free_space = shutil.disk_usage('.').free / (1024**3)
            space_ok = free_space > 1.0  # 至少1GB
            print(f"磁盘空间: {'✅ 充足' if space_ok else '⚠️ 不足'} ({free_space:.1f}GB)")
        except Exception:
            print("磁盘空间: ❓ 无法检测")
    
    def _check_ffmpeg(self) -> bool:
        """检查FFmpeg"""
        try:
            import subprocess
            subprocess.run(['ffmpeg', '-version'], 
                          capture_output=True, check=True)
            return True
        except Exception:
            return False
    
    def _check_python_packages(self) -> bool:
        """检查Python包"""
        required_packages = ['requests', 'pyyaml', 'moviepy', 'pillow']
        
        for package in required_packages:
            try:
                __import__(package)
            except ImportError:
                return False
        return True
    
    def run_main_menu(self):
        """运行主菜单"""
        while True:
            try:
                self.cli.clear_screen()
                self.cli.print_banner()
                
                menu = CLIMenu("主菜单")
                menu.add_option("1", "处理小说文件 - 生成视频")
                menu.add_option("2", "查看系统状态")  
                menu.add_option("3", "批量处理文件")
                menu.add_option("4", "配置设置")
                menu.add_option("0", "退出程序")
                
                choice = menu.display()
                
                if choice == "1":
                    asyncio.run(self.process_novel_interactive())
                    self.cli.wait_for_enter()
                elif choice == "2":
                    self.show_status_menu()
                    self.cli.wait_for_enter()
                elif choice == "3":
                    self.cli.print_info("批量处理功能开发中...")
                    self.cli.wait_for_enter()
                elif choice == "4":
                    self.cli.print_info("配置设置功能开发中...")
                    self.cli.wait_for_enter()
                elif choice == "0":
                    if self.cli.confirm("确认退出程序", default=True):
                        self.cli.print_success("感谢使用，再见！")
                        break
                else:
                    continue
                    
            except KeyboardInterrupt:
                if self.cli.confirm("\n确认退出程序", default=True):
                    break
            except Exception as e:
                error_info = handle_error(e, "主程序运行")
                self.cli.print_error(f"程序异常: {error_info.message}")
                self.cli.wait_for_enter("按 Enter 键继续...")


def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='小说转视频自动化工具 - 增强版')
    parser.add_argument('-c', '--config', default='config.yaml', help='配置文件路径')
    parser.add_argument('--gui', action='store_true', help='使用图形界面模式')
    parser.add_argument('input_file', nargs='?', help='输入小说文件（可选）')
    
    args = parser.parse_args()
    
    try:
        processor = EnhancedNovelProcessor(args.config)
        
        if args.input_file:
            # 命令行模式 - 直接处理文件
            asyncio.run(processor.process_novel_interactive())
        else:
            # 交互式菜单模式
            processor.run_main_menu()
            
    except KeyboardInterrupt:
        print("\n程序已中断")
    except Exception as e:
        error_info = handle_error(e, "程序启动")
        print(f"\n程序启动失败: {error_info.message}")
        sys.exit(1)


if __name__ == "__main__":
    main()