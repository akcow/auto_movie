#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
批量处理脚本
批量处理多个小说文件，支持并发处理和进度监控
"""

import asyncio
import sys
import time
from pathlib import Path
from typing import List, Dict, Any
import glob

# 添加项目路径
sys.path.append(str(Path(__file__).parent))

from utils.logger import setup_logger
from utils.file_utils import FileUtils
from main import NovelToVideoProcessor


class BatchProcessor:
    """批量处理器"""
    
    def __init__(self, config_path: str = "config.yaml"):
        """
        初始化批量处理器
        
        Args:
            config_path: 配置文件路径
        """
        self.processor = NovelToVideoProcessor(config_path)
        self.logger = setup_logger("batch_processor", log_level="INFO")
        
        # 批处理配置
        self.max_concurrent = 3  # 最大并发数
        self.retry_failed = True  # 是否重试失败的任务
        self.max_retries = 2     # 最大重试次数
    
    async def process_directory(
        self, 
        input_dir: str, 
        output_dir: str = None,
        file_pattern: str = "*.txt"
    ) -> Dict[str, Any]:
        """
        批量处理目录中的文件
        
        Args:
            input_dir: 输入目录
            output_dir: 输出目录 (可选)
            file_pattern: 文件匹配模式
            
        Returns:
            批处理结果
        """
        try:
            self.logger.info(f"开始批量处理目录: {input_dir}")
            start_time = time.time()
            
            # 查找匹配的文件
            input_files = self._find_input_files(input_dir, file_pattern)
            
            if not input_files:
                self.logger.warning(f"在目录 {input_dir} 中未找到匹配的文件")
                return {
                    'total_files': 0,
                    'processed': 0,
                    'succeeded': 0,
                    'failed': 0,
                    'results': []
                }
            
            self.logger.info(f"找到 {len(input_files)} 个文件待处理")
            
            # 批量处理
            results = await self._process_files_concurrent(input_files)
            
            # 统计结果
            total_time = time.time() - start_time
            succeeded = len([r for r in results if r['status'] == 'completed'])
            failed = len(results) - succeeded
            
            summary = {
                'total_files': len(input_files),
                'processed': len(results),
                'succeeded': succeeded,
                'failed': failed,
                'processing_time': total_time,
                'results': results
            }
            
            self.logger.info(f"批量处理完成: {succeeded}/{len(input_files)} 成功, 耗时 {total_time:.1f}秒")
            
            return summary
            
        except Exception as e:
            self.logger.error(f"批量处理失败: {e}")
            raise
    
    def _find_input_files(self, input_dir: str, pattern: str) -> List[str]:
        """查找输入文件"""
        input_path = Path(input_dir)
        
        if not input_path.exists():
            raise FileNotFoundError(f"输入目录不存在: {input_dir}")
        
        if not input_path.is_dir():
            raise ValueError(f"输入路径不是目录: {input_dir}")
        
        # 查找匹配的文件
        files = list(input_path.glob(pattern))
        
        # 过滤文本文件
        valid_files = []
        for file_path in files:
            if file_path.is_file() and file_path.suffix.lower() in ['.txt', '.md']:
                valid_files.append(str(file_path))
        
        return sorted(valid_files)
    
    async def _process_files_concurrent(self, input_files: List[str]) -> List[Dict[str, Any]]:
        """
        并发处理文件
        
        Args:
            input_files: 输入文件列表
            
        Returns:
            处理结果列表
        """
        # 创建信号量控制并发数
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        # 创建处理任务
        tasks = []
        for i, file_path in enumerate(input_files):
            task = self._process_single_file_with_semaphore(
                semaphore, file_path, i + 1, len(input_files)
            )
            tasks.append(task)
        
        # 等待所有任务完成
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常结果
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"处理文件异常 [{input_files[i]}]: {result}")
                processed_results.append({
                    'input_file': input_files[i],
                    'status': 'failed',
                    'error': str(result)
                })
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def _process_single_file_with_semaphore(
        self, 
        semaphore: asyncio.Semaphore,
        file_path: str, 
        current_index: int, 
        total_files: int
    ) -> Dict[str, Any]:
        """
        带信号量的单文件处理
        
        Args:
            semaphore: 信号量
            file_path: 文件路径
            current_index: 当前索引
            total_files: 总文件数
            
        Returns:
            处理结果
        """
        async with semaphore:
            return await self._process_single_file_with_retry(
                file_path, current_index, total_files
            )
    
    async def _process_single_file_with_retry(
        self, 
        file_path: str, 
        current_index: int, 
        total_files: int
    ) -> Dict[str, Any]:
        """
        带重试的单文件处理
        
        Args:
            file_path: 文件路径
            current_index: 当前索引  
            total_files: 总文件数
            
        Returns:
            处理结果
        """
        self.logger.info(f"处理文件 [{current_index}/{total_files}]: {file_path}")
        
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                if attempt > 0:
                    self.logger.info(f"重试处理 [{current_index}/{total_files}] - 第 {attempt} 次")
                
                result = await self.processor.process_novel(file_path)
                
                if result['status'] == 'completed':
                    self.logger.info(f"处理成功 [{current_index}/{total_files}]: {result['output_video']}")
                    return result
                else:
                    last_error = result.get('error', '未知错误')
                    if not self.retry_failed:
                        break
                        
            except Exception as e:
                last_error = str(e)
                self.logger.warning(f"处理失败 [{current_index}/{total_files}] (尝试 {attempt + 1}): {e}")
                
                if not self.retry_failed:
                    break
                
                # 重试前等待一段时间
                if attempt < self.max_retries:
                    await asyncio.sleep(min(2 ** attempt, 10))
        
        # 所有重试都失败了
        self.logger.error(f"处理最终失败 [{current_index}/{total_files}]: {last_error}")
        return {
            'input_file': file_path,
            'status': 'failed',
            'error': last_error,
            'attempts': self.max_retries + 1
        }
    
    def generate_report(self, summary: Dict[str, Any], output_file: str = None) -> str:
        """
        生成处理报告
        
        Args:
            summary: 处理汇总
            output_file: 输出文件 (可选)
            
        Returns:
            报告内容
        """
        report_lines = [
            "=" * 60,
            "批量处理报告",
            "=" * 60,
            f"总文件数: {summary['total_files']}",
            f"已处理: {summary['processed']}",
            f"成功: {summary['succeeded']}",
            f"失败: {summary['failed']}",
            f"成功率: {summary['succeeded']/max(summary['processed'], 1)*100:.1f}%",
            f"总耗时: {summary['processing_time']:.1f}秒",
            "",
            "详细结果:",
            "-" * 60
        ]
        
        # 添加成功的文件
        successful_results = [r for r in summary['results'] if r['status'] == 'completed']
        if successful_results:
            report_lines.append("成功处理的文件:")
            for result in successful_results:
                report_lines.append(f"  ✓ {result['input_file']}")
                report_lines.append(f"    输出: {result['output_video']}")
                report_lines.append(f"    耗时: {result['processing_time']:.1f}秒")
                report_lines.append(f"    成本: ¥{result['statistics']['total_cost']:.4f}")
                report_lines.append("")
        
        # 添加失败的文件
        failed_results = [r for r in summary['results'] if r['status'] == 'failed']
        if failed_results:
            report_lines.append("失败的文件:")
            for result in failed_results:
                report_lines.append(f"  ✗ {result['input_file']}")
                report_lines.append(f"    错误: {result['error']}")
                if 'attempts' in result:
                    report_lines.append(f"    尝试次数: {result['attempts']}")
                report_lines.append("")
        
        # 总成本统计
        total_cost = sum(
            r.get('statistics', {}).get('total_cost', 0) 
            for r in successful_results
        )
        if total_cost > 0:
            report_lines.extend([
                "成本统计:",
                f"  总成本: ¥{total_cost:.4f}",
                f"  平均成本: ¥{total_cost/max(len(successful_results), 1):.4f}",
                ""
            ])
        
        report_lines.append("=" * 60)
        
        report_content = '\n'.join(report_lines)
        
        # 保存报告文件
        if output_file:
            FileUtils.write_text_file(output_file, report_content)
            self.logger.info(f"报告已保存: {output_file}")
        
        return report_content


async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='批量处理小说转视频')
    parser.add_argument('input_dir', help='输入目录路径')
    parser.add_argument('-o', '--output-dir', help='输出目录路径')
    parser.add_argument('-p', '--pattern', default='*.txt', help='文件匹配模式')
    parser.add_argument('-c', '--config', default='config.yaml', help='配置文件路径')
    parser.add_argument('--max-concurrent', type=int, default=3, help='最大并发数')
    parser.add_argument('--no-retry', action='store_true', help='不重试失败的任务')
    parser.add_argument('--max-retries', type=int, default=2, help='最大重试次数')
    parser.add_argument('--report', help='生成报告文件路径')
    
    args = parser.parse_args()
    
    try:
        # 初始化批处理器
        batch_processor = BatchProcessor(args.config)
        batch_processor.max_concurrent = args.max_concurrent
        batch_processor.retry_failed = not args.no_retry
        batch_processor.max_retries = args.max_retries
        
        # 开始批量处理
        summary = await batch_processor.process_directory(
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            file_pattern=args.pattern
        )
        
        # 生成和显示报告
        report_file = args.report or f"batch_report_{int(time.time())}.txt"
        report_content = batch_processor.generate_report(summary, report_file)
        
        print(report_content)
        
        # 根据成功率决定退出代码
        success_rate = summary['succeeded'] / max(summary['processed'], 1)
        return 0 if success_rate > 0.5 else 1
        
    except KeyboardInterrupt:
        print("\n用户中断批量处理")
        return 1
    except Exception as e:
        print(f"批量处理异常: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)