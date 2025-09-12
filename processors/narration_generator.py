#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
口播文案生成器
基于小说内容生成适合视频解说的完整口播文案
"""

import json
import re
from typing import Dict, Any, List, Optional
from utils.logger import get_logger


class NarrationGenerator:
    """口播文案生成器"""
    
    def __init__(self, llm_client, config: Dict[str, Any]):
        """
        初始化口播文案生成器
        
        Args:
            llm_client: LLM客户端实例
            config: 配置信息
        """
        self.llm_client = llm_client
        self.config = config
        self.logger = get_logger(self.__class__.__name__)
        
        # 从配置中获取参数
        self.narration_config = config.get('narration', {})
        self.target_wpm = self.narration_config.get('words_per_minute', 150)  # 每分钟词数
        self.style = self.narration_config.get('style', 'engaging')  # 解说风格
        
    async def generate_narration(
        self, 
        novel_content: str, 
        target_duration: int,
        novel_title: str = ""
    ) -> Dict[str, Any]:
        """
        基于小说内容生成完整口播文案
        
        Args:
            novel_content: 小说文本内容
            target_duration: 目标视频时长（秒）
            novel_title: 小说标题
            
        Returns:
            包含口播文案和相关信息的字典
        """
        try:
            self.logger.info(f"开始生成口播文案，目标时长: {target_duration}秒")
            
            # 计算目标字数（中文按字符计算，英文按单词计算）
            target_minutes = target_duration / 60
            target_word_count = int(target_minutes * self.target_wpm)
            
            # 预处理小说内容
            processed_content = self._preprocess_novel_content(novel_content)
            
            # 生成口播文案
            narration_result = await self._generate_narration_content(
                processed_content, target_word_count, target_duration, novel_title
            )
            
            # 验证和优化文案
            optimized_result = await self._optimize_narration(narration_result, target_duration)
            
            self.logger.info("口播文案生成完成")
            return optimized_result
            
        except Exception as e:
            self.logger.error(f"生成口播文案失败: {e}")
            raise
    
    def _preprocess_novel_content(self, content: str) -> str:
        """
        预处理小说内容，提取关键信息
        
        Args:
            content: 原始小说内容
            
        Returns:
            处理后的内容摘要
        """
        # 清理文本
        content = re.sub(r'\s+', ' ', content.strip())
        
        # 如果内容过长，截取关键部分
        max_input_length = self.narration_config.get('max_input_length', 3000)
        if len(content) > max_input_length:
            # 取开头、中间、结尾各1/3
            section_length = max_input_length // 3
            beginning = content[:section_length]
            middle_start = len(content) // 2 - section_length // 2
            middle = content[middle_start:middle_start + section_length]
            ending = content[-section_length:]
            content = f"{beginning}...(中间省略)...{middle}...(中间省略)...{ending}"
        
        return content
    
    async def _generate_narration_content(
        self, 
        content: str, 
        target_word_count: int, 
        target_duration: int,
        novel_title: str
    ) -> Dict[str, Any]:
        """
        生成口播文案内容
        """
        prompt = self._build_narration_prompt(content, target_word_count, target_duration, novel_title)
        
        # 调用LLM生成文案
        response = await self.llm_client.generate_text(prompt)
        
        # 解析响应
        narration_data = self._parse_narration_response(response)
        
        return narration_data
    
    def _build_narration_prompt(
        self, 
        content: str, 
        target_word_count: int, 
        target_duration: int,
        novel_title: str
    ) -> str:
        """构建用于生成口播文案的提示词"""
        
        style_descriptions = {
            'engaging': '生动有趣、富有感染力',
            'documentary': '客观严谨、纪录片风格',
            'storytelling': '故事性强、娓娓道来',
            'casual': '轻松随意、贴近观众'
        }
        
        style_desc = style_descriptions.get(self.style, '生动有趣')
        
        prompt = f"""你是一个专业的视频解说文案创作者，请基于以下小说内容创作一个视频解说文案。

小说标题：{novel_title}
小说内容：
{content}

创作要求：
1. 文案风格：{style_desc}
2. 目标时长：{target_duration}秒（约{target_duration//60}分{target_duration%60}秒）
3. 目标字数：约{target_word_count}字
4. 语言节奏：适合口播，句子长短搭配合理
5. 内容要求：
   - 突出小说的核心情节和关键人物
   - 保持悬念感，吸引观众
   - 逻辑清晰，层次分明
   - 适合配合视觉画面

请返回JSON格式的结果：
{{
    "title": "视频标题",
    "narration": "完整的口播文案",
    "summary": "内容概要",
    "key_points": ["关键点1", "关键点2", "关键点3"],
    "estimated_duration": 预估时长秒数,
    "word_count": 实际字数
}}

注意：文案要自然流畅，避免生硬的转折，确保适合语音合成和视频节奏。"""

        return prompt
    
    def _parse_narration_response(self, response: str) -> Dict[str, Any]:
        """
        解析LLM返回的口播文案响应
        """
        try:
            # 清理响应中的控制字符
            cleaned_response = self._clean_response_text(response)
            
            # 尝试解析JSON格式响应
            if cleaned_response.strip().startswith('{'):
                try:
                    return json.loads(cleaned_response)
                except json.JSONDecodeError as e:
                    self.logger.warning(f"JSON解析失败，转为文本解析: {e}")
            
            # 如果不是JSON格式，尝试提取关键信息
            lines = cleaned_response.strip().split('\n')
            narration_text = ""
            
            # 查找主要文案内容
            in_narration = False
            for line in lines:
                if any(keyword in line.lower() for keyword in ['文案', 'narration', '解说']):
                    in_narration = True
                    continue
                if in_narration and line.strip():
                    narration_text += line.strip() + " "
            
            if not narration_text:
                narration_text = cleaned_response.strip()
            
            # 构建结果
            result = {
                "title": "小说视频解说",
                "narration": narration_text.strip(),
                "summary": "基于小说内容生成的解说文案",
                "key_points": ["小说情节", "人物关系", "关键转折"],
                "estimated_duration": len(narration_text) * 60 // self.target_wpm,
                "word_count": len(narration_text)
            }
            
            return result
            
        except Exception as e:
            self.logger.error(f"解析口播文案响应失败: {e}")
            # 返回基础结构
            return {
                "title": "小说视频解说",
                "narration": self._clean_response_text(response).strip(),
                "summary": "解说文案",
                "key_points": [],
                "estimated_duration": 0,
                "word_count": len(response)
            }
    
    def _clean_response_text(self, text: str) -> str:
        """
        清理文本中的控制字符和无效字符
        """
        import re
        # 移除控制字符但保留换行符和制表符
        cleaned = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
        # 移除过多的空白字符
        cleaned = re.sub(r'\s+', ' ', cleaned)
        return cleaned.strip()
    
    async def _optimize_narration(self, narration_data: Dict[str, Any], target_duration: int) -> Dict[str, Any]:
        """
        优化口播文案，确保时长和质量符合要求（简化版，避免过多API调用）
        """
        current_duration = narration_data.get('estimated_duration', 0)
        narration_text = narration_data.get('narration', '')
        
        # 简单的文本调整，不使用API
        duration_diff = abs(current_duration - target_duration)
        if duration_diff > target_duration * 0.3:  # 只在差异很大时才调整
            
            if current_duration < target_duration * 0.7:
                # 文案过短，简单重复关键句子
                narration_text = self._simple_expand_narration(narration_text, target_duration)
                narration_data['narration'] = narration_text
                narration_data['word_count'] = len(narration_text)
                narration_data['estimated_duration'] = len(narration_text) * 60 // self.target_wpm
                self.logger.info(f"文案过短，已扩展至{len(narration_text)}字")
                
            elif current_duration > target_duration * 1.3:
                # 文案过长，简单截断
                target_chars = target_duration * self.target_wpm // 60
                if len(narration_text) > target_chars:
                    # 在句号处截断，保持完整性
                    truncated = narration_text[:target_chars]
                    last_period = truncated.rfind('。')
                    if last_period > target_chars * 0.8:  # 如果句号位置合理
                        narration_text = truncated[:last_period + 1]
                    else:
                        narration_text = truncated + '。'
                    
                    narration_data['narration'] = narration_text
                    narration_data['word_count'] = len(narration_text)
                    narration_data['estimated_duration'] = len(narration_text) * 60 // self.target_wpm
                    self.logger.info(f"文案过长，已截断至{len(narration_text)}字")
        
        # 添加分段信息，便于后续分镜处理
        narration_data['segments'] = self._segment_narration(narration_data['narration'])
        
        return narration_data
    
    def _simple_expand_narration(self, narration: str, target_duration: int) -> str:
        """
        简单扩展文案（不使用API）
        """
        target_chars = target_duration * self.target_wpm // 60
        current_length = len(narration)
        
        if current_length >= target_chars:
            return narration
        
        # 找到关键句子进行重复或扩展
        sentences = narration.split('。')
        sentences = [s.strip() for s in sentences if s.strip()]
        
        expanded = narration
        
        # 添加一些通用的过渡句子
        transitions = [
            "让我们继续这个故事。",
            "接下来会发生什么呢？",
            "这个情节越来越精彩了。",
            "故事的发展令人意想不到。"
        ]
        
        transition_index = 0
        while len(expanded) < target_chars and transition_index < len(transitions):
            expanded += transitions[transition_index]
            transition_index += 1
        
        return expanded
    
    async def _expand_narration(self, narration: str, target_duration: int) -> str:
        """扩展文案内容"""
        prompt = f"""请将以下解说文案扩展到约{target_duration}秒的时长：

原文案：
{narration}

扩展要求：
1. 保持原有核心内容和风格
2. 增加细节描述和情感渲染
3. 补充背景信息或人物心理描写
4. 确保内容自然流畅，不显突兀

请返回扩展后的完整文案："""

        response = await self.llm_client.generate_text(prompt)
        return response.strip()
    
    async def _compress_narration(self, narration: str, target_duration: int) -> str:
        """压缩文案内容"""
        prompt = f"""请将以下解说文案压缩到约{target_duration}秒的时长：

原文案：
{narration}

压缩要求：
1. 保留核心情节和关键信息
2. 删除冗余描述和次要细节
3. 保持语言流畅和逻辑完整
4. 确保压缩后仍有吸引力

请返回压缩后的完整文案："""

        response = await self.llm_client.generate_text(prompt)
        return response.strip()
    
    def _segment_narration(self, narration: str) -> List[Dict[str, Any]]:
        """
        将口播文案分段，为后续分镜提供结构化信息
        """
        # 按句号、感叹号、问号分段
        sentences = re.split(r'[。！？.!?]+', narration)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        # 将句子按逻辑分组
        segments = []
        current_segment = []
        current_length = 0
        target_segment_length = len(narration) // 6  # 预计分成6-8段
        
        for sentence in sentences:
            current_segment.append(sentence)
            current_length += len(sentence)
            
            # 如果当前段落长度合适，结束当前段落
            if current_length >= target_segment_length or len(current_segment) >= 3:
                segments.append({
                    'content': '。'.join(current_segment) + '。',
                    'word_count': current_length,
                    'sentence_count': len(current_segment)
                })
                current_segment = []
                current_length = 0
        
        # 处理剩余内容
        if current_segment:
            segments.append({
                'content': '。'.join(current_segment) + '。',
                'word_count': current_length,
                'sentence_count': len(current_segment)
            })
        
        return segments
    
    def get_narration_stats(self, narration_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取口播文案的统计信息
        """
        narration = narration_data.get('narration', '')
        
        return {
            'total_characters': len(narration),
            'estimated_duration': narration_data.get('estimated_duration', 0),
            'word_count': narration_data.get('word_count', 0),
            'segment_count': len(narration_data.get('segments', [])),
            'average_segment_length': len(narration) // max(len(narration_data.get('segments', [])), 1)
        }