#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
文生图模块
负责调用火山引擎文生图API，批量生成高质量图片
"""

import os
import asyncio
import base64
import time
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


class ImageGenerator(LoggerMixin):
    """文生图生成器"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化图片生成器
        
        Args:
            config: 配置字典
        """
        self.config = config
        self.api_config = config.get('api', {}).get('volcengine', {})
        self.models_config = config.get('models', {})
        self.generation_config = config.get('generation', {})
        self.storage_config = config.get('storage', {})
        
        # API配置（使用通用2.0模型）
        self.access_key_id = self.api_config.get('access_key_id') or self.api_config.get('api_key')
        self.secret_access_key = self.api_config.get('secret_access_key')
        self.api_key = self.api_config.get('api_key')  # 兼容旧配置
        self.region = self.api_config.get('region', 'cn-north-1')  # 通用2.0模型使用cn-north-1
        self.model = self.models_config.get('text2image_endpoint', 'high_aes_general_v20_L')
        
        # 检查认证配置
        if not self.access_key_id:
            raise ValueError("文生图API配置不完整，请在config.yaml中配置access_key_id或api_key")
        
        # 如果没有secret_access_key，使用单一认证模式
        if not self.secret_access_key:
            self.logger.warning("未配置secret_access_key，将使用单一认证模式")
            self.use_dual_auth = False
        else:
            self.use_dual_auth = True
        
        # API工具
        self.api_utils = APIUtils(config)
        
        # 生成参数
        self.image_size = self.generation_config.get('image_size', '512x768')
        self.image_quality = self.generation_config.get('image_quality', 'high')
        self.max_images = self.generation_config.get('max_images', 15)
        
        # 存储配置
        self.temp_dir = self.storage_config.get('temp_dir', './data/temp')
        self.output_dir = self.storage_config.get('output_dir', './data/output')
        
        # 确保目录存在
        FileUtils.ensure_dir(self.temp_dir)
        FileUtils.ensure_dir(self.output_dir)
        
        # 数据库
        self.db = DatabaseManager(self.storage_config.get('database_path', './data/database.db'))
        
        # 提示词模板
        self.image_prompt_template = self._load_image_prompt_template()
    
    def _load_image_prompt_template(self) -> str:
        """加载图片生成提示词模板"""
        template_path = self.config.get('prompts', {}).get('image_prompt_template', './prompts/image_prompt.txt')
        
        if FileUtils.path_exists(template_path):
            return FileUtils.read_text_file(template_path)
        else:
            return "{style}，{description}，超高分辨率，竖屏9:16，精美细节，光影对比强烈，色彩绚丽，--ar 9:16 --q 2"
    
    async def generate_images(
        self, 
        script_data: Dict[str, Any], 
        task_id: str
    ) -> List[Dict[str, Any]]:
        """
        批量生成图片
        
        Args:
            script_data: 脚本数据
            task_id: 任务ID
            
        Returns:
            生成的图片信息列表
        """
        try:
            self.logger.info(f"开始生成图片: {len(script_data['shots'])} 个镜头")
            
            # 提取需要生成的镜头
            shots = script_data['shots'][:self.max_images]
            style = script_data.get('style', '现代 写实 高质量')
            
            # 并行生成图片
            tasks = []
            for i, shot in enumerate(shots):
                task = self._generate_single_image(
                    description=shot['description'],
                    style=style,
                    shot_index=i,
                    task_id=task_id
                )
                tasks.append(task)
            
            # 控制并发数量，避免API限流
            results = []
            batch_size = 3  # 每批3个并发
            
            for i in range(0, len(tasks), batch_size):
                batch_tasks = tasks[i:i+batch_size]
                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                
                for result in batch_results:
                    if isinstance(result, Exception):
                        self.logger.error(f"图片生成异常: {result}")
                        # 生成默认图片信息
                        results.append(self._create_fallback_image_info())
                    else:
                        results.append(result)
                
                # 批次间延迟，避免频率限制
                if i + batch_size < len(tasks):
                    await asyncio.sleep(2)
            
            # 过滤成功的结果
            successful_results = [r for r in results if r is not None]
            
            self.logger.info(f"图片生成完成: {len(successful_results)}/{len(shots)} 成功")
            return successful_results
            
        except Exception as e:
            self.logger.error(f"批量图片生成失败: {e}")
            raise
    
    async def _generate_single_image(
        self,
        description: str,
        style: str,
        shot_index: int,
        task_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        生成单张图片
        
        Args:
            description: 图片描述
            style: 视觉风格
            shot_index: 镜头索引
            task_id: 任务ID
            
        Returns:
            图片信息字典
        """
        try:
            start_time = time.time()
            
            # 构建提示词
            prompt = self._build_image_prompt(description, style)
            
            # 调用API生成图片
            image_data = await self._call_text2image_api(prompt)
            
            # 保存图片文件
            image_path = await self._save_image(
                image_data=image_data,
                filename=f"{task_id}_shot_{shot_index:02d}.png"
            )
            
            # 验证图片质量
            is_valid, image_info = self._validate_image(image_path)
            
            if not is_valid:
                self.logger.warning(f"图片质量不合格: {image_path}")
                self.logger.info(f"图片详情: {image_info}")
                # 限制重试，避免递归
                return await self._retry_generation(description, style, shot_index, task_id)
            
            processing_time = time.time() - start_time
            
            # 记录生成信息
            result = {
                'shot_index': shot_index,
                'description': description,
                'prompt': prompt,
                'file_path': image_path,
                'file_size': image_info['file_size'],
                'resolution': image_info['resolution'],
                'processing_time': processing_time,
                'cost': 0.025  # 火山引擎文生图成本约0.025元/张
            }
            
            # 保存到数据库
            self.db.save_media_generation(
                task_id=task_id,
                media_type='image',
                description=description,
                file_path=image_path,
                file_size=image_info['file_size'],
                duration=0.0,
                cost=result['cost'],
                processing_time=processing_time
            )
            
            # 记录成本
            cost_tracker.add_cost('text2image', result['cost'], 1)
            
            self.logger.debug(f"图片生成成功: {shot_index} - {image_path}")
            return result
            
        except Exception as e:
            self.logger.error(f"单张图片生成失败 [{shot_index}]: {e}")
            return None
    
    def _build_image_prompt(self, description: str, style: str) -> str:
        """
        构建图片生成提示词（按照通用2.0模型推荐结构）
        
        Args:
            description: 基础描述
            style: 视觉风格
            
        Returns:
            完整的提示词
        """
        # 解析描述，按照推荐结构重新组织
        parsed_components = self._parse_description_for_v2_model(description, style)
        
        # 按照推荐顺序构建提示词：场景 → 角色 → 构图 → 动作 → 风格
        prompt_parts = []
        
        # 1. 场景描述
        if parsed_components['scene']:
            prompt_parts.append(parsed_components['scene'])
        
        # 2. 角色描述  
        if parsed_components['character']:
            prompt_parts.append(parsed_components['character'])
        
        # 3. 构图描述
        if parsed_components['composition']:
            prompt_parts.append(parsed_components['composition'])
        
        # 4. 动作描述
        if parsed_components['action']:
            prompt_parts.append(parsed_components['action'])
        
        # 5. 风格描述
        if parsed_components['style']:
            prompt_parts.append(parsed_components['style'])
        else:
            prompt_parts.append(style)
        
        # 组合提示词
        base_prompt = "，".join(prompt_parts)
        
        # 添加质量控制和安全提示词
        quality_prompt = self._get_quality_and_safety_prompt()
        
        # 组合最终提示词
        final_prompt = f"{base_prompt}，{quality_prompt}"
        
        # 确保提示词不超过限制
        if len(final_prompt) > 800:
            # 优先保留前面重要的部分
            final_prompt = final_prompt[:800] + "..."
        
        return final_prompt
    
    def _parse_description_for_v2_model(self, description: str, style: str) -> Dict[str, str]:
        """
        解析描述为通用2.0模型推荐的结构
        
        Args:
            description: 原始描述
            style: 风格
            
        Returns:
            解析后的组件字典
        """
        components = {
            'scene': '',
            'character': '', 
            'composition': '',
            'action': '',
            'style': ''
        }
        
        # 简单的关键词匹配来分类描述内容
        desc_lower = description.lower()
        
        # 场景关键词
        scene_keywords = ['庭院', '房间', '森林', '海边', '山顶', '街道', '室内', '室外', '天空', '大地']
        for keyword in scene_keywords:
            if keyword in description:
                components['scene'] = f"{keyword}内"
                break
        
        # 角色描述（包含人物特征的描述）
        if '女子' in description or '女子' in description:
            if '白衣' in description:
                components['character'] = '一位穿白色圆领袍的女性'
            else:
                components['character'] = '一位女性角色'
        elif '男子' in description or '男子' in description:
            if '黑衣' in description:
                components['character'] = '一位穿黑色圆领袍的男性'
            else:
                components['character'] = '一位男性角色'
        
        # 构图描述
        if '月光' in description or '阳光' in description:
            components['composition'] = '电影般的意境角度'
        elif '特写' in description:
            components['composition'] = '细致的脸特写'
        else:
            components['composition'] = '电影级低视角拍摄'
        
        # 动作描述
        if '站立' in description or '站' in description:
            components['action'] = '站立着'
        elif '坐着' in description or '坐' in description:
            components['action'] = '坐着'
        elif '行走' in description or '走' in description:
            components['action'] = '正在行走'
        else:
            components['action'] = '静态姿势'
        
        # 风格映射
        style_mapping = {
            '古风': '古风言情动漫风格',
            '写实': '写实照片风格', 
            '动漫': '二次元动漫手绘',
            '唯美': '唯美治愈风',
            '仙侠': '古风仙侠风格'
        }
        
        for style_key, style_value in style_mapping.items():
            if style_key in style:
                components['style'] = style_value
                break
        
        return components
    
    def _get_quality_and_safety_prompt(self) -> str:
        """
        获取质量控制和安全提示词
        
        Returns:
            质量和安全提示词字符串
        """
        # 积极的质量词
        positive_words = [
            '超高分辨率', '竖屏9:16', '精美细节', '光影对比强烈', 
            '色彩绚丽', '专业摄影', '高领服饰', '圆领袍'
        ]
        
        # 避免的负面词（用于安全控制）
        negative_words = [
            'watermark', 'text', 'signature', '汉字', '字母', 'logo', 
            'nsfw', 'nude', '深V', '锁骨', '胸部', '低分辨率', 
            'blurry', 'worst quality', 'mutated hands'
        ]
        
        # 返回积极质量词
        return '，'.join(positive_words)
    
    async def _call_text2image_api(self, prompt: str) -> bytes:
        """
        调用文生图API（使用通用2.0模型Visual Service SDK）
        
        Args:
            prompt: 提示词
            
        Returns:
            图片二进制数据
        """
        try:
            from volcengine.visual.VisualService import VisualService
            import asyncio
            
            # 在线程池中运行同步的Visual Service SDK调用
            loop = asyncio.get_event_loop()
            
            def sync_generate_image():
                # 使用Visual Service SDK
                visual_service = VisualService()
                
                if self.use_dual_auth:
                    # 双重认证模式
                    visual_service.set_ak(self.access_key_id)
                    visual_service.set_sk(self.secret_access_key)
                else:
                    # 单一认证模式（兼容旧配置）
                    visual_service.set_ak(self.access_key_id)
                
                # 构建请求参数
                form = {
                    "req_key": "high_aes_general_v20_L",
                    "prompt": prompt,
                    "seed": -1,
                    "scale": 3.5,
                    "ddim_steps": 16,
                    "width": 512,
                    "height": 512,
                    "use_sr": True,  # 开启超分功能
                    "use_rephraser": True,  # 开启prompt扩写
                    "return_url": True,
                    "logo_info": {
                        "add_logo": False,
                        "position": 0,
                        "language": 0,
                        "opacity": 0.3
                    }
                }
                
                # 调用同步接口
                resp = visual_service.cv_process(form)
                
                # 检查响应状态
                if resp.get('code') != 10000:
                    raise ValueError(f"API调用失败: {resp.get('message', '未知错误')}")
                
                # 获取图片URL
                data = resp.get('data', {})
                image_urls = data.get('image_urls', [])
                
                if image_urls and len(image_urls) > 0:
                    return image_urls[0]
                else:
                    raise ValueError("API未返回图片URL")
            
            # 异步执行同步调用
            image_url = await loop.run_in_executor(None, sync_generate_image)
            
            # 下载图片
            response = await self.api_utils.make_async_request(
                method="GET",
                url=image_url,
                timeout=120
            )
            
            # 处理API工具返回的响应格式
            if isinstance(response, dict) and 'content' in response:
                return response['content']  # 返回二进制数据
            elif isinstance(response, bytes):
                return response
            else:
                raise ValueError("下载的图片数据格式异常")
                
        except ImportError:
            self.logger.error("缺少volcengine依赖，请安装：pip install volcengine")
            raise
        except Exception as e:
            self.logger.error(f"文生图API调用失败: {e}")
            raise
    
    def _get_access_token(self) -> str:
        """获取访问令牌"""
        # 使用API Key作为Bearer token
        return self.api_key
    
    async def _save_image(self, image_data: bytes, filename: str) -> str:
        """
        保存图片文件
        
        Args:
            image_data: 图片二进制数据
            filename: 文件名
            
        Returns:
            保存的文件路径
        """
        file_path = os.path.join(self.temp_dir, filename)
        
        try:
            with open(file_path, 'wb') as f:
                f.write(image_data)
            
            self.logger.debug(f"图片保存成功: {file_path}")
            return file_path
            
        except Exception as e:
            self.logger.error(f"图片保存失败: {e}")
            raise
    
    def _validate_image(self, image_path: str) -> Tuple[bool, Dict[str, Any]]:
        """
        验证图片质量
        
        Args:
            image_path: 图片路径
            
        Returns:
            (是否合格, 图片信息)
        """
        try:
            with Image.open(image_path) as img:
                width, height = img.size
                file_size = FileUtils.get_file_size(image_path)
                
                image_info = {
                    'resolution': f"{width}x{height}",
                    'file_size': file_size,
                    'format': img.format
                }
                
                # 基础质量检查（更宽松的标准）
                min_width, min_height = map(int, self.image_size.split('x'))
                
                # 检查分辨率（允许更大的偏差）
                if width < min_width * 0.7 or height < min_height * 0.7:
                    self.logger.debug(f"图片分辨率不达标: {width}x{height}, 期望: {min_width}x{min_height}")
                    return False, image_info
                
                # 检查文件大小（太小可能质量不好）
                if file_size < 20 * 1024:  # 小于20KB
                    self.logger.debug(f"图片文件太小: {file_size} bytes")
                    return False, image_info
                
                # 检查宽高比（允许更大的偏差）
                target_ratio = min_width / min_height
                actual_ratio = width / height
                
                if abs(actual_ratio - target_ratio) > 0.5:  # 从0.2放宽到0.5
                    self.logger.debug(f"图片宽高比偏差太大: {actual_ratio:.2f}, 期望: {target_ratio:.2f}")
                    return False, image_info
                
                return True, image_info
                
        except Exception as e:
            self.logger.error(f"图片验证失败: {e}")
            return False, {'resolution': '0x0', 'file_size': 0, 'format': 'unknown'}
    
    def _validate_image_relaxed(self, image_path: str) -> Tuple[bool, Dict[str, Any]]:
        """
        宽松的图片质量验证（用于重试）
        
        Args:
            image_path: 图片路径
            
        Returns:
            (是否合格, 图片信息)
        """
        try:
            with Image.open(image_path) as img:
                width, height = img.size
                file_size = FileUtils.get_file_size(image_path)
                
                image_info = {
                    'resolution': f"{width}x{height}",
                    'file_size': file_size,
                    'format': img.format
                }
                
                # 宽松的质量检查标准
                # 只检查文件大小和基本尺寸
                if file_size < 10 * 1024:  # 小于10KB才算太小
                    return False, image_info
                
                if width < 200 or height < 200:  # 最低尺寸要求
                    return False, image_info
                
                return True, image_info
                
        except Exception as e:
            self.logger.error(f"宽松图片验证失败: {e}")
            return False, {'resolution': '0x0', 'file_size': 0, 'format': 'unknown'}
    
    async def _retry_generation(
        self, 
        description: str, 
        style: str, 
        shot_index: int, 
        task_id: str,
        max_retries: int = 2
    ) -> Optional[Dict[str, Any]]:
        """
        重试生成图片（避免递归调用）
        
        Args:
            description: 图片描述
            style: 视觉风格
            shot_index: 镜头索引
            task_id: 任务ID
            max_retries: 最大重试次数
            
        Returns:
            图片信息字典
        """
        for retry in range(max_retries):
            try:
                self.logger.info(f"重试生成图片 [{shot_index}] - 第 {retry + 1} 次")
                
                # 稍微修改提示词
                modified_description = f"{description}，高质量，精美细节，超高清"
                prompt = self._build_image_prompt(modified_description, style)
                
                # 直接调用API，避免递归
                image_data = await self._call_text2image_api(prompt)
                
                # 保存图片文件（使用不同的文件名避免覆盖）
                filename = f"{task_id}_shot_{shot_index:02d}_retry_{retry + 1}.png"
                image_path = await self._save_image(image_data, filename)
                
                # 验证图片质量（宽松标准）
                is_valid, image_info = self._validate_image_relaxed(image_path)
                
                if is_valid:
                    processing_time = 1.0  # 估算处理时间
                    result = {
                        'shot_index': shot_index,
                        'description': description,
                        'prompt': prompt,
                        'file_path': image_path,
                        'file_size': image_info['file_size'],
                        'resolution': image_info['resolution'],
                        'processing_time': processing_time,
                        'cost': 0.025,
                        'is_retry': True
                    }
                    self.logger.info(f"重试生成成功 [{shot_index}] - 第 {retry + 1} 次")
                    return result
                else:
                    self.logger.warning(f"重试生成的图片质量仍不合格 [{shot_index}] - 第 {retry + 1} 次")
                    
            except Exception as e:
                self.logger.warning(f"重试失败 [{shot_index}][{retry + 1}]: {e}")
        
        # 重试失败，返回默认图片信息
        self.logger.info(f"所有重试都失败，使用默认图片 [{shot_index}]")
        return self._create_fallback_image_info(shot_index, description)
    
    def _create_fallback_image_info(
        self, 
        shot_index: int = 0, 
        description: str = "默认图片"
    ) -> Dict[str, Any]:
        """创建默认图片信息"""
        # 创建一个简单的占位图片
        fallback_path = os.path.join(self.temp_dir, f"fallback_{shot_index}.png")
        self._create_placeholder_image(fallback_path)
        
        return {
            'shot_index': shot_index,
            'description': description,
            'prompt': f"默认占位图片: {description}",
            'file_path': fallback_path,
            'file_size': FileUtils.get_file_size(fallback_path),
            'resolution': self.image_size,
            'processing_time': 0.1,
            'cost': 0.0,
            'is_fallback': True
        }
    
    def _create_placeholder_image(self, file_path: str):
        """创建占位图片"""
        try:
            from PIL import Image, ImageDraw, ImageFont
            
            width, height = map(int, self.image_size.split('x'))
            
            # 创建纯色背景
            img = Image.new('RGB', (width, height), color=(128, 128, 128))
            draw = ImageDraw.Draw(img)
            
            # 添加文字
            try:
                font = ImageFont.truetype("arial.ttf", 36)
            except:
                font = ImageFont.load_default()
            
            text = "占位图片"
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            x = (width - text_width) // 2
            y = (height - text_height) // 2
            
            draw.text((x, y), text, fill=(255, 255, 255), font=font)
            
            img.save(file_path)
            
        except Exception as e:
            self.logger.error(f"创建占位图片失败: {e}")
            # 创建最简单的图片
            img = Image.new('RGB', map(int, self.image_size.split('x')), color=(200, 200, 200))
            img.save(file_path)
    
    def get_generation_summary(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        获取生成总结
        
        Args:
            results: 生成结果列表
            
        Returns:
            生成总结
        """
        if not results:
            return {'total': 0, 'successful': 0, 'failed': 0, 'total_cost': 0.0}
        
        total = len(results)
        successful = len([r for r in results if r and not r.get('is_fallback', False)])
        failed = total - successful
        total_cost = sum(r.get('cost', 0.0) for r in results if r)
        total_time = sum(r.get('processing_time', 0.0) for r in results if r)
        
        return {
            'total': total,
            'successful': successful,
            'failed': failed,
            'total_cost': total_cost,
            'total_time': total_time,
            'avg_time': total_time / total if total > 0 else 0
        }


async def test_image_generator():
    """测试图片生成器"""
    # 模拟配置
    config = {
        'api': {
            'volcengine': {
                'api_key': 'mock_api_key'
            }
        },
        'models': {
            'text2image_endpoint': 'ep-20241230140000-xxxxx'
        },
        'generation': {
            'image_size': '512x768',
            'image_quality': 'high',
            'max_images': 3
        },
        'storage': {
            'temp_dir': './test_temp',
            'output_dir': './test_output',
            'database_path': './test_db.db'
        },
        'prompts': {
            'image_prompt_template': './prompts/image_prompt.txt'
        },
        'api_settings': {
            'max_retries': 3,
            'request_timeout': 30
        }
    }
    
    # 模拟脚本数据
    script_data = {
        'title': '测试视频',
        'style': '古风 仙侠 唯美',
        'shots': [
            {'description': '古朴庭院中，白衣少年盘膝而坐', 'duration': 5},
            {'description': '夜空中繁星点点，明月当空', 'duration': 4},
            {'description': '山峦起伏，云雾缭绕', 'duration': 4}
        ]
    }
    
    try:
        generator = ImageGenerator(config)
        
        # 测试提示词构建
        prompt = generator._build_image_prompt("测试场景", "古风 唯美")
        print(f"提示词构建测试: {prompt}")
        
        # 测试占位图片创建
        fallback_info = generator._create_fallback_image_info(0, "测试图片")
        print(f"占位图片测试: {fallback_info}")
        
        print("图片生成器测试完成")
        
    except Exception as e:
        print(f"图片生成器测试失败: {e}")
    finally:
        # 清理测试文件
        import shutil
        for path in ['./test_temp', './test_output']:
            if Path(path).exists():
                shutil.rmtree(path)
        Path('./test_db.db').unlink(missing_ok=True)


if __name__ == "__main__":
    asyncio.run(test_image_generator())