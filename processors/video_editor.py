#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
视频编辑模块
负责将生成的图片、视频、音频素材合成为最终的短视频
"""

import os
import asyncio
import time
import json
import subprocess
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).parent.parent))

from utils.logger import LoggerMixin
from utils.file_utils import FileUtils
from utils.database import DatabaseManager


class VideoEditor(LoggerMixin):
    """视频编辑器"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化视频编辑器
        
        Args:
            config: 配置字典
        """
        self.config = config
        self.generation_config = config.get('generation', {})
        self.storage_config = config.get('storage', {})
        
        # 视频参数
        self.output_resolution = self.generation_config.get('output_resolution', '720p')
        self.output_fps = self.generation_config.get('output_fps', 24)
        self.final_duration_min = self.generation_config.get('final_duration_min', 120)
        self.final_duration_max = self.generation_config.get('final_duration_max', 240)
        
        # 存储配置
        self.temp_dir = self.storage_config.get('temp_dir', './data/temp')
        self.output_dir = self.storage_config.get('output_dir', './data/output')
        
        # 确保目录存在
        FileUtils.ensure_dir(self.temp_dir)
        FileUtils.ensure_dir(self.output_dir)
        
        # 数据库
        self.db = DatabaseManager(self.storage_config.get('database_path', './data/database.db'))
        
        # 分辨率映射
        self.resolution_map = {
            '480p': (480, 854),
            '720p': (720, 1280), 
            '1080p': (1080, 1920)
        }
        
        # 字幕样式配置
        subtitle_config = self.config.get('subtitle', {})
        self.subtitle_style = {
            'font_size': subtitle_config.get('font_size', 36),
            'font_family': subtitle_config.get('font_family', 'Arial Black'),
            'font_color': subtitle_config.get('font_color', 'white'),
            'outline_color': subtitle_config.get('outline_color', 'black'),
            'outline_width': subtitle_config.get('outline_width', 2),
            'shadow_color': subtitle_config.get('shadow_color', 'gray'),
            'shadow_offset': subtitle_config.get('shadow_offset', 2),
            'position': subtitle_config.get('position', 'bottom'),
            'margin': subtitle_config.get('margin', 50),
            'alignment': subtitle_config.get('alignment', 'center'),
            'fade_in': subtitle_config.get('fade_in', True),
            'fade_duration': subtitle_config.get('fade_duration', 0.5)
        }
    
    def _safe_decode(self, byte_data: bytes) -> str:
        """安全地解码字节数据，处理编码问题"""
        try:
            return byte_data.decode('utf-8')
        except UnicodeDecodeError:
            try:
                return byte_data.decode('gbk')
            except UnicodeDecodeError:
                return byte_data.decode('utf-8', errors='ignore')
    
    async def compose_video(
        self,
        image_results: List[Dict[str, Any]],
        video_results: List[Dict[str, Any]], 
        audio_result: Dict[str, Any],
        script_data: Dict[str, Any],
        task_id: str
    ) -> Dict[str, Any]:
        """
        合成最终视频
        
        Args:
            image_results: 图片生成结果
            video_results: 视频生成结果
            audio_result: 音频生成结果
            script_data: 脚本数据
            task_id: 任务ID
            
        Returns:
            最终视频信息
        """
        try:
            self.logger.info(f"开始合成视频: {script_data['title']}")
            start_time = time.time()
            
            # 1. 创建视频片段
            video_segments = await self._create_video_segments(
                image_results, video_results, script_data, task_id
            )
            
            # 2. 生成字幕文件
            subtitle_file = await self._create_subtitles(
                script_data, audio_result, task_id
            )
            
            # 3. 合成视频
            merged_video = await self._merge_video_segments(video_segments, task_id)
            
            # 4. 添加音频轨道
            audio_file_path = audio_result.get('file_path') if audio_result else None
            self.logger.info(f"音频文件路径: {audio_file_path}")
            
            if audio_file_path and os.path.exists(audio_file_path):
                self.logger.info(f"音频文件存在，大小: {os.path.getsize(audio_file_path)} bytes")
                video_with_audio = await self._add_audio_track(
                    merged_video, audio_file_path, task_id
                )
            else:
                self.logger.warning("音频文件不存在或为空，跳过添加音频轨道")
                video_with_audio = merged_video
            
            # 5. 添加字幕
            final_video = await self._add_subtitles(
                video_with_audio, subtitle_file, task_id
            )
            
            # 6. 后处理优化
            optimized_video = await self._optimize_video(final_video, task_id)
            
            # 7. 移动到输出目录
            output_filename = f"{script_data['title']}_{task_id}.mp4"
            output_filename = FileUtils.clean_filename(output_filename)
            final_output_path = os.path.join(self.output_dir, output_filename)
            
            FileUtils.move_file(optimized_video, final_output_path)
            
            # 8. 验证最终视频
            is_valid, video_info = self._validate_final_video(final_output_path)
            
            processing_time = time.time() - start_time
            
            # 构建结果
            result = {
                'title': script_data['title'],
                'task_id': task_id,
                'file_path': final_output_path,
                'file_size': video_info['file_size'],
                'duration': video_info['duration'],
                'resolution': video_info['resolution'],
                'fps': video_info['fps'],
                'has_audio': True,
                'has_subtitles': True,
                'segments_count': len(video_segments),
                'processing_time': processing_time,
                'is_valid': is_valid
            }
            
            # 保存到数据库
            self.db.save_media_generation(
                task_id=task_id,
                media_type='final_video',
                description=f"最终视频: {script_data['title']}",
                file_path=final_output_path,
                file_size=video_info['file_size'],
                duration=video_info['duration'],
                cost=0.0,
                processing_time=processing_time
            )
            
            self.logger.info(f"视频合成完成: {final_output_path} ({video_info['duration']:.1f}秒)")
            return result
            
        except Exception as e:
            self.logger.error(f"视频合成失败: {e}")
            raise
    
    async def _create_video_segments(
        self,
        image_results: List[Dict[str, Any]], 
        video_results: List[Dict[str, Any]],
        script_data: Dict[str, Any],
        task_id: str
    ) -> List[Dict[str, Any]]:
        """
        创建视频片段
        
        Args:
            image_results: 图片结果
            video_results: 视频结果
            script_data: 脚本数据
            task_id: 任务ID
            
        Returns:
            视频片段列表
        """
        segments = []
        shots = script_data['shots']
        
        # 创建视频结果索引
        video_dict = {v['shot_index']: v for v in video_results}
        
        for i, shot in enumerate(shots):
            if i < len(video_results) and i in video_dict:
                # 使用生成的视频
                video_info = video_dict[i]
                segments.append({
                    'type': 'video',
                    'file_path': video_info['file_path'],
                    'duration': shot['duration'],
                    'description': shot['description'],
                    'shot_index': i
                })
            elif i < len(image_results):
                # 将图片转换为静态视频
                image_info = image_results[i]
                static_video = await self._create_static_video_segment(
                    image_info['file_path'],
                    shot['duration'], 
                    i,
                    task_id
                )
                segments.append({
                    'type': 'static_video',
                    'file_path': static_video,
                    'duration': shot['duration'],
                    'description': shot['description'],
                    'shot_index': i
                })
            else:
                # 创建占位视频
                placeholder_video = await self._create_placeholder_video_segment(
                    shot['duration'], i, task_id
                )
                segments.append({
                    'type': 'placeholder',
                    'file_path': placeholder_video,
                    'duration': shot['duration'],
                    'description': shot['description'],
                    'shot_index': i
                })
        
        self.logger.debug(f"创建了 {len(segments)} 个视频片段")
        return segments
    
    async def _create_static_video_segment(
        self, 
        image_path: str, 
        duration: int, 
        index: int,
        task_id: str
    ) -> str:
        """
        从图片创建静态视频片段（带动态效果）
        
        Args:
            image_path: 图片路径
            duration: 视频时长
            index: 片段索引
            task_id: 任务ID
            
        Returns:
            视频文件路径
        """
        output_path = os.path.join(self.temp_dir, f"{task_id}_segment_{index:02d}.mp4")
        
        try:
            width, height = self.resolution_map[self.output_resolution]
            
            # 获取视频效果配置
            effects_config = self.config.get('video_effects', {})
            enable_motion = effects_config.get('enable_static_motion', True)
            
            # 构建视频滤镜
            video_filters = []
            
            # 基础缩放和填充
            video_filters.append(f'scale={width*1.1}:{height*1.1}:force_original_aspect_ratio=decrease')
            video_filters.append(f'pad={width*1.1}:{height*1.1}:(ow-iw)/2:(oh-ih)/2')
            
            if enable_motion:
                # 添加肯·伯恩斯效果（缓慢缩放+移动）
                motion_type = ['zoom_in', 'zoom_out', 'pan_left', 'pan_right'][index % 4]
                motion_filter = self._get_motion_filter(motion_type, width, height, duration)
                video_filters.append(motion_filter)
            else:
                # 静态裁剪到目标尺寸
                video_filters.append(f'crop={width}:{height}')
            
            # 添加帧率
            video_filters.append(f'fps={self.output_fps}')
            
            # 使用ffmpeg创建动态视频
            cmd = [
                'ffmpeg', '-y',
                '-loop', '1',
                '-i', image_path,
                '-t', str(duration),
                '-vf', ','.join(video_filters),
                '-c:v', 'libx264',
                '-pix_fmt', 'yuv420p',
                '-preset', 'medium',
                '-crf', '23',
                output_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                return output_path
            else:
                raise RuntimeError(f"FFmpeg创建静态视频失败: {self._safe_decode(stderr)}")
                
        except Exception as e:
            self.logger.error(f"创建静态视频片段失败: {e}")
            # 创建简单的占位视频
            return await self._create_placeholder_video_segment(duration, index, task_id)
    
    def _get_motion_filter(self, motion_type: str, width: int, height: int, duration: int) -> str:
        """
        获取动态效果滤镜
        
        Args:
            motion_type: 动态类型
            width: 视频宽度
            height: 视频高度  
            duration: 时长
            
        Returns:
            滤镜字符串
        """
        # 计算总帧数
        total_frames = duration * self.output_fps
        
        # 使用简单的静态裁剪，避免复杂的时间变量表达式
        # 复杂的动态crop表达式容易出错，暂时禁用
        return f'crop={width}:{height}:(iw-ow)/2:(ih-oh)/2'
    
    async def _create_placeholder_video_segment(
        self, 
        duration: int, 
        index: int,
        task_id: str
    ) -> str:
        """创建占位视频片段"""
        output_path = os.path.join(self.temp_dir, f"{task_id}_placeholder_{index:02d}.mp4")
        
        try:
            width, height = self.resolution_map[self.output_resolution]
            
            # 创建纯色视频
            cmd = [
                'ffmpeg', '-y',
                '-f', 'lavfi',
                '-i', f'color=c=gray:size={width}x{height}:rate={self.output_fps}',
                '-t', str(duration),
                '-c:v', 'libx264',
                '-pix_fmt', 'yuv420p',
                output_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            await process.communicate()
            return output_path
            
        except Exception as e:
            self.logger.error(f"创建占位视频失败: {e}")
            # 返回空字符串，后续会跳过
            return ""
    
    async def _create_subtitles(
        self,
        script_data: Dict[str, Any],
        audio_result: Dict[str, Any],
        task_id: str
    ) -> str:
        """
        创建字幕文件
        
        Args:
            script_data: 脚本数据
            audio_result: 音频结果
            task_id: 任务ID
            
        Returns:
            字幕文件路径
        """
        subtitle_path = os.path.join(self.temp_dir, f"{task_id}_subtitles.srt")
        
        try:
            narration = script_data.get('narration', '')
            audio_duration = audio_result.get('duration', 10.0)
            
            if not narration:
                # 创建简单的标题字幕
                narration = script_data.get('title', '精彩内容')
            
            # 计算字幕时间轴
            subtitle_content = self._generate_subtitle_content(narration, audio_duration)
            
            # 保存字幕文件
            FileUtils.write_text_file(subtitle_path, subtitle_content, encoding='utf-8')
            
            self.logger.debug(f"字幕文件创建完成: {subtitle_path}")
            return subtitle_path
            
        except Exception as e:
            self.logger.error(f"创建字幕失败: {e}")
            return ""
    
    def _generate_subtitle_content(self, text: str, duration: float) -> str:
        """
        生成字幕内容
        
        Args:
            text: 文本内容
            duration: 总时长
            
        Returns:
            SRT格式字幕内容
        """
        # 智能文本分割
        sentences = self._smart_text_split(text)
        
        if not sentences:
            sentences = [text]
        
        subtitle_lines = []
        total_chars = sum(len(s) for s in sentences)
        
        # 根据字符数分配时间
        current_time = 0.0
        fade_duration = self.subtitle_style['fade_duration']
        
        for i, sentence in enumerate(sentences):
            # 根据字符数按比例分配时间
            char_ratio = len(sentence) / total_chars if total_chars > 0 else 1.0 / len(sentences)
            segment_duration = duration * char_ratio
            
            # 最短显示时间1秒，最长5秒
            segment_duration = max(1.0, min(5.0, segment_duration))
            
            start_time = current_time
            end_time = current_time + segment_duration
            
            # 添加淡入淡出效果时间
            if self.subtitle_style['fade_in'] and i > 0:
                start_time += fade_duration * 0.5
            
            start_str = self._seconds_to_srt_time(start_time)
            end_str = self._seconds_to_srt_time(end_time)
            
            # 处理长句子换行
            formatted_sentence = self._format_subtitle_text(sentence)
            
            subtitle_lines.extend([
                str(i + 1),
                f"{start_str} --> {end_str}",
                formatted_sentence,
                ""  # 空行
            ])
            
            current_time = end_time
        
        return '\n'.join(subtitle_lines)
    
    def _smart_text_split(self, text: str) -> List[str]:
        """
        智能文本分割
        
        Args:
            text: 原文本
            
        Returns:
            分割后的句子列表
        """
        import re
        
        # 首先按句号等分割
        sentences = re.split(r'[。！？.!?]', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        # 处理过长的句子（超过20字）
        final_sentences = []
        for sentence in sentences:
            if len(sentence) > 20:
                # 按逗号进一步分割
                parts = re.split(r'[，,]', sentence)
                parts = [p.strip() for p in parts if p.strip()]
                final_sentences.extend(parts)
            else:
                final_sentences.append(sentence)
        
        return final_sentences
    
    def _format_subtitle_text(self, text: str) -> str:
        """
        格式化字幕文本（换行处理）
        
        Args:
            text: 原文本
            
        Returns:
            格式化后的文本
        """
        # 如果文本超过15个字符，尝试在中间换行
        if len(text) > 15:
            mid_point = len(text) // 2
            # 寻找最近的空格或逗号作为换行点
            for offset in range(min(3, mid_point)):
                if mid_point - offset >= 0:
                    char = text[mid_point - offset]
                    if char in [' ', '，', ',']:
                        return text[:mid_point - offset] + '\n' + text[mid_point - offset + 1:]
                if mid_point + offset < len(text):
                    char = text[mid_point + offset]
                    if char in [' ', '，', ',']:
                        return text[:mid_point + offset] + '\n' + text[mid_point + offset + 1:]
            
            # 如果找不到合适的分割点，强制在中点换行
            return text[:mid_point] + '\n' + text[mid_point:]
        
        return text
    
    def _seconds_to_srt_time(self, seconds: float) -> str:
        """将秒转换为SRT时间格式"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millisecs = int((seconds % 1) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"
    
    async def _merge_video_segments(
        self, 
        segments: List[Dict[str, Any]], 
        task_id: str
    ) -> str:
        """
        合并视频片段（带转场效果）
        
        Args:
            segments: 视频片段列表
            task_id: 任务ID
            
        Returns:
            合并后的视频路径
        """
        output_path = os.path.join(self.temp_dir, f"{task_id}_merged_video.mp4")
        
        try:
            # 过滤有效的视频文件
            valid_segments = [seg for seg in segments if seg['file_path'] and FileUtils.path_exists(seg['file_path'])]
            
            if not valid_segments:
                raise ValueError("没有有效的视频片段")
            
            if len(valid_segments) == 1:
                # 只有一个片段，直接复制
                FileUtils.copy_file(valid_segments[0]['file_path'], output_path)
                return output_path
            
            # 检查是否启用转场效果
            effects_config = self.config.get('video_effects', {})
            enable_transitions = effects_config.get('enable_transitions', False)
            
            if enable_transitions and len(valid_segments) > 1:
                # 使用转场效果合并
                return await self._merge_with_transitions(valid_segments, task_id)
            else:
                # 简单拼接
                return await self._simple_concat(valid_segments, task_id)
                
        except Exception as e:
            self.logger.error(f"合并视频片段失败: {e}")
            # 返回第一个有效片段
            if segments and segments[0]['file_path']:
                return segments[0]['file_path']
            raise
    
    async def _simple_concat(self, segments: List[Dict[str, Any]], task_id: str) -> str:
        """简单拼接视频"""
        output_path = os.path.join(self.temp_dir, f"{task_id}_merged_video.mp4")
        
        # 创建输入文件列表
        filelist_path = os.path.join(self.temp_dir, f"{task_id}_filelist.txt")
        with open(filelist_path, 'w', encoding='utf-8') as f:
            for segment in segments:
                # 使用绝对路径避免问题
                abs_path = os.path.abspath(segment['file_path'])
                f.write(f"file '{abs_path}'\n")
        
        # 使用ffmpeg合并
        cmd = [
            'ffmpeg', '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', filelist_path,
            '-c', 'copy',
            output_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            # 清理临时文件
            Path(filelist_path).unlink(missing_ok=True)
            return output_path
        else:
            raise RuntimeError(f"FFmpeg合并视频失败: {self._safe_decode(stderr)}")
    
    async def _merge_with_transitions(self, segments: List[Dict[str, Any]], task_id: str) -> str:
        """
        使用转场效果合并视频
        
        Args:
            segments: 视频片段列表
            task_id: 任务ID
            
        Returns:
            合并后的视频路径
        """
        output_path = os.path.join(self.temp_dir, f"{task_id}_merged_with_transitions.mp4")
        
        # 转场效果列表
        transition_types = ['fade', 'dissolve', 'wipeleft', 'wiperight']
        transition_duration = 0.5  # 转场时长
        
        try:
            # 构建复杂的ffmpeg命令
            cmd = ['ffmpeg', '-y']
            
            # 添加输入文件
            for segment in segments:
                cmd.extend(['-i', segment['file_path']])
            
            # 构建滤镜图
            filter_complex = self._build_transition_filter_complex(
                len(segments), transition_types, transition_duration
            )
            
            cmd.extend([
                '-filter_complex', filter_complex,
                '-map', f'[final]',
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '23',
                output_path
            ])
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                return output_path
            else:
                # 转场失败，回退到简单拼接
                self.logger.warning(f"转场效果失败，使用简单拼接: {self._safe_decode(stderr)}")
                return await self._simple_concat(segments, task_id)
                
        except Exception as e:
            self.logger.warning(f"转场效果失败，使用简单拼接: {e}")
            return await self._simple_concat(segments, task_id)
    
    def _build_transition_filter_complex(
        self, 
        segment_count: int, 
        transition_types: List[str],
        transition_duration: float
    ) -> str:
        """
        构建转场滤镜复合命令
        
        Args:
            segment_count: 片段数量
            transition_types: 转场类型列表
            transition_duration: 转场时长
            
        Returns:
            滤镜复合字符串
        """
        if segment_count < 2:
            return "[0:v]copy[final]"
        
        filter_parts = []
        
        # 第一个片段
        current_output = "[v0]"
        filter_parts.append(f"[0:v]copy{current_output}")
        
        # 逐个添加转场
        for i in range(1, segment_count):
            transition_type = transition_types[(i-1) % len(transition_types)]
            prev_output = current_output
            current_output = f"[v{i}]"
            
            # 根据转场类型构建滤镜
            if transition_type == 'fade':
                filter_parts.append(
                    f"{prev_output}[{i}:v]xfade=transition=fade:duration={transition_duration}:offset=0{current_output}"
                )
            elif transition_type == 'dissolve':
                filter_parts.append(
                    f"{prev_output}[{i}:v]xfade=transition=dissolve:duration={transition_duration}:offset=0{current_output}"
                )
            elif transition_type == 'wipeleft':
                filter_parts.append(
                    f"{prev_output}[{i}:v]xfade=transition=wipeleft:duration={transition_duration}:offset=0{current_output}"
                )
            elif transition_type == 'wiperight':
                filter_parts.append(
                    f"{prev_output}[{i}:v]xfade=transition=wiperight:duration={transition_duration}:offset=0{current_output}"
                )
        
        # 最终输出
        filter_parts.append(f"{current_output}copy[final]")
        
        return ';'.join(filter_parts)
    
    async def _add_audio_track(
        self, 
        video_path: str, 
        audio_path: str, 
        task_id: str
    ) -> str:
        """
        添加音频轨道
        
        Args:
            video_path: 视频文件路径
            audio_path: 音频文件路径
            task_id: 任务ID
            
        Returns:
            添加音频后的视频路径
        """
        output_path = os.path.join(self.temp_dir, f"{task_id}_with_audio.mp4")
        
        try:
            if not FileUtils.path_exists(audio_path):
                self.logger.warning("音频文件不存在，跳过添加音频")
                return video_path
            
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-i', audio_path,
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-map', '0:v:0',
                '-map', '1:a:0',
                '-shortest',  # 以较短的为准
                output_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                return output_path
            else:
                self.logger.warning(f"添加音频失败: {self._safe_decode(stderr)}")
                return video_path
                
        except Exception as e:
            self.logger.error(f"添加音频轨道失败: {e}")
            return video_path
    
    async def _add_subtitles(
        self, 
        video_path: str, 
        subtitle_path: str, 
        task_id: str
    ) -> str:
        """
        添加字幕
        
        Args:
            video_path: 视频文件路径
            subtitle_path: 字幕文件路径
            task_id: 任务ID
            
        Returns:
            添加字幕后的视频路径
        """
        output_path = os.path.join(self.temp_dir, f"{task_id}_with_subtitles.mp4")
        
        try:
            if not FileUtils.path_exists(subtitle_path):
                self.logger.warning("字幕文件不存在，跳过添加字幕")
                return video_path
            
            # 修复路径分隔符问题（Windows路径需要转义或使用正斜杠）
            fixed_subtitle_path = subtitle_path.replace('\\', '/')
            
            # 构建简化的字幕滤镜（避免复杂样式导致的问题）
            subtitle_filter = f"subtitles={fixed_subtitle_path}"
            
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-vf', subtitle_filter,
                '-c:a', 'copy',
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '23',
                output_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                return output_path
            else:
                self.logger.warning(f"添加字幕失败: {self._safe_decode(stderr)}")
                return video_path
                
        except Exception as e:
            self.logger.error(f"添加字幕失败: {e}")
            return video_path
    
    def _color_to_hex(self, color_name: str) -> str:
        """颜色名称转十六进制（BGR格式）"""
        color_map = {
            'white': 'FFFFFF',
            'black': '000000',
            'red': '0000FF',      # BGR格式
            'green': '00FF00',
            'blue': 'FF0000',     # BGR格式
            'yellow': '00FFFF',   # BGR格式
            'orange': '0080FF',   # BGR格式
            'purple': 'FF00FF',   # BGR格式
            'cyan': 'FFFF00',     # BGR格式
            'gray': '808080',
            'pink': 'FF69B4'
        }
        return color_map.get(color_name.lower(), 'FFFFFF')
    
    def _get_alignment_value(self) -> int:
        """获取字幕对齐值"""
        alignment_map = {
            'left': 1,
            'center': 2,
            'right': 3,
            'bottom_left': 1,
            'bottom_center': 2,
            'bottom_right': 3,
            'top_left': 5,
            'top_center': 6,
            'top_right': 7
        }
        position = self.subtitle_style['position']
        alignment = self.subtitle_style['alignment']
        key = f"{position}_{alignment}" if position != 'center' else alignment
        return alignment_map.get(key, 2)
    
    async def _optimize_video(self, video_path: str, task_id: str) -> str:
        """
        优化视频
        
        Args:
            video_path: 输入视频路径
            task_id: 任务ID
            
        Returns:
            优化后的视频路径
        """
        output_path = os.path.join(self.temp_dir, f"{task_id}_optimized.mp4")
        
        try:
            width, height = self.resolution_map[self.output_resolution]
            
            # 获取质量配置
            quality_config = self.config.get('quality_control', {})
            video_quality = quality_config.get('video_quality', 'medium')
            
            # 根据质量设置参数
            quality_params = self._get_quality_params(video_quality)
            
            # 构建优化命令
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-vf', self._build_video_filters(width, height),
                '-c:v', 'libx264',
                '-preset', quality_params['preset'],
                '-crf', str(quality_params['crf']),
                '-maxrate', quality_params['maxrate'],
                '-bufsize', quality_params['bufsize'],
                '-c:a', 'aac',
                '-b:a', quality_params['audio_bitrate'],
                '-ar', '44100',  # 音频采样率
                '-ac', '2',      # 双声道
                '-movflags', '+faststart',  # 优化网络播放
                '-pix_fmt', 'yuv420p',  # 兼容性
                output_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                # 验证输出文件
                if FileUtils.path_exists(output_path) and FileUtils.get_file_size(output_path) > 1024:
                    return output_path
                else:
                    self.logger.warning("优化后文件异常，返回原文件")
                    return video_path
            else:
                self.logger.warning(f"视频优化失败: {self._safe_decode(stderr)}")
                return video_path
                
        except Exception as e:
            self.logger.error(f"视频优化失败: {e}")
            return video_path
    
    def _get_quality_params(self, quality: str) -> Dict[str, Any]:
        """
        获取质量参数
        
        Args:
            quality: 质量等级 (low/medium/high)
            
        Returns:
            质量参数字典
        """
        quality_settings = {
            'low': {
                'preset': 'fast',
                'crf': 28,
                'maxrate': '1000k',
                'bufsize': '2000k',
                'audio_bitrate': '96k'
            },
            'medium': {
                'preset': 'medium',
                'crf': 23,
                'maxrate': '2000k',
                'bufsize': '4000k',
                'audio_bitrate': '128k'
            },
            'high': {
                'preset': 'slow',
                'crf': 18,
                'maxrate': '4000k',
                'bufsize': '8000k',
                'audio_bitrate': '192k'
            }
        }
        return quality_settings.get(quality, quality_settings['medium'])
    
    def _build_video_filters(self, width: int, height: int) -> str:
        """
        构建视频滤镜
        
        Args:
            width: 目标宽度
            height: 目标高度
            
        Returns:
            滤镜字符串
        """
        filters = []
        
        # 基础缩放和填充
        scale_filter = f'scale={width}:{height}:force_original_aspect_ratio=decrease'
        pad_filter = f'pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black'
        
        filters.extend([scale_filter, pad_filter])
        
        # 检查是否需要添加视觉效果
        effects_config = self.config.get('video_effects', {})
        
        if effects_config.get('stabilization', False):
            filters.append('deshake')
        
        if effects_config.get('denoise', False):
            filters.append('hqdn3d=2:1:2:1')
        
        if effects_config.get('sharpen', False):
            filters.append('unsharp=5:5:1.0:5:5:0.0')
        
        # 色彩调整
        if effects_config.get('enhance_colors', False):
            filters.append('eq=brightness=0.05:contrast=1.1:saturation=1.15')
        
        return ','.join(filters)
    
    def _validate_final_video(self, video_path: str) -> Tuple[bool, Dict[str, Any]]:
        """
        验证最终视频
        
        Args:
            video_path: 视频路径
            
        Returns:
            (是否合格, 视频信息)
        """
        try:
            # 使用ffprobe获取视频信息
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_format', '-show_streams', video_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, encoding='utf-8', errors='ignore')
            
            if result.returncode == 0 and result.stdout:
                try:
                    info = json.loads(result.stdout)
                except json.JSONDecodeError as e:
                    self.logger.error(f"FFprobe输出JSON解析失败: {e}, 输出内容: {result.stdout}")
                    raise ValueError(f"视频信息解析失败: {e}")
                
                format_info = info.get('format', {})
                duration = float(format_info.get('duration', 0))
                file_size = int(format_info.get('size', 0))
                
                video_stream = None
                audio_stream = None
                
                for stream in info.get('streams', []):
                    if stream.get('codec_type') == 'video':
                        video_stream = stream
                    elif stream.get('codec_type') == 'audio':
                        audio_stream = stream
                
                if video_stream:
                    width = video_stream.get('width', 0)
                    height = video_stream.get('height', 0)
                    fps = eval(video_stream.get('r_frame_rate', '0/1'))
                else:
                    width = height = fps = 0
                
                video_info = {
                    'duration': duration,
                    'file_size': file_size,
                    'resolution': f"{width}x{height}",
                    'fps': fps,
                    'has_audio': audio_stream is not None
                }
                
                # 质量检查
                is_valid = (
                    duration >= self.final_duration_min * 0.8 and  # 时长检查
                    file_size > 1024 * 1024 and  # 至少1MB
                    width > 0 and height > 0  # 分辨率有效
                )
                
                return is_valid, video_info
            else:
                # ffprobe失败，使用基础检查
                error_msg = self._safe_decode(result.stderr) if result.stderr else "未知错误"
                self.logger.warning(f"FFprobe执行失败: {error_msg}")
                
                file_size = FileUtils.get_file_size(video_path)
                video_info = {
                    'duration': 0.0,
                    'file_size': file_size,
                    'resolution': f"{self.resolution_map[self.output_resolution][0]}x{self.resolution_map[self.output_resolution][1]}",
                    'fps': self.output_fps,
                    'has_audio': False
                }
                
                return file_size > 0, video_info
                
        except Exception as e:
            self.logger.error(f"视频验证失败: {e}")
            file_size = FileUtils.get_file_size(video_path) if FileUtils.path_exists(video_path) else 0
            video_info = {
                'duration': 0.0,
                'file_size': file_size,
                'resolution': f"{self.resolution_map[self.output_resolution][0]}x{self.resolution_map[self.output_resolution][1]}",
                'fps': self.output_fps,
                'has_audio': False
            }
            return file_size > 0, video_info
    
    def cleanup_temp_files(self, task_id: str):
        """
        清理临时文件
        
        Args:
            task_id: 任务ID
        """
        try:
            temp_files = FileUtils.list_files(self.temp_dir, f"{task_id}_*")
            for file_path in temp_files:
                try:
                    file_path.unlink()
                except Exception:
                    pass
            
            self.logger.debug(f"清理了 {len(temp_files)} 个临时文件")
            
        except Exception as e:
            self.logger.error(f"清理临时文件失败: {e}")


async def test_video_editor():
    """测试视频编辑器"""
    # 模拟配置
    config = {
        'generation': {
            'output_resolution': '720p',
            'output_fps': 24,
            'final_duration_min': 120,
            'final_duration_max': 240
        },
        'storage': {
            'temp_dir': './test_temp',
            'output_dir': './test_output',
            'database_path': './test_db.db'
        }
    }
    
    # 模拟数据
    script_data = {
        'title': '测试视频',
        'narration': '这是一个测试视频的旁白内容。'
    }
    
    audio_result = {
        'file_path': '',
        'duration': 10.0
    }
    
    try:
        editor = VideoEditor(config)
        
        # 测试字幕生成
        print("测试字幕生成...")
        subtitle_content = editor._generate_subtitle_content("测试句子一。测试句子二！", 10.0)
        print(f"字幕内容: {subtitle_content[:100]}...")
        
        # 测试时间格式转换
        time_str = editor._seconds_to_srt_time(65.5)
        print(f"时间转换测试: 65.5秒 -> {time_str}")
        
        # 测试颜色转换
        hex_color = editor._color_to_hex('white')
        print(f"颜色转换测试: white -> {hex_color}")
        
        print("视频编辑器测试完成")
        
    except Exception as e:
        print(f"视频编辑器测试失败: {e}")
    finally:
        # 清理测试文件
        import shutil
        for path in ['./test_temp', './test_output']:
            if Path(path).exists():
                shutil.rmtree(path)
        Path('./test_db.db').unlink(missing_ok=True)


if __name__ == "__main__":
    asyncio.run(test_video_editor())