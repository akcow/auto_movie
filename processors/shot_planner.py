#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
智能分镜决策器
基于口播文案智能决策生成分镜脚本
"""

import json
import re
import math
from typing import Dict, Any, List, Optional, Tuple
from utils.logger import get_logger


class ShotPlanner:
    """智能分镜决策器"""
    
    def __init__(self, llm_client, config: Dict[str, Any]):
        """
        初始化分镜决策器
        
        Args:
            llm_client: LLM客户端实例
            config: 配置信息
        """
        self.llm_client = llm_client
        self.config = config
        self.logger = get_logger(self.__class__.__name__)
        
        # 从配置中获取参数
        self.shot_config = config.get('shot_planning', {})
        self.min_shots = self.shot_config.get('min_shots', 8)
        self.max_shots = self.shot_config.get('max_shots', 15)
        self.dynamic_shot_count = self.shot_config.get('dynamic_shot_count', 3)  # 前3个为动态视频
        self.min_shot_duration = self.shot_config.get('min_shot_duration', 8)  # 最短8秒
        self.max_shot_duration = self.shot_config.get('max_shot_duration', 25)  # 最长25秒
        
    async def plan_shots(
        self, 
        narration_data: Dict[str, Any], 
        target_duration: int
    ) -> Dict[str, Any]:
        """
        基于口播文案智能决策分镜方案
        
        Args:
            narration_data: 口播文案数据
            target_duration: 目标视频时长（秒）
            
        Returns:
            包含分镜脚本的字典
        """
        try:
            self.logger.info(f"开始生成分镜脚本，目标时长: {target_duration}秒")
            
            # 计算最佳分镜数量
            optimal_shot_count = self._calculate_optimal_shot_count(narration_data, target_duration)
            
            # 生成分镜脚本
            shot_script = await self._generate_shot_script(
                narration_data, target_duration, optimal_shot_count
            )
            
            # 优化分镜时长分配
            optimized_script = self._optimize_shot_durations(shot_script, target_duration)
            
            # 验证分镜脚本
            validated_script = self._validate_shot_script(optimized_script)
            
            self.logger.info(f"分镜脚本生成完成，共{len(validated_script['shots'])}个分镜")
            return validated_script
            
        except Exception as e:
            self.logger.error(f"生成分镜脚本失败: {e}")
            raise
    
    def _calculate_optimal_shot_count(self, narration_data: Dict[str, Any], target_duration: int) -> int:
        """
        计算最佳分镜数量
        """
        # 基础计算：根据时长和最小分镜时长
        base_shot_count = target_duration // self.min_shot_duration
        
        # 根据文案段落数量调整
        segments = narration_data.get('segments', [])
        segment_based_count = len(segments)
        
        # 综合考虑，取平均值
        optimal_count = (base_shot_count + segment_based_count) // 2
        
        # 确保在合理范围内
        optimal_count = max(self.min_shots, min(self.max_shots, optimal_count))
        
        self.logger.info(f"计算最佳分镜数量: {optimal_count} (基于时长: {base_shot_count}, 基于段落: {segment_based_count})")
        return optimal_count
    
    async def _generate_shot_script(
        self, 
        narration_data: Dict[str, Any], 
        target_duration: int, 
        shot_count: int
    ) -> Dict[str, Any]:
        """
        生成分镜脚本
        """
        narration = narration_data.get('narration', '')
        title = narration_data.get('title', '小说视频')
        key_points = narration_data.get('key_points', [])
        
        prompt = self._build_shot_script_prompt(
            narration, title, key_points, target_duration, shot_count
        )
        
        # 调用LLM生成分镜脚本
        response = await self.llm_client.generate_text(prompt)
        
        # 解析响应
        shot_script = self._parse_shot_script_response(response, narration_data, target_duration)
        
        return shot_script
    
    def _build_shot_script_prompt(
        self, 
        narration: str, 
        title: str, 
        key_points: List[str], 
        target_duration: int, 
        shot_count: int
    ) -> str:
        """构建分镜脚本生成的提示词"""
        
        dynamic_duration = 15  # 前3个动态分镜总共15秒
        static_duration = target_duration - dynamic_duration
        
        prompt = f"""你是一个专业的视频分镜师，请为以下视频解说创作分镜脚本。

视频信息：
标题：{title}
总时长：{target_duration}秒
目标分镜数：{shot_count}个

口播文案：
{narration}

关键要点：
{json.dumps(key_points, ensure_ascii=False, indent=2) if key_points else "无"}

分镜要求：
1. 前{self.dynamic_shot_count}个分镜为动态视频分镜（每个5秒，共15秒）
2. 其余分镜为静态图片分镜（总计{static_duration}秒）
3. 每个分镜都要有详细的视觉描述
4. 分镜内容要与口播文案紧密对应
5. 静态分镜时长在{self.min_shot_duration}-{self.max_shot_duration}秒之间

