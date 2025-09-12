#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LLM客户端模块
负责调用火山引擎豆包大语言模型，生成视频分镜脚本
"""

import json
import re
import asyncio
from typing import Dict, List, Any, Optional
import requests
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from utils.logger import LoggerMixin
from utils.api_utils import APIUtils, cost_tracker
from utils.file_utils import FileUtils


class LLMClient(LoggerMixin):
    """LLM客户端"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化LLM客户端
        
        Args:
            config: 配置字典
        """
        self.config = config
        self.api_config = config.get('api', {}).get('volcengine', {})
        self.models_config = config.get('models', {})
        self.generation_config = config.get('generation', {})
        
        # API配置（按照官方项目模式）
        self.api_key = self.api_config.get('api_key')
        self.region = self.api_config.get('region', 'cn-beijing')
        self.endpoint = self.models_config.get('llm_endpoint')
        
        if not all([self.api_key, self.endpoint]):
            raise ValueError("LLM API配置不完整，请在config.yaml中配置api_key和llm_endpoint")
        
        # API工具
        self.api_utils = APIUtils(config)
        
        # 提示词模板路径
        self.storyboard_template_path = config.get('prompts', {}).get('storyboard_template', './prompts/storyboard.txt')
        
        # 生成参数
        self.max_images = self.generation_config.get('max_images', 15)
        self.video_segments = self.generation_config.get('video_segments', 3)
        self.video_duration = self.generation_config.get('video_duration', 5)
    
    async def generate_text(self, prompt: str, system_prompt: str = None) -> str:
        """
        通用的文本生成方法
        
        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词（可选）
            
        Returns:
            生成的文本内容
        """
        try:
            # 使用默认系统提示词
            if system_prompt is None:
                system_prompt = "你是一个专业的AI助手，能够根据用户需求生成高质量的内容。"
            
            # 构建请求数据
            request_data = {
                "model": self.endpoint,
                "messages": [
                    {
                        "role": "system", 
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.7,
                "max_tokens": 2048,
                "top_p": 0.9
            }
            
            # 构建请求头
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            # API URL
            api_url = f"https://ark.cn-beijing.volces.com/api/v3/chat/completions"
            
            # 发起请求，增加超时时间解决网络问题
            response = self.api_utils.make_request(
                method="POST",
                url=api_url,
                headers=headers,
                json_data=request_data,
                timeout=360  # 增加到360秒，支持分镜脚本生成等复杂任务
            )
            
            # 解析响应
            if response and 'choices' in response and len(response['choices']) > 0:
                content = response['choices'][0]['message']['content']
                
                # 记录成本
                self._track_cost(response)
                
                return content.strip()
            else:
                raise ValueError("API响应格式无效")
                
        except Exception as e:
            self.logger.error(f"文本生成失败: {e}")
            raise
    
    def generate_script(self, text_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成分镜脚本
        
        Args:
            text_data: 文本解析结果
            
        Returns:
            生成的脚本数据
        """
        try:
            self.logger.info(f"开始生成分镜脚本: {text_data['title']}")
            
            # 加载提示词模板
            prompt = self._build_prompt(text_data)
            
            # 调用LLM API
            response = self._call_llm_api(prompt)
            
            # 解析响应
            script_data = self._parse_llm_response(response)
            
            # 验证脚本格式
            validated_script = self._validate_script(script_data)
            
            # 记录成本
            self._track_cost(response)
            
            self.logger.info(f"脚本生成成功: {len(validated_script['shots'])} 个镜头")
            return validated_script
            
        except Exception as e:
            self.logger.error(f"脚本生成失败: {e}")
            raise
    
    def _build_prompt(self, text_data: Dict[str, Any]) -> str:
        """
        构建提示词
        
        Args:
            text_data: 文本数据
            
        Returns:
            完整的提示词
        """
        try:
            # 加载提示词模板
            if FileUtils.path_exists(self.storyboard_template_path):
                template = FileUtils.read_text_file(self.storyboard_template_path)
            else:
                # 使用内置模板
                template = self._get_default_storyboard_template()
            
            # 替换变量
            prompt = template.format(
                title=text_data['title'],
                content=text_data['content'][:2000],  # 限制长度避免超过token限制
                max_images=self.max_images,
                video_segments=self.video_segments,
                video_duration=self.video_duration,
                word_count=text_data['word_count']
            )
            
            return prompt
            
        except Exception as e:
            self.logger.error(f"构建提示词失败: {e}")
            return self._get_default_storyboard_template().format(
                title=text_data.get('title', '未知'),
                content=text_data.get('content', '')[:2000],
                max_images=self.max_images,
                video_segments=self.video_segments,
                video_duration=self.video_duration,
                word_count=text_data.get('word_count', 0)
            )
    
    def _get_default_storyboard_template(self) -> str:
        """获取默认分镜脚本提示词模板"""
        return """你是一名专业的短视频导演，需要根据小说片段生成2-4分钟竖屏短视频的详细分镜脚本。

请根据以下小说内容生成分镜脚本：

标题：{title}
内容：{content}
字数：{word_count}

要求：
1. 输出严格的JSON格式，必须包含以下字段：
   - title: 视频标题
   - summary: 内容摘要(50字以内)
   - style: 视觉风格(5个中文关键词，空格分隔，如"古风 玄幻 唯美 仙侠 国漫")
   - shots: 分镜列表
   - narration: 旁白文本(适合语音合成，流畅自然)

2. shots数组要求：
   - 总共{max_images}个镜头
   - 前{video_segments}个镜头type设为"video"，duration设为{video_duration}秒
   - 其余镜头type设为"image"，duration设为3-4秒
   - 每个镜头包含：type, description, duration
   - description要详细描述画面内容，适合AI绘图

3. 内容要求：
   - 风格：爽文、快节奏、有冲击力
   - 画面：竖屏9:16比例，适合短视频
   - 禁止：NSFW、政治敏感、暴力血腥内容
   - 语言：简洁明快，适合年轻观众

4. JSON格式示例：
```json
{{
  "title": "第一章 觉醒",
  "summary": "少年意外获得神秘力量，踏上修仙之路",
  "style": "古风 仙侠 玄幻 唯美 国漫",
  "shots": [
    {{"type": "video", "description": "破旧院落中，白衣少年盘膝而坐，周身金光涌现", "duration": 5}},
    {{"type": "image", "description": "夜空中繁星闪烁，一道流光划过苍穹", "duration": 4}}
  ],
  "narration": "那一夜，星辰坠落，少年的命运从此改变。神秘的力量在他体内觉醒，一场惊天动地的冒险即将开始。"
}}
```

请严格按照JSON格式输出，不要添加任何其他内容："""
    
    def _call_llm_api(self, prompt: str) -> Dict[str, Any]:
        """
        调用LLM API
        
        Args:
            prompt: 提示词
            
        Returns:
            API响应
        """
        # 构建请求数据
        request_data = {
            "model": self.endpoint,
            "messages": [
                {
                    "role": "system", 
                    "content": "你是专业的短视频分镜脚本创作者，专注于将小说内容转化为吸引人的视频脚本。"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.7,
            "max_tokens": 2048,
            "top_p": 0.9
        }
        
        # 构建请求头（使用API Key认证）
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # 火山引擎ARK API URL
        api_url = f"https://ark.cn-beijing.volces.com/api/v3/chat/completions"
        
        try:
            # 发起请求
            response = self.api_utils.make_request(
                method="POST",
                url=api_url,
                headers=headers,
                json_data=request_data,
                timeout=360  # LLM调用超时时间为360秒，支持分镜脚本生成等复杂任务
            )
            
            return response
            
        except Exception as e:
            self.logger.error(f"LLM API调用失败: {e}")
            raise
    
    def _get_access_token(self) -> str:
        """
        获取访问令牌
        
        Returns:
            访问令牌
        """
        # 使用API Key作为Bearer token
        return self.api_key
    
    def _parse_llm_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析LLM响应
        
        Args:
            response: API响应
            
        Returns:
            解析后的脚本数据
        """
        try:
            # 提取生成的内容
            if 'choices' in response and len(response['choices']) > 0:
                content = response['choices'][0]['message']['content']
            else:
                raise ValueError("LLM响应格式异常")
            
            # 提取JSON部分
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # 尝试直接解析整个内容
                json_str = content.strip()
            
            # 解析JSON
            script_data = json.loads(json_str)
            
            return script_data
            
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON解析失败: {e}")
            self.logger.debug(f"原始内容: {content}")
            # 返回默认脚本
            return self._get_fallback_script()
        except Exception as e:
            self.logger.error(f"响应解析失败: {e}")
            return self._get_fallback_script()
    
    def _validate_script_format(self, script_data: Dict[str, Any]) -> bool:
        """
        验证脚本格式
        
        Args:
            script_data: 脚本数据
            
        Returns:
            是否格式正确
        """
        if not isinstance(script_data, dict):
            return False
        
        required_fields = ['title', 'shots', 'narration']
        for field in required_fields:
            if field not in script_data:
                return False
        
        # 验证shots格式
        shots = script_data['shots']
        if not isinstance(shots, list) or len(shots) == 0:
            return False
        
        for shot in shots:
            if not isinstance(shot, dict):
                return False
            if 'description' not in shot or 'duration' not in shot:
                return False
        
        return True
    
    def _validate_script(self, script_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证并修复脚本格式
        
        Args:
            script_data: 原始脚本数据
            
        Returns:
            验证后的脚本数据
        """
        # 确保必要字段存在
        validated = {
            'title': script_data.get('title', '未命名'),
            'summary': script_data.get('summary', '精彩内容即将呈现'),
            'style': script_data.get('style', '现代 都市 青春 励志 温馨'),
            'shots': [],
            'narration': script_data.get('narration', '这是一个精彩的故事。')
        }
        
        # 验证分镜列表
        shots = script_data.get('shots', [])
        if not shots:
            # 生成默认分镜
            shots = self._generate_default_shots()
        
        # 确保前几个是视频，其余是图片
        for i, shot in enumerate(shots[:self.max_images]):
            shot_type = "video" if i < self.video_segments else "image"
            duration = self.video_duration if shot_type == "video" else 4
            
            validated_shot = {
                'type': shot_type,
                'description': shot.get('description', f'第{i+1}个场景'),
                'duration': shot.get('duration', duration)
            }
            
            validated['shots'].append(validated_shot)
        
        # 确保总时长合理
        total_duration = sum(shot['duration'] for shot in validated['shots'])
        target_duration = 120  # 2分钟
        
        if abs(total_duration - target_duration) > 30:  # 误差超过30秒
            # 调整时长
            adjustment_factor = target_duration / total_duration
            for shot in validated['shots']:
                shot['duration'] = int(shot['duration'] * adjustment_factor)
        
        self.logger.info(f"脚本验证完成: {len(validated['shots'])} 个镜头, 总时长 {sum(shot['duration'] for shot in validated['shots'])} 秒")
        return validated
    
    def _generate_default_shots(self) -> List[Dict[str, Any]]:
        """生成默认分镜"""
        default_shots = [
            {"type": "video", "description": "主角出现，神情专注", "duration": 5},
            {"type": "video", "description": "环境全景，氛围营造", "duration": 5}, 
            {"type": "video", "description": "关键动作特写", "duration": 5},
        ]
        
        # 添加静态图片
        image_descriptions = [
            "背景环境远景", "人物表情特写", "重要物品展示", "场景转换过渡",
            "情绪渲染画面", "故事高潮画面", "结局暗示画面"
        ]
        
        for i, desc in enumerate(image_descriptions):
            if len(default_shots) >= self.max_images:
                break
            default_shots.append({
                "type": "image", 
                "description": desc,
                "duration": 4
            })
        
        return default_shots
    
    def _get_fallback_script(self) -> Dict[str, Any]:
        """获取备用脚本"""
        return {
            'title': '精彩故事',
            'summary': '一个引人入胜的故事即将开始',
            'style': '现代 都市 青春 励志 温馨',
            'shots': self._generate_default_shots(),
            'narration': '这是一个精彩的故事，让我们一起来感受其中的魅力。'
        }
    
    def _track_cost(self, response: Dict[str, Any]):
        """
        跟踪API成本
        
        Args:
            response: API响应
        """
        try:
            # 从响应中提取token使用信息
            usage = response.get('usage', {})
            total_tokens = usage.get('total_tokens', 800)  # 默认估算
            
            # 豆包API成本: 约0.012元/1k tokens
            cost = (total_tokens / 1000) * 0.012
            
            # 记录成本
            cost_tracker.add_cost('llm', cost, 1)
            
            self.logger.debug(f"LLM调用成本: ¥{cost:.4f} (tokens: {total_tokens})")
            
        except Exception as e:
            self.logger.warning(f"成本跟踪失败: {e}")


async def test_llm_client():
    """测试LLM客户端"""
    # 模拟配置
    config = {
        'api': {
            'volcengine': {
                'api_key': 'test_api_key',
                'region': 'cn-beijing'
            }
        },
        'models': {
            'llm_endpoint': 'ep-20241230140000-xxxxx'
        },
        'generation': {
            'max_images': 15,
            'video_segments': 3,
            'video_duration': 5
        },
        'prompts': {
            'storyboard_template': './prompts/storyboard.txt'
        },
        'api_settings': {
            'max_retries': 3,
            'request_timeout': 30
        }
    }
    
    # 模拟文本数据
    text_data = {
        'title': '测试章节',
        'content': '这是一个测试的小说内容。主角是一个年轻人，他在一个神秘的世界中冒险。',
        'word_count': 100
    }
    
    try:
        client = LLMClient(config)
        
        # 测试默认脚本生成
        fallback_script = client._get_fallback_script()
        print("备用脚本:", json.dumps(fallback_script, indent=2, ensure_ascii=False))
        
        # 测试脚本验证
        test_script = {
            'title': '测试',
            'shots': [
                {'type': 'video', 'description': '测试场景', 'duration': 5}
            ]
        }
        validated = client._validate_script(test_script)
        print("验证后脚本:", json.dumps(validated, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"测试失败: {e}")


if __name__ == "__main__":
    import re
    asyncio.run(test_llm_client())