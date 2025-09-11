#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
文本解析模块
负责小说文本的解析、章节分割、内容清理等功能
"""

import re
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from utils.file_utils import FileUtils
from utils.logger import LoggerMixin


class TextParser(LoggerMixin):
    """文本解析器"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化文本解析器
        
        Args:
            config: 配置字典
        """
        self.config = config
        self.generation_config = config.get('generation', {})
        self.min_duration = self.generation_config.get('final_duration_min', 120)  # 最小120秒
        self.max_duration = self.generation_config.get('final_duration_max', 240)  # 最大240秒
        
        # 预估每分钟需要的字数 (中文约250字/分钟)
        self.words_per_minute = 250
        self.min_words = int(self.min_duration / 60 * self.words_per_minute)  # 约500字
        self.max_words = int(self.max_duration / 60 * self.words_per_minute)  # 约1000字
        
        # 章节标题模式
        self.chapter_patterns = [
            r'^第[一二三四五六七八九十零\d]+章.*$',           # 第X章
            r'^第[一二三四五六七八九十零\d]+节.*$',           # 第X节  
            r'^第[一二三四五六七八九十零\d]+回.*$',           # 第X回
            r'^\d+[、．\.].*$',                            # 1. 或 1、
            r'^[一二三四五六七八九十零]{1,3}[、．\.].*$',      # 一、二、
            r'^Chapter\s*\d+.*$',                          # Chapter 1
            r'^第[一二三四五六七八九十零\d]+部分.*$',         # 第X部分
            r'^\[.+\]$',                                  # [标题]
            r'^【.+】$',                                   # 【标题】
        ]
    
    def parse(self, file_path: str) -> Dict[str, Any]:
        """
        解析小说文件，返回处理后的内容和分段结果
        
        Args:
            file_path: 小说文件路径
            
        Returns:
            包含解析结果的字典，包含segments列表
        """
        try:
            self.logger.info(f"开始解析文件: {file_path}")
            
            # 读取文件内容
            content = self._read_file(file_path)
            if not content:
                raise ValueError("文件内容为空")
            
            # 文本预处理
            cleaned_content = self._clean_text(content)
            
            # 章节分割
            chapters = self._split_chapters(cleaned_content)
            
            # 选择合适的章节或片段
            selected_text = self._select_text_segment(chapters, file_path)
            
            # 最终文本处理
            final_text = self._process_final_text(selected_text)
            
            # 创建语义分段
            segments = self._create_semantic_segments(final_text)
            
            return {
                'segments': segments,
                'cleaned_text': final_text,
                'title': self._extract_title(final_text, file_path),
                'word_count': len(final_text),
                'chapters_count': len(chapters)
            }
            
        except Exception as e:
            print(f"解析文件时出错: {e}")
            return {'segments': [], 'cleaned_text': '', 'title': '未知', 'word_count': 0, 'chapters_count': 0}
    
    def _read_file(self, file_path: str) -> str:
        """
        读取文件内容，支持多种编码
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件内容
        """
        try:
            return FileUtils.read_text_file(file_path)
        except Exception as e:
            self.logger.error(f"文件读取失败: {e}")
            raise ValueError(f"无法读取文件: {file_path}")
    
    def _clean_text(self, content: str) -> str:
        """
        清理文本内容
        
        Args:
            content: 原始文本内容
            
        Returns:
            清理后的文本
        """
        # 统一换行符
        content = re.sub(r'\r\n|\r', '\n', content)
        
        # 移除多余的空行 (保留段落间的单个空行)
        content = re.sub(r'\n{3,}', '\n\n', content)
        
        # 移除行首行尾空白
        lines = []
        for line in content.split('\n'):
            cleaned_line = line.strip()
            if cleaned_line:  # 非空行
                lines.append(cleaned_line)
            elif lines and lines[-1] != '':  # 保留段落间隔
                lines.append('')
        
        # 移除常见的无关内容
        cleaned_lines = []
        skip_patterns = [
            r'^更新时间.*$',
            r'^字数.*$', 
            r'^作者.*$',
            r'^来源.*$',
            r'^www\..*\.com$',
            r'^.*\.txt.*$',
            r'^.*\.doc.*$',
            r'^\d+$',  # 纯数字行
            r'^[-=_]{5,}$',  # 分隔线
            r'^[。，！？；：""''（）【】《》]{1,5}$',  # 纯标点符号行
        ]
        
        for line in lines:
            should_skip = False
            for pattern in skip_patterns:
                if re.match(pattern, line):
                    should_skip = True
                    break
            
            if not should_skip:
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    def _split_chapters(self, content: str) -> List[Dict[str, Any]]:
        """
        增强的章节分割方法
        
        Args:
            content: 文本内容
            
        Returns:
            章节列表
        """
        lines = content.split('\n')
        chapters = []
        current_chapter = {'title': '', 'content': '', 'start_line': 0}
        
        for i, line in enumerate(lines):
            if self._is_chapter_title(line):
                # 保存上一章节
                if current_chapter['content'].strip():
                    current_chapter['word_count'] = len(current_chapter['content'])
                    chapters.append(current_chapter)
                
                # 开始新章节
                current_chapter = {
                    'title': line.strip(),
                    'content': '',
                    'start_line': i
                }
            else:
                # 添加内容到当前章节
                if line.strip():  # 非空行
                    current_chapter['content'] += line + '\n'
        
        # 添加最后一个章节
        if current_chapter['content'].strip():
            current_chapter['word_count'] = len(current_chapter['content'])
            chapters.append(current_chapter)
        
        # 如果没有找到章节，将整个文本作为一个章节
        if not chapters:
            chapters = [{
                'title': '正文',
                'content': content,
                'word_count': len(content),
                'start_line': 0
            }]
        
        self.logger.info(f"找到 {len(chapters)} 个章节")
        return chapters
    
    def _create_semantic_segments(self, text: str) -> List[str]:
        """
        创建语义分段，按语义和时长双重标准分段
        每段控制在50-100字，适合15-30秒音频长度
        
        Args:
            text: 处理后的文本
            
        Returns:
            分段后的文本列表
        """
        if not text.strip():
            return []
        
        segments = []
        # 按段落分割
        paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
        
        current_segment = ""
        min_segment_length = self.config.get('min_segment_length', 50)
        max_segment_length = self.config.get('max_segment_length', 100)
        
        for paragraph in paragraphs:
            # 如果段落本身就很长，需要进一步分割
            if len(paragraph) > max_segment_length:
                # 先保存当前段（如果有内容）
                if current_segment:
                    segments.append(current_segment.strip())
                    current_segment = ""
                
                # 按句子分割长段落
                sentences = self._split_long_paragraph(paragraph, max_segment_length)
                segments.extend(sentences)
            else:
                # 检查加入当前段落后是否超长
                test_segment = current_segment + ("\n" if current_segment else "") + paragraph
                
                if len(test_segment) <= max_segment_length:
                    current_segment = test_segment
                else:
                    # 当前段已达到合适长度，保存并开始新段
                    if current_segment and len(current_segment) >= min_segment_length:
                        segments.append(current_segment.strip())
                    current_segment = paragraph
        
        # 处理最后一段
        if current_segment:
            if len(current_segment) >= min_segment_length or not segments:
                segments.append(current_segment.strip())
            else:
                # 如果最后一段太短，合并到前一段
                if segments:
                    segments[-1] += "\n" + current_segment
                else:
                    segments.append(current_segment.strip())
        
        return segments
    
    def _split_long_paragraph(self, paragraph: str, max_length: int) -> List[str]:
        """
        分割过长的段落
        
        Args:
            paragraph: 需要分割的段落
            max_length: 最大长度
            
        Returns:
            分割后的句子列表
        """
        if len(paragraph) <= max_length:
            return [paragraph]
        
        segments = []
        # 按标点符号分割
        import re
        sentences = re.split(r'[。！？；]', paragraph)
        
        current_segment = ""
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # 恢复标点符号（除了最后一个）
            if sentence != sentences[-1]:
                # 找到原文中的标点符号
                for punct in ['。', '！', '？', '；']:
                    if paragraph.find(sentence + punct) != -1:
                        sentence += punct
                        break
            
            test_segment = current_segment + sentence
            if len(test_segment) <= max_length:
                current_segment = test_segment
            else:
                if current_segment:
                    segments.append(current_segment)
                current_segment = sentence
        
        if current_segment:
            segments.append(current_segment)
        
        return segments
    
    def _is_chapter_title(self, line: str) -> bool:
        """
        判断是否是章节标题
        
        Args:
            line: 文本行
            
        Returns:
            是否是章节标题
        """
        line = line.strip()
        if not line or len(line) > 50:  # 太长的不是标题
            return False
        
        for pattern in self.chapter_patterns:
            if re.match(pattern, line, re.IGNORECASE):
                return True
        
        return False
    
    def _select_text_segment(self, chapters: List[Dict[str, Any]], file_path: str) -> str:
        """
        选择合适的文本片段
        
        Args:
            chapters: 章节列表
            file_path: 原文件路径
            
        Returns:
            选中的文本内容
        """
        if not chapters:
            raise ValueError("没有找到可用的文本内容")
        
        # 策略1: 寻找长度合适的单个章节
        for chapter in chapters:
            if self.min_words <= chapter['word_count'] <= self.max_words:
                self.logger.info(f"选择章节: {chapter['title']} ({chapter['word_count']}字)")
                return f"# {chapter['title']}\n\n{chapter['content']}"
        
        # 策略2: 合并短章节
        if len(chapters) > 1:
            combined_content = []
            combined_word_count = 0
            
            for chapter in chapters:
                if combined_word_count + chapter['word_count'] <= self.max_words:
                    combined_content.append(f"# {chapter['title']}\n\n{chapter['content']}")
                    combined_word_count += chapter['word_count']
                    
                    if combined_word_count >= self.min_words:
                        break
            
            if combined_content and combined_word_count >= self.min_words:
                self.logger.info(f"合并 {len(combined_content)} 个章节 ({combined_word_count}字)")
                return '\n\n'.join(combined_content)
        
        # 策略3: 截取最长章节的合适部分
        longest_chapter = max(chapters, key=lambda x: x['word_count'])
        content = longest_chapter['content']
        
        if len(content) > self.max_words:
            # 截取前面部分，在句子边界截断
            truncated = content[:self.max_words]
            sentences = re.split(r'[。！？]', truncated)
            if len(sentences) > 1:
                truncated = '。'.join(sentences[:-1]) + '。'
            
            self.logger.info(f"截取章节: {longest_chapter['title']} ({len(truncated)}字)")
            return f"# {longest_chapter['title']}\n\n{truncated}"
        else:
            self.logger.info(f"使用完整章节: {longest_chapter['title']} ({len(content)}字)")
            return f"# {longest_chapter['title']}\n\n{content}"
    
    def _process_final_text(self, text: str) -> str:
        """
        最终文本处理
        
        Args:
            text: 原始文本
            
        Returns:
            处理后的文本
        """
        # 移除多余的空白字符
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' {2,}', ' ', text)
        
        # 确保标点符号正确
        text = re.sub(r'([。！？])\s*([^"\n])', r'\1\n\2', text)  # 句子后换行
        
        # 移除空的标题行
        lines = text.split('\n')
        filtered_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped and not (stripped.startswith('#') and len(stripped.replace('#', '').strip()) < 2):
                filtered_lines.append(line)
        
        return '\n'.join(filtered_lines).strip()
    
    def _extract_title(self, content: str, file_path: str) -> str:
        """
        提取标题
        
        Args:
            file_path: 文件路径
            content: 文本内容
            
        Returns:
            标题
        """
        # 从内容中提取标题
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('#'):
                title = line.replace('#', '').strip()
                if title and len(title) <= 30:
                    return title
        
        # 从文件名提取标题
        file_name = Path(file_path).stem
        # 移除常见的后缀
        title = re.sub(r'[-_\s]*(?:小说|txt|doc|全集|完整版|最新版)[-_\s]*$', '', file_name)
        
        return title if title else "未命名"
    
    def validate_text(self, text: str) -> Tuple[bool, str]:
        """
        验证文本质量
        
        Args:
            text: 文本内容
            
        Returns:
            (是否通过, 错误信息)
        """
        if not text or not text.strip():
            return False, "文本内容为空"
        
        # 检查长度
        word_count = len(text)
        if word_count < self.min_words // 2:
            return False, f"文本过短 ({word_count}字), 最少需要{self.min_words//2}字"
        
        if word_count > self.max_words * 2:
            return False, f"文本过长 ({word_count}字), 最多支持{self.max_words*2}字"
        
        # 检查字符质量
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        chinese_ratio = chinese_chars / word_count if word_count > 0 else 0
        
        if chinese_ratio < 0.3:
            return False, f"中文字符比例过低 ({chinese_ratio:.1%}), 可能不是中文小说"
        
        # 检查内容质量
        sentences = re.split(r'[。！？]', text)
        valid_sentences = [s for s in sentences if len(s.strip()) > 5]
        
        if len(valid_sentences) < 3:
            return False, "文本内容质量过低，句子数量不足"
        
        return True, ""


def test_parser():
    """测试文本解析器"""
    config = {
        'generation': {
            'final_duration_min': 120,
            'final_duration_max': 240
        }
    }
    
    parser = TextParser(config)
    
    # 创建测试文本
    test_content = """第一章 开始

这是一个测试的小说内容。主角是一个年轻人，他生活在一个神秘的世界里。

在这个世界中，魔法和科技并存。每个人都有自己独特的能力。

第二章 冒险

主角开始了他的冒险之旅。他遇到了很多困难，但是他从未放弃。

通过不断的努力和学习，他变得越来越强大。

第三章 成长

最终，主角成为了这个世界的英雄。他拯救了无数的人，也找到了自己的真正价值。

这就是他成长的故事。"""
    
    # 保存测试文件
    test_file = "./test_novel.txt"
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write(test_content)
    
    try:
        # 测试解析
        result = parser.parse(test_file)
        print("解析结果:", result)
        
        # 测试验证
        is_valid, error = parser.validate_text(result['content'])
        print(f"验证结果: {is_valid}, {error}")
        
    finally:
        # 清理测试文件
        Path(test_file).unlink(missing_ok=True)


if __name__ == "__main__":
    test_parser()