请返回JSON格式的分镜脚本：
{{
    "title": "视频标题",
    "total_duration": {target_duration},
    "shot_count": {shot_count},
    "shots": [
        {{
            "index": 1,
            "type": "dynamic",  // "dynamic" 或 "static"
            "duration": 5,
            "narration_text": "对应的口播文案片段",
            "visual_description": "详细的视觉场景描述",
            "scene_elements": ["元素1", "元素2", "元素3"],
            "mood": "画面情感氛围",
            "camera_angle": "机位角度建议",
            "lighting": "光线效果",
            "style_notes": "风格说明"
        }},
        // 更多分镜...
    ],
    "style_consistency": "整体风格一致性说明",
    "narrative_flow": "叙事节奏说明"
}}

注意事项：
- 确保每个分镜的视觉描述具体生动
- 前{self.dynamic_shot_count}个分镜要适合生成动态视频
- 静态分镜要有丰富的视觉层次
- 分镜切换要自然流畅
- 总时长必须严格等于{target_duration}秒"""

        return prompt
    
    def _parse_shot_script_response(
        self, 
        response: str, 
        narration_data: Dict[str, Any], 
        target_duration: int
    ) -> Dict[str, Any]:
        """
        解析LLM返回的分镜脚本响应
        """
        try:
            # 尝试解析JSON格式响应
            if response.strip().startswith('{'):
                script_data = json.loads(response)
                return script_data
            
            # 如果不是标准JSON，尝试提取和构建
            return self._extract_shot_info_from_text(response, narration_data, target_duration)
            
        except Exception as e:
            self.logger.error(f"解析分镜脚本响应失败: {e}")
            # 生成默认分镜脚本
            return self._generate_default_shot_script(narration_data, target_duration)
    
    def _extract_shot_info_from_text(
        self, 
        response: str, 
        narration_data: Dict[str, Any], 
        target_duration: int
    ) -> Dict[str, Any]:
        """
        从文本中提取分镜信息
        """
        shots = []
        lines = response.split('\n')
        current_shot = {}
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # 识别分镜编号
            if re.match(r'^\d+[\.、]', line):
                if current_shot:
                    shots.append(current_shot)
                current_shot = {
                    'index': len(shots) + 1,
                    'type': 'dynamic' if len(shots) < self.dynamic_shot_count else 'static',
                    'duration': 5 if len(shots) < self.dynamic_shot_count else 15,
                    'visual_description': line,
                    'narration_text': '',
                    'scene_elements': [],
                    'mood': '生动自然',
                    'camera_angle': '平视',
                    'lighting': '自然光',
                    'style_notes': '电影化风格'
                }
            elif current_shot and line:
                current_shot['visual_description'] += ' ' + line
        
        if current_shot:
            shots.append(current_shot)
        
        # 构建完整的脚本数据
        return {
            'title': narration_data.get('title', '小说视频'),
            'total_duration': target_duration,
            'shot_count': len(shots),
            'shots': shots,
            'style_consistency': '保持一致的视觉风格',
            'narrative_flow': '流畅的叙事节奏'
        }
    
    def _generate_default_shot_script(
        self, 
        narration_data: Dict[str, Any], 
        target_duration: int
    ) -> Dict[str, Any]:
        """
        生成默认的分镜脚本
        """
        narration = narration_data.get('narration', '')
        segments = narration_data.get('segments', [])
        
        # 如果没有预分段，按长度分段
        if not segments:
            segment_length = len(narration) // 8
            segments = []
            for i in range(0, len(narration), segment_length):
                segment_text = narration[i:i+segment_length]
                if segment_text.strip():
                    segments.append({
                        'content': segment_text,
                        'word_count': len(segment_text)
                    })
        
        shots = []
        dynamic_duration = 5
        remaining_duration = target_duration - (self.dynamic_shot_count * dynamic_duration)
        static_shot_count = len(segments) - self.dynamic_shot_count
        static_duration_per_shot = remaining_duration // max(static_shot_count, 1)
        
        for i, segment in enumerate(segments[:self.min_shots]):
            is_dynamic = i < self.dynamic_shot_count
            
            shot = {
                'index': i + 1,
                'type': 'dynamic' if is_dynamic else 'static',
                'duration': dynamic_duration if is_dynamic else static_duration_per_shot,
                'narration_text': segment.get('content', ''),
                'visual_description': f"第{i+1}个场景的视觉描述",
                'scene_elements': ['主要元素', '背景', '氛围'],
                'mood': '生动自然',
                'camera_angle': '平视',
                'lighting': '自然光',
                'style_notes': '电影化风格'
            }
            shots.append(shot)
        
        return {
            'title': narration_data.get('title', '小说视频'),
            'total_duration': target_duration,
            'shot_count': len(shots),
            'shots': shots,
            'style_consistency': '保持一致的视觉风格',
            'narrative_flow': '流畅的叙事节奏'
        }
    
    def _optimize_shot_durations(self, script_data: Dict[str, Any], target_duration: int) -> Dict[str, Any]:
        """
        优化分镜时长分配
        """
        shots = script_data.get('shots', [])
        if not shots:
            return script_data
        
        # 计算当前总时长
        current_total = sum(shot.get('duration', 0) for shot in shots)
        
        # 如果时长差异较大，需要调整
        if abs(current_total - target_duration) > 5:  # 超过5秒差异
            # 重新分配时长
            dynamic_shots = [shot for shot in shots if shot.get('type') == 'dynamic']
            static_shots = [shot for shot in shots if shot.get('type') == 'static']
            
            # 动态分镜固定为5秒
            dynamic_total = len(dynamic_shots) * 5
            for shot in dynamic_shots:
                shot['duration'] = 5
            
            # 静态分镜均分剩余时长
            static_total = target_duration - dynamic_total
            if static_shots:
                static_duration_per_shot = static_total // len(static_shots)
                static_remainder = static_total % len(static_shots)
                
                for i, shot in enumerate(static_shots):
                    base_duration = static_duration_per_shot
                    # 将余数分配给前几个分镜
                    if i < static_remainder:
                        base_duration += 1
                    
                    # 确保在合理范围内
                    shot['duration'] = max(
                        self.min_shot_duration, 
                        min(self.max_shot_duration, base_duration)
                    )
        
        # 更新总时长
        script_data['total_duration'] = sum(shot.get('duration', 0) for shot in shots)
        
        return script_data
    
    def _validate_shot_script(self, script_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证分镜脚本的完整性和合理性
        """
        shots = script_data.get('shots', [])
        
        # 确保每个分镜都有必要字段
        for i, shot in enumerate(shots):
            if 'index' not in shot:
                shot['index'] = i + 1
            
            if 'type' not in shot:
                shot['type'] = 'dynamic' if i < self.dynamic_shot_count else 'static'
            
            if 'duration' not in shot or shot['duration'] <= 0:
                shot['duration'] = 5 if shot['type'] == 'dynamic' else 15
            
            # 确保有基本的描述信息
            default_fields = {
                'narration_text': f"第{i+1}段口播内容",
                'visual_description': f"第{i+1}个场景描述",
                'scene_elements': ['主要场景元素'],
                'mood': '自然',
                'camera_angle': '平视',
                'lighting': '自然光',
                'style_notes': '电影风格'
            }
            
            for field, default_value in default_fields.items():
                if field not in shot or not shot[field]:
                    shot[field] = default_value
        
        # 更新统计信息
        script_data['shot_count'] = len(shots)
        script_data['total_duration'] = sum(shot.get('duration', 0) for shot in shots)
        
        # 添加分镜类型统计
        dynamic_count = len([s for s in shots if s.get('type') == 'dynamic'])
        static_count = len([s for s in shots if s.get('type') == 'static'])
        
        script_data['shot_statistics'] = {
            'total_shots': len(shots),
            'dynamic_shots': dynamic_count,
            'static_shots': static_count,
            'average_shot_duration': script_data['total_duration'] / max(len(shots), 1)
        }
        
        return script_data
    
    def get_shot_script_summary(self, script_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取分镜脚本摘要信息
        """
        shots = script_data.get('shots', [])
        
        return {
            'total_shots': len(shots),
            'dynamic_shots': len([s for s in shots if s.get('type') == 'dynamic']),
            'static_shots': len([s for s in shots if s.get('type') == 'static']),
            'total_duration': script_data.get('total_duration', 0),
            'average_shot_duration': script_data.get('total_duration', 0) / max(len(shots), 1),
            'duration_range': {
                'min': min(shot.get('duration', 0) for shot in shots) if shots else 0,
                'max': max(shot.get('duration', 0) for shot in shots) if shots else 0
            }
        }
    
    async def refine_shot_descriptions(self, script_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        细化分镜描述，提供更详细的视觉指导
        """
        shots = script_data.get('shots', [])
        
        for shot in shots:
            if shot.get('visual_description') and len(shot['visual_description']) < 50:
                # 如果描述过于简单，进行扩展
                enhanced_desc = await self._enhance_shot_description(shot)
                shot['visual_description'] = enhanced_desc
        
        return script_data
    
    async def _enhance_shot_description(self, shot: Dict[str, Any]) -> str:
        """
        增强单个分镜的视觉描述
        """
        current_desc = shot.get('visual_description', '')
        shot_type = shot.get('type', 'static')
        narration = shot.get('narration_text', '')
        
        prompt = f"""请为以下视频分镜提供更详细的视觉描述：

分镜类型：{shot_type}
当前描述：{current_desc}
对应口播：{narration}

请提供一个详细的视觉描述，包括：
1. 具体的场景设定
2. 人物/物体的位置和状态
3. 色彩和光线效果
4. 氛围和情感表达
5. {'运动轨迹和动作' if shot_type == 'dynamic' else '构图和视觉焦点'}

描述要适合用于AI图像生成，语言简洁明确："""

        response = await self.llm_client.generate_text(prompt)
        return response.strip()