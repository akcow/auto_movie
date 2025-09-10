#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
图生视频模块
负责调用火山引擎图生视频API，将静态图片转换为动态视频
"""

import os
import asyncio
import base64
import time
import json
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import requests
from PIL import Image
import sys
sys.path.append(str(Path(__file__).parent.parent))

from utils.logger import LoggerMixin
from utils.api_utils import APIUtils, cost_tracker
from utils.file_utils import FileUtils
from utils.database import DatabaseManager
from utils.tos_client import TOSClient


class VideoGenerator(LoggerMixin):
    """图生视频生成器"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化视频生成器
        
        Args:
            config: 配置字典
        """
        self.config = config
        self.api_config = config.get('api', {}).get('volcengine', {})
        self.models_config = config.get('models', {})
        self.generation_config = config.get('generation', {})
        self.storage_config = config.get('storage', {})
        
        # API配置（使用统一的api_key认证）
        self.api_key = self.api_config.get('api_key')
        self.region = self.api_config.get('region', 'cn-beijing')
        self.model = self.models_config.get('image_to_video_endpoint', 'image2video_v1.0')
        
        if not self.api_key:
            raise ValueError("图生视频API配置不完整，请在config.yaml中配置api_key")
        
        # API工具
        self.api_utils = APIUtils(config)
        
        # 生成参数
        self.video_segments = self.generation_config.get('video_segments', 3)
        self.video_duration = self.generation_config.get('video_duration', 5)
        self.output_fps = self.generation_config.get('output_fps', 24)
        self.output_resolution = self.generation_config.get('output_resolution', '720p')
        
        # 存储配置
        self.temp_dir = self.storage_config.get('temp_dir', './data/temp')
        self.output_dir = self.storage_config.get('output_dir', './data/output')
        
        # 确保目录存在
        FileUtils.ensure_dir(self.temp_dir)
        FileUtils.ensure_dir(self.output_dir)
        
        # 数据库
        self.db = DatabaseManager(self.storage_config.get('database_path', './data/database.db'))
        
        # TOS客户端（用于图片上传）
        try:
            self.tos_client = TOSClient(config)
            self.logger.info("TOS客户端初始化成功，将使用云存储上传图片")
        except Exception as e:
            self.logger.warning(f"TOS客户端初始化失败: {e}，图生视频功能将被禁用")
            self.tos_client = None
        
        # 提示词模板
        self.video_prompt_template = self._load_video_prompt_template()
    
    def _load_video_prompt_template(self) -> str:
        """加载视频生成提示词模板"""
        template_path = self.config.get('prompts', {}).get('video_prompt_template', './prompts/video_prompt.txt')
        
        if FileUtils.path_exists(template_path):
            return FileUtils.read_text_file(template_path)
        else:
            return "将这张静态图转换成{duration}秒动态视频：{description}，摄像机缓慢推进，轻微视差，2.5D动画效果，{style}风格，流畅自然"
    
    async def generate_videos(
        self, 
        image_results: List[Dict[str, Any]], 
        script_data: Dict[str, Any],
        task_id: str
    ) -> List[Dict[str, Any]]:
        """
        批量生成视频
        
        Args:
            image_results: 图片生成结果
            script_data: 脚本数据
            task_id: 任务ID
            
        Returns:
            生成的视频信息列表
        """
        try:
            self.logger.info(f"开始生成视频: 前{self.video_segments}个镜头转为视频")
            
            # 选择前N个图片用于视频生成
            video_images = image_results[:self.video_segments]
            shots = script_data['shots'][:self.video_segments]
            style = script_data.get('style', '现代 写实')
            
            if len(video_images) < self.video_segments:
                self.logger.warning(f"图片数量不足: {len(video_images)}/{self.video_segments}")
            
            # 串行生成视频（避免GPU资源冲突）
            results = []
            for i, (image_info, shot) in enumerate(zip(video_images, shots)):
                if image_info and not image_info.get('is_fallback', False):
                    result = await self._generate_single_video(
                        image_path=image_info['file_path'],
                        description=shot['description'],
                        style=style,
                        duration=shot.get('duration', self.video_duration),
                        shot_index=i,
                        task_id=task_id
                    )
                    
                    if result:
                        results.append(result)
                    else:
                        # 生成失败，创建静态视频
                        fallback_result = await self._create_static_video(
                            image_info, shot, i, task_id
                        )
                        results.append(fallback_result)
                else:
                    # 使用占位图片创建静态视频
                    fallback_result = await self._create_static_video(
                        image_info or {}, shot, i, task_id
                    )
                    results.append(fallback_result)
                
                # 视频生成间隔，避免资源冲突
                if i < len(video_images) - 1:
                    await asyncio.sleep(3)
            
            successful_results = [r for r in results if r is not None]
            
            self.logger.info(f"视频生成完成: {len(successful_results)}/{len(video_images)} 成功")
            return successful_results
            
        except Exception as e:
            self.logger.error(f"批量视频生成失败: {e}")
            raise
    
    async def _generate_single_video(
        self,
        image_path: str,
        description: str,
        style: str,
        duration: int,
        shot_index: int,
        task_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        生成单个视频
        
        Args:
            image_path: 输入图片路径
            description: 视频描述
            style: 视觉风格
            duration: 视频时长
            shot_index: 镜头索引
            task_id: 任务ID
            
        Returns:
            视频信息字典
        """
        try:
            # 检查TOS客户端是否可用
            if self.tos_client is None:
                self.logger.warning("TOS客户端不可用，跳过图生视频，将创建静态视频")
                return None
            
            start_time = time.time()
            
            # 构建视频生成提示词
            prompt = self._build_video_prompt(description, style, duration)
            
            # 预处理图片
            processed_image_path = await self._preprocess_image(image_path, shot_index)
            
            # 调用API生成视频
            video_data = await self._call_image2video_api(
                processed_image_path, prompt, duration
            )
            
            # 保存视频文件
            video_path = await self._save_video(
                video_data=video_data,
                filename=f"{task_id}_video_{shot_index:02d}.mp4"
            )
            
            # 验证视频质量
            is_valid, video_info = self._validate_video(video_path, duration)
            
            if not is_valid:
                self.logger.warning(f"视频质量不合格: {video_path}")
                # 返回静态视频作为后备
                return await self._create_static_video_from_image(
                    image_path, duration, shot_index, task_id
                )
            
            processing_time = time.time() - start_time
            
            # 构建结果信息
            result = {
                'shot_index': shot_index,
                'description': description,
                'prompt': prompt,
                'input_image': image_path,
                'file_path': video_path,
                'file_size': video_info['file_size'],
                'duration': video_info['duration'],
                'resolution': video_info['resolution'],
                'fps': video_info['fps'],
                'processing_time': processing_time,
                'cost': 0.15  # 火山引擎图生视频成本约0.15元/次
            }
            
            # 保存到数据库
            self.db.save_media_generation(
                task_id=task_id,
                media_type='video',
                description=description,
                file_path=video_path,
                file_size=video_info['file_size'],
                duration=video_info['duration'],
                cost=result['cost'],
                processing_time=processing_time
            )
            
            # 记录成本
            cost_tracker.add_cost('image2video', result['cost'], 1)
            
            self.logger.debug(f"视频生成成功: {shot_index} - {video_path}")
            return result
            
        except Exception as e:
            self.logger.error(f"单个视频生成失败 [{shot_index}]: {e}")
            return None
    
    def _build_video_prompt(self, description: str, style: str, duration: int) -> str:
        """
        构建视频生成提示词
        
        Args:
            description: 基础描述
            style: 视觉风格
            duration: 视频时长
            
        Returns:
            完整的提示词
        """
        prompt = self.video_prompt_template.format(
            description=description,
            style=style,
            duration=duration
        )
        
        # 确保提示词不超过限制
        if len(prompt) > 300:
            # 截断描述部分
            max_desc_len = 100
            if len(description) > max_desc_len:
                description = description[:max_desc_len] + "..."
            
            prompt = self.video_prompt_template.format(
                description=description,
                style=style,
                duration=duration
            )
        
        return prompt
    
    async def _preprocess_image(self, image_path: str, shot_index: int) -> str:
        """
        预处理输入图片
        
        Args:
            image_path: 原图片路径
            shot_index: 镜头索引
            
        Returns:
            处理后图片路径
        """
        try:
            processed_path = os.path.join(
                self.temp_dir, 
                f"processed_{shot_index}_{int(time.time())}.jpg"
            )
            
            with Image.open(image_path) as img:
                # 转换为RGB模式
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # 调整尺寸以符合视频要求
                target_width, target_height = self._get_video_resolution()
                
                # 保持宽高比的情况下调整大小
                img_ratio = img.width / img.height
                target_ratio = target_width / target_height
                
                if img_ratio > target_ratio:
                    # 图片较宽，以高度为准
                    new_height = target_height
                    new_width = int(new_height * img_ratio)
                else:
                    # 图片较高，以宽度为准
                    new_width = target_width
                    new_height = int(new_width / img_ratio)
                
                img = img.resize((new_width, new_height), Image.LANCZOS)
                
                # 如果尺寸不匹配，进行裁剪或填充
                if (new_width, new_height) != (target_width, target_height):
                    # 中心裁剪
                    left = (new_width - target_width) // 2
                    top = (new_height - target_height) // 2
                    right = left + target_width
                    bottom = top + target_height
                    
                    img = img.crop((left, top, right, bottom))
                
                # 保存处理后的图片
                img.save(processed_path, 'JPEG', quality=90)
            
            self.logger.debug(f"图片预处理完成: {processed_path}")
            return processed_path
            
        except Exception as e:
            self.logger.error(f"图片预处理失败: {e}")
            # 返回原图片路径
            return image_path
    
    def _get_video_resolution(self) -> Tuple[int, int]:
        """获取视频分辨率"""
        resolution_map = {
            '480p': (480, 854),    # 9:16 竖屏
            '720p': (720, 1280),   # 9:16 竖屏
            '1080p': (1080, 1920)  # 9:16 竖屏
        }
        return resolution_map.get(self.output_resolution, (720, 1280))
    
    async def _call_image2video_api(
        self, 
        image_path: str, 
        prompt: str, 
        duration: int
    ) -> bytes:
        """
        调用图生视频API（使用Ark SDK模式）
        
        Args:
            image_path: 输入图片路径
            prompt: 生成提示词
            duration: 视频时长
            
        Returns:
            视频二进制数据
        """
        try:
            from volcenginesdkarkruntime import Ark
            import asyncio
            
            # 在线程池中运行同步的Ark SDK调用
            loop = asyncio.get_event_loop()
            
            def sync_generate_video():
                # 使用Ark SDK
                client = Ark(api_key=self.api_key, region=self.region)
                
                # 上传图片到TOS获取公网URL
                if not hasattr(self, 'tos_client') or self.tos_client is None:
                    raise ValueError("TOS客户端未初始化，无法上传图片")
                
                # 在当前线程中创建事件循环来调用异步方法
                import asyncio
                try:
                    # 获取当前事件循环
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    # 如果没有事件循环，创建一个新的
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                # 上传图片
                image_url = loop.run_until_complete(
                    self.tos_client.upload_image(image_path, task_id="video_gen")
                )
                
                # 创建图生视频任务
                create_result = client.content_generation.tasks.create(
                    model=self.model,
                    content=[
                        {
                            "type": "text",
                            "text": f"{prompt} --dur {duration}"
                        },
                        {
                            "type": "image_url", 
                            "image_url": {
                                "url": image_url
                            }
                        }
                    ]
                )
                
                # 轮询任务状态
                task_id = create_result.id
                import time
                max_wait_time = 300  # 最大等待5分钟
                wait_time = 0
                
                while wait_time < max_wait_time:
                    get_result = client.content_generation.tasks.get(task_id=task_id)
                    
                    if get_result.status == "succeeded":
                        # 任务成功，返回视频URL
                        if hasattr(get_result, 'content') and hasattr(get_result.content, 'video_url'):
                            return get_result.content.video_url
                        else:
                            raise ValueError("API任务成功但未返回视频URL")
                    elif get_result.status == "failed":
                        error_msg = getattr(get_result, 'error', '未知错误')
                        raise ValueError(f"视频生成任务失败: {error_msg}")
                    else:
                        # 等待任务完成
                        time.sleep(10)
                        wait_time += 10
                
                raise TimeoutError(f"视频生成任务超时({max_wait_time}秒)")
            
            # 异步执行同步调用
            video_url = await loop.run_in_executor(None, sync_generate_video)
            
            # 下载视频
            response = await self.api_utils.make_async_request(
                method="GET",
                url=video_url,
                timeout=300
            )
            
            # 处理API工具返回的响应格式
            if isinstance(response, dict) and 'content' in response:
                return response['content']  # 返回二进制数据
            elif isinstance(response, bytes):
                return response
            else:
                raise ValueError("下载的视频数据格式异常")
                
        except ImportError:
            self.logger.error("缺少volcenginesdkarkruntime依赖，请安装：pip install volcengine-sdk-ark")
            raise
        except Exception as e:
            self.logger.error(f"图生视频API调用失败: {e}")
            # 返回空视频数据，让后续流程继续
            return b""
    
    def _get_access_token(self) -> str:
        """获取访问令牌"""
        return self.api_key
    
    async def _poll_video_result(self, task_id: str, max_wait: int = 300) -> bytes:
        """
        轮询视频生成结果
        
        Args:
            task_id: 任务ID
            max_wait: 最大等待时间(秒)
            
        Returns:
            视频二进制数据
        """
        start_time = time.time()
        poll_interval = 10  # 轮询间隔
        
        while time.time() - start_time < max_wait:
            try:
                # 查询任务状态
                headers = {
                    "Authorization": f"Bearer {self._get_access_token()}"
                }
                
                api_url = f"https://visual.volcengineapi.com/visual/general/v1.0/image2video/result/{task_id}"
                
                response = await self.api_utils.make_async_request(
                    method="GET",
                    url=api_url,
                    headers=headers,
                    timeout=30
                )
                
                status = response.get('status')
                
                if status == 'completed':
                    video_b64 = response['data']['video']
                    return base64.b64decode(video_b64)
                elif status == 'failed':
                    raise ValueError(f"视频生成失败: {response.get('error', '未知错误')}")
                elif status == 'processing':
                    self.logger.debug(f"视频生成中... ({task_id})")
                    await asyncio.sleep(poll_interval)
                else:
                    raise ValueError(f"未知任务状态: {status}")
                    
            except Exception as e:
                self.logger.warning(f"轮询任务状态失败: {e}")
                await asyncio.sleep(poll_interval)
        
        raise TimeoutError(f"视频生成超时: {task_id}")
    
    async def _save_video(self, video_data: bytes, filename: str) -> str:
        """
        保存视频文件
        
        Args:
            video_data: 视频二进制数据
            filename: 文件名
            
        Returns:
            保存的文件路径
        """
        file_path = os.path.join(self.temp_dir, filename)
        
        try:
            with open(file_path, 'wb') as f:
                f.write(video_data)
            
            self.logger.debug(f"视频保存成功: {file_path}")
            return file_path
            
        except Exception as e:
            self.logger.error(f"视频保存失败: {e}")
            raise
    
    def _validate_video(self, video_path: str, expected_duration: int) -> Tuple[bool, Dict[str, Any]]:
        """
        验证视频质量
        
        Args:
            video_path: 视频路径
            expected_duration: 预期时长
            
        Returns:
            (是否合格, 视频信息)
        """
        try:
            # 使用ffprobe获取视频信息
            import subprocess
            
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json', 
                '-show_format', '-show_streams', video_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, encoding='utf-8', errors='ignore')
            
            if result.returncode == 0:
                info = json.loads(result.stdout)
                
                # 提取视频信息
                format_info = info.get('format', {})
                duration = float(format_info.get('duration', 0))
                file_size = int(format_info.get('size', 0))
                
                video_stream = None
                for stream in info.get('streams', []):
                    if stream.get('codec_type') == 'video':
                        video_stream = stream
                        break
                
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
                    'fps': fps
                }
                
                # 基础质量检查
                if duration < expected_duration * 0.8:  # 时长误差20%内可接受
                    return False, video_info
                
                if file_size < 100 * 1024:  # 小于100KB可能有问题
                    return False, video_info
                
                if width < 400 or height < 400:  # 分辨率太低
                    return False, video_info
                
                return True, video_info
            else:
                # ffprobe失败，使用基础检查
                file_size = FileUtils.get_file_size(video_path)
                video_info = {
                    'duration': expected_duration,
                    'file_size': file_size,
                    'resolution': f"{self._get_video_resolution()[0]}x{self._get_video_resolution()[1]}",
                    'fps': self.output_fps
                }
                
                return file_size > 100 * 1024, video_info
                
        except Exception as e:
            self.logger.error(f"视频验证失败: {e}")
            # 返回基础信息
            file_size = FileUtils.get_file_size(video_path) if FileUtils.path_exists(video_path) else 0
            video_info = {
                'duration': expected_duration,
                'file_size': file_size,
                'resolution': f"{self._get_video_resolution()[0]}x{self._get_video_resolution()[1]}",
                'fps': self.output_fps
            }
            return file_size > 0, video_info
    
    async def _create_static_video(
        self, 
        image_info: Dict[str, Any], 
        shot: Dict[str, Any], 
        shot_index: int, 
        task_id: str
    ) -> Dict[str, Any]:
        """
        创建静态视频(图片循环)
        
        Args:
            image_info: 图片信息
            shot: 镜头信息
            shot_index: 镜头索引
            task_id: 任务ID
            
        Returns:
            视频信息字典
        """
        return await self._create_static_video_from_image(
            image_info.get('file_path', ''),
            shot.get('duration', self.video_duration),
            shot_index,
            task_id
        )
    
    async def _create_static_video_from_image(
        self, 
        image_path: str, 
        duration: int, 
        shot_index: int, 
        task_id: str
    ) -> Dict[str, Any]:
        """
        从图片创建静态视频
        
        Args:
            image_path: 图片路径
            duration: 视频时长
            shot_index: 镜头索引
            task_id: 任务ID
            
        Returns:
            视频信息字典
        """
        try:
            # 创建简单的静态视频
            output_path = os.path.join(self.temp_dir, f"{task_id}_static_{shot_index:02d}.mp4")
            
            if FileUtils.path_exists(image_path):
                # 使用ffmpeg创建静态视频
                await self._create_static_video_with_ffmpeg(image_path, output_path, duration)
            else:
                # 创建纯色视频
                await self._create_placeholder_video(output_path, duration)
            
            # 获取视频信息
            file_size = FileUtils.get_file_size(output_path) if FileUtils.path_exists(output_path) else 0
            width, height = self._get_video_resolution()
            
            return {
                'shot_index': shot_index,
                'description': f"静态视频 {shot_index}",
                'input_image': image_path,
                'file_path': output_path,
                'file_size': file_size,
                'duration': duration,
                'resolution': f"{width}x{height}",
                'fps': self.output_fps,
                'processing_time': 1.0,
                'cost': 0.0,
                'is_static': True
            }
            
        except Exception as e:
            self.logger.error(f"创建静态视频失败: {e}")
            return None
    
    async def _create_static_video_with_ffmpeg(
        self, 
        image_path: str, 
        output_path: str, 
        duration: int
    ):
        """使用ffmpeg创建静态视频"""
        try:
            import subprocess
            
            width, height = self._get_video_resolution()
            
            cmd = [
                'ffmpeg', '-y',  # 覆盖输出文件
                '-loop', '1',    # 循环图片
                '-i', image_path,
                '-t', str(duration),  # 视频时长
                '-vf', f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2',
                '-r', str(self.output_fps),  # 帧率
                '-c:v', 'libx264',  # 编码器
                '-pix_fmt', 'yuv420p',  # 像素格式
                output_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                raise RuntimeError(f"FFmpeg执行失败: {stderr.decode()}")
                
        except Exception as e:
            self.logger.error(f"FFmpeg创建静态视频失败: {e}")
            # 创建占位视频
            await self._create_placeholder_video(output_path, duration)
    
    async def _create_placeholder_video(self, output_path: str, duration: int):
        """创建占位视频"""
        try:
            import subprocess
            
            width, height = self._get_video_resolution()
            
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
            
        except Exception as e:
            self.logger.error(f"创建占位视频失败: {e}")
    
    def get_generation_summary(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        获取生成总结
        
        Args:
            results: 生成结果列表
            
        Returns:
            生成总结
        """
        if not results:
            return {'total': 0, 'successful': 0, 'static': 0, 'failed': 0, 'total_cost': 0.0}
        
        total = len(results)
        successful = len([r for r in results if r and not r.get('is_static', False)])
        static = len([r for r in results if r and r.get('is_static', False)])
        failed = total - successful - static
        total_cost = sum(r.get('cost', 0.0) for r in results if r)
        total_time = sum(r.get('processing_time', 0.0) for r in results if r)
        total_duration = sum(r.get('duration', 0.0) for r in results if r)
        
        return {
            'total': total,
            'successful': successful,
            'static': static,
            'failed': failed,
            'total_cost': total_cost,
            'total_time': total_time,
            'total_duration': total_duration,
            'avg_time': total_time / total if total > 0 else 0
        }


async def test_video_generator():
    """测试视频生成器"""
    # 模拟配置
    config = {
        'api': {
            'volcengine': {
                'api_key': 'mock_api_key'
            }
        },
        'models': {
            'image_to_video_endpoint': 'ep-20241230140000-xxxxx'
        },
        'generation': {
            'video_segments': 3,
            'video_duration': 5,
            'output_fps': 24,
            'output_resolution': '720p'
        },
        'storage': {
            'temp_dir': './test_temp',
            'output_dir': './test_output',
            'database_path': './test_db.db'
        },
        'prompts': {
            'video_prompt_template': './prompts/video_prompt.txt'
        },
        'api_settings': {
            'max_retries': 3,
            'request_timeout': 30
        }
    }
    
    try:
        generator = VideoGenerator(config)
        
        # 测试提示词构建
        prompt = generator._build_video_prompt("测试场景", "古风 唯美", 5)
        print(f"视频提示词测试: {prompt}")
        
        # 测试分辨率获取
        resolution = generator._get_video_resolution()
        print(f"视频分辨率: {resolution}")
        
        print("视频生成器测试完成")
        
    except Exception as e:
        print(f"视频生成器测试失败: {e}")
    finally:
        # 清理测试文件
        import shutil
        for path in ['./test_temp', './test_output']:
            if Path(path).exists():
                shutil.rmtree(path)
        Path('./test_db.db').unlink(missing_ok=True)


if __name__ == "__main__":
    asyncio.run(test_video_generator())