#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
小说转视频自动化工具 - 主程序
将小说txt文件转换为短视频的完整流程
"""

import asyncio
import sys
import time
import uuid
import os
from pathlib import Path
from typing import Dict, Any, Optional

# 设置环境变量解决Windows下的编码问题
os.environ['PYTHONIOENCODING'] = 'utf-8'

# 添加项目路径
sys.path.append(str(Path(__file__).parent))

from utils.logger import setup_logger, get_logger
from utils.file_utils import FileUtils, load_config
from utils.database import DatabaseManager
from utils.api_utils import cost_tracker
from utils.performance import (
    memory_manager, performance_monitor, resource_cleaner,
    timing_decorator, setup_performance_monitoring
)

from processors.parser import TextParser
from processors.llm_client import LLMClient
from processors.narration_generator import NarrationGenerator
from processors.shot_planner import ShotPlanner
from processors.image_gen import ImageGenerator
from processors.video_gen import VideoGenerator
from processors.tts_client import TTSClient
from processors.video_editor import VideoEditor


class NovelToVideoProcessor:
    """小说转视频处理器"""
    
    def __init__(self, config_path: str = "config.yaml"):
        """
        初始化处理器
        
        Args:
            config_path: 配置文件路径
        """
        # 加载配置
        self.config = load_config(config_path)
        
        # 设置性能监控
        setup_performance_monitoring(self.config)
        
        # 设置日志
        log_config = self.config.get('logging', {})
        self.logger = setup_logger(
            name="auto_movie",
            log_level=log_config.get('level', 'INFO'),
            log_file=log_config.get('log_file', './logs/app.log'),
            max_file_size=log_config.get('max_file_size', '10MB'),
            backup_count=log_config.get('backup_count', 5)
        )
        
        # 初始化数据库
        db_path = self.config.get('storage', {}).get('database_path', './data/database.db')
        self.db = DatabaseManager(db_path)
        
        # 延迟初始化处理模块（按需加载）
        self._text_parser = None
        self._llm_client = None
        self._narration_generator = None
        self._shot_planner = None
        self._image_generator = None
        self._video_generator = None
        self._tts_client = None
        self._video_editor = None
        
        self.logger.info("小说转视频处理器初始化完成")
    
    @property
    def text_parser(self):
        """延迟加载文本解析器"""
        if self._text_parser is None:
            self._text_parser = TextParser(self.config)
        return self._text_parser
    
    @property
    def llm_client(self):
        """延迟加载LLM客户端"""
        if self._llm_client is None:
            self._llm_client = LLMClient(self.config)
        return self._llm_client
    
    @property
    def narration_generator(self):
        """延迟加载口播文案生成器"""
        if self._narration_generator is None:
            self._narration_generator = NarrationGenerator(self.llm_client, self.config)
        return self._narration_generator
    
    @property
    def shot_planner(self):
        """延迟加载智能分镜决策器"""
        if self._shot_planner is None:
            self._shot_planner = ShotPlanner(self.llm_client, self.config)
        return self._shot_planner
    
    @property
    def image_generator(self):
        """延迟加载图片生成器"""
        if self._image_generator is None:
            self._image_generator = ImageGenerator(self.config)
        return self._image_generator
    
    @property
    def video_generator(self):
        """延迟加载视频生成器"""
        if self._video_generator is None:
            self._video_generator = VideoGenerator(self.config)
        return self._video_generator
    
    @property
    def tts_client(self):
        """延迟加载TTS客户端"""
        if self._tts_client is None:
            self._tts_client = TTSClient(self.config)
        return self._tts_client
    
    @property
    def video_editor(self):
        """延迟加载视频编辑器"""
        if self._video_editor is None:
            self._video_editor = VideoEditor(self.config)
        return self._video_editor
    
    @timing_decorator(performance_monitor)
    async def process_novel(self, input_file: str, output_name: Optional[str] = None) -> Dict[str, Any]:
        """
        处理单个小说文件
        
        Args:
            input_file: 输入小说文件路径
            output_name: 输出视频名称 (可选)
            
        Returns:
            处理结果
        """
        # 生成任务ID
        task_id = f"task_{int(time.time())}_{str(uuid.uuid4())[:8]}"
        
        try:
            self.logger.info(f"开始处理小说: {input_file} (任务ID: {task_id})")
            start_time = time.time()
            
            # 验证输入文件
            if not FileUtils.path_exists(input_file):
                raise FileNotFoundError(f"输入文件不存在: {input_file}")
            
            # 检查内存状态
            memory_usage = memory_manager.get_memory_usage()
            self.logger.info(f"初始内存使用: {memory_usage['rss_mb']:.1f}MB")
            
            # 使用内存限制上下文
            with memory_manager.memory_limit_context():
                # 1. 文本解析
                self.logger.info("步骤 1/6: 文本解析")
                self.db.create_task(task_id, "文本解析", input_file)
                self.db.update_task_status(task_id, "processing")
                
                text_result = self.text_parser.parse(input_file)
                
                # 检查内存压力
                if memory_manager.check_memory_pressure():
                    memory_manager.force_gc()
            
            self.db.save_text_parsing(
                task_id=task_id,
                original_content=f"文件: {input_file}",
                parsed_content=text_result['content'],
                word_count=text_result['word_count'],
                chapters_found=text_result['chapters_found'],
                processing_time=1.0
            )
            
            self.logger.info(f"文本解析完成: {text_result['word_count']}字, {text_result['chapters_found']}章")
            
            # 2. 生成口播文案
            self.logger.info("步骤 2/7: 生成口播文案")
            target_duration = self.config.get('generation', {}).get('final_duration_target', 180)
            
            narration_result = await self.narration_generator.generate_narration(
                text_result['content'], 
                target_duration,
                text_result.get('title', '小说视频')
            )
            
            self.logger.info(f"口播文案生成完成: {narration_result['word_count']}字, 预估{narration_result['estimated_duration']}秒")
            
            # 3. 智能分镜决策
            self.logger.info("步骤 3/7: 智能分镜决策")
            script_result = await self.shot_planner.plan_shots(narration_result, target_duration)
            
            self.logger.info(f"分镜脚本生成完成: {len(script_result['shots'])}个分镜, 总时长{script_result['total_duration']}秒")
            
            # 4. 生成完整TTS音频
            self.logger.info("步骤 4/7: 生成完整配音")
            audio_result = await self.tts_client.synthesize_long_speech(
                narration_result['narration'], 
                target_duration, 
                task_id
            )
            
            self.logger.info(f"配音生成完成: {audio_result['duration']:.1f}秒")
            
            # 5. 并行生成图片内容
            self.logger.info("步骤 5/7: 生成分镜图片")
            image_results = await self.image_generator.generate_images_from_script(script_result, task_id)
            
            self.logger.info(f"图片生成完成: {len(image_results)}张")
            
            # 6. 生成动态视频片段（仅前3个分镜）
            self.logger.info("步骤 6/7: 生成动态视频片段")
            dynamic_shots = [shot for shot in script_result['shots'] if shot.get('type') == 'dynamic']
            dynamic_images = image_results[:len(dynamic_shots)]
            
            video_results = await self.video_generator.generate_videos_from_images(
                dynamic_images, dynamic_shots, task_id
            )
            
            self.logger.info(f"动态视频生成完成: {len(video_results)}个片段")
            
            # 7. 合成最终视频（基于新流程）
            self.logger.info("步骤 7/7: 合成最终视频")
            final_video = await self.video_editor.compose_video_with_narration(
                image_results, video_results, audio_result, script_result, narration_result, task_id
            )
            
            self.logger.info(f"视频合成完成: {final_video['file_path']}")
            
            # 8. 后处理和统计
            self.logger.info("完成处理和清理")
            
            # 清理临时文件
            self.video_editor.cleanup_temp_files(task_id)
            resource_cleaner.cleanup_temp_files()
            
            # 更新任务状态
            self.db.update_task_status(task_id, "completed")
            
            # 打印性能报告
            performance_monitor.print_performance_report()
            
            # 计算总耗时和成本
            total_time = time.time() - start_time
            cost_summary = cost_tracker.get_summary()
            
            # 构建最终结果
            result = {
                'task_id': task_id,
                'input_file': input_file,
                'output_video': final_video['file_path'],
                'title': text_result['title'],
                'processing_time': total_time,
                'video_info': {
                    'duration': final_video['duration'],
                    'resolution': final_video['resolution'],
                    'file_size': final_video['file_size'],
                    'fps': final_video['fps']
                },
                'statistics': {
                    'text_words': text_result['word_count'],
                    'images_generated': len(image_results),
                    'videos_generated': len(video_results),
                    'audio_duration': audio_result['duration'],
                    'total_cost': cost_summary['costs']['total']
                },
                'status': 'completed'
            }
            
            self.logger.info(f"处理成功完成: {total_time:.1f}秒, 总成本: ¥{cost_summary['costs']['total']:.4f}")
            return result
            
        except Exception as e:
            self.logger.error(f"处理失败: {e}")
            self.db.update_task_status(task_id, "failed", str(e))
            
            return {
                'task_id': task_id,
                'input_file': input_file,
                'error': str(e),
                'status': 'failed'
            }
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务状态信息
        """
        return self.db.get_task(task_id)
    
    def list_recent_tasks(self, limit: int = 10) -> list:
        """
        列出最近的任务
        
        Args:
            limit: 限制数量
            
        Returns:
            任务列表
        """
        return self.db.list_tasks(limit=limit)
    
    def get_cost_summary(self, date: Optional[str] = None) -> Dict[str, Any]:
        """
        获取成本汇总
        
        Args:
            date: 日期 (YYYY-MM-DD格式，默认今日)
            
        Returns:
            成本汇总
        """
        return self.db.get_daily_cost_summary(date)
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取整体统计信息
        
        Returns:
            统计信息
        """
        task_stats = self.db.get_task_statistics()
        cost_summary = self.get_cost_summary()
        
        return {
            'tasks': task_stats,
            'costs': cost_summary,
            'system': {
                'version': '1.0.0',
                'uptime': 'N/A'
            }
        }


async def main():
    """主函数"""
    import argparse
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='小说转视频自动化工具')
    parser.add_argument('input_file', help='输入小说文件路径')
    parser.add_argument('-c', '--config', default='config.yaml', help='配置文件路径')
    parser.add_argument('-o', '--output', help='输出视频名称')
    parser.add_argument('--status', help='查询任务状态 (提供任务ID)')
    parser.add_argument('--list', action='store_true', help='列出最近任务')
    parser.add_argument('--stats', action='store_true', help='显示统计信息')
    parser.add_argument('--cost', help='显示成本信息 (可选日期 YYYY-MM-DD)')
    
    args = parser.parse_args()
    
    processor = None
    try:
        # 初始化处理器
        processor = NovelToVideoProcessor(args.config)
        
        # 处理不同的命令
        if args.status:
            # 查询任务状态
            task_info = processor.get_task_status(args.status)
            if task_info:
                print(f"任务状态: {task_info['status']}")
                print(f"标题: {task_info['title']}")
                print(f"创建时间: {task_info['created_at']}")
                if task_info['error_message']:
                    print(f"错误信息: {task_info['error_message']}")
            else:
                print(f"任务不存在: {args.status}")
            
        elif args.list:
            # 列出最近任务
            tasks = processor.list_recent_tasks(10)
            print(f"最近 {len(tasks)} 个任务:")
            for task in tasks:
                print(f"  {task['task_id']}: {task['title']} ({task['status']})")
        
        elif args.stats:
            # 显示统计信息
            stats = processor.get_statistics()
            print("系统统计:")
            print(f"  今日任务: {stats['tasks']['today_tasks']}")
            print(f"  平均处理时间: {stats['tasks']['avg_processing_time']:.1f}秒")
            print(f"  今日成本: ¥{stats['costs']['total_cost']:.4f}")
        
        elif args.cost is not None:
            # 显示成本信息
            cost_info = processor.get_cost_summary(args.cost if args.cost else None)
            print(f"日期: {cost_info['date']}")
            print(f"总成本: ¥{cost_info['total_cost']:.4f}")
            print(f"总请求: {cost_info['total_requests']}")
            for service, info in cost_info['services'].items():
                print(f"  {service}: ¥{info['cost']:.4f} ({info['requests']}次)")
        
        else:
            # 处理小说文件
            result = await processor.process_novel(args.input_file, args.output)
            
            if result['status'] == 'completed':
                print("处理成功完成!")
                print(f"输出视频: {result['output_video']}")
                print(f"处理时间: {result['processing_time']:.1f}秒")
                print(f"视频时长: {result['video_info']['duration']:.1f}秒")
                print(f"视频大小: {FileUtils.format_file_size(result['video_info']['file_size'])}")
                print(f"总成本: ¥{result['statistics']['total_cost']:.4f}")
            else:
                print("处理失败!")
                print(f"错误: {result['error']}")
                return 1
        
        return 0
        
    except KeyboardInterrupt:
        print("\n用户中断")
        return 1
    except Exception as e:
        print(f"程序异常: {e}")
        return 1
    finally:
        # 清理资源
        if processor:
            # 关闭所有API客户端的会话
            try:
                await _cleanup_processor(processor)
            except Exception as cleanup_error:
                print(f"资源清理时出错: {cleanup_error}")


async def _cleanup_processor(processor):
    """清理处理器的资源"""
    cleanup_tasks = []
    
    # 收集所有需要清理的API客户端
    for attr_name in ['_llm_client', '_image_generator', '_video_generator', '_tts_client']:
        client = getattr(processor, attr_name, None)
        if client and hasattr(client, 'api_utils'):
            cleanup_tasks.append(client.api_utils.close_session_async())
    
    # 并行清理所有会话
    if cleanup_tasks:
        await asyncio.gather(*cleanup_tasks, return_exceptions=True)


def create_sample_config():
    """创建示例配置文件"""
    if not FileUtils.path_exists("config.yaml"):
        print("未找到配置文件，请先复制 config.yaml.example 为 config.yaml 并配置API密钥")
        return False
    return True


if __name__ == "__main__":
    # 检查配置文件
    if not create_sample_config():
        sys.exit(1)
    
    # 运行主程序
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except Exception as e:
        print(f"程序启动失败: {e}")
        sys.exit(1)