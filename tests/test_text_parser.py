#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
文本解析器单元测试
"""

import pytest
import sys
import tempfile
import os
from pathlib import Path

# 添加项目路径
sys.path.append(str(Path(__file__).parent.parent))

from processors.parser import TextParser
from utils.file_utils import FileUtils


class TestTextParser:
    """文本解析器测试类"""
    
    @pytest.fixture
    def parser(self):
        """创建测试用的解析器实例"""
        config = {
            'generation': {
                'max_images': 10,
                'final_duration_min': 60,
                'final_duration_max': 180
            },
            'quality_control': {
                'min_text_length': 100
            }
        }
        return TextParser(config)
    
    @pytest.fixture
    def sample_text_file(self):
        """创建样本文本文件"""
        content = """第一章：开始
        
这是一个测试小说的第一章内容。包含了一些基本的情节描述。

第二章：发展

这是第二章的内容，继续推进故事情节。这里有更多的细节描述。

第三章：高潮

故事在这里达到高潮，所有的矛盾都集中爆发了。

结语

这就是测试小说的结尾部分。"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_file = f.name
        
        yield temp_file
        
        # 清理
        if os.path.exists(temp_file):
            os.unlink(temp_file)
    
    def test_parse_basic_functionality(self, parser, sample_text_file):
        """测试基本解析功能"""
        result = parser.parse(sample_text_file)
        
        # 检查返回结果结构
        assert isinstance(result, dict)
        assert 'content' in result
        assert 'title' in result
        assert 'word_count' in result
        assert 'chapters_found' in result
        
        # 检查内容不为空
        assert len(result['content']) > 0
        assert result['word_count'] > 0
        assert result['chapters_found'] >= 0
    
    def test_chapter_detection(self, parser, sample_text_file):
        """测试章节检测功能"""
        result = parser.parse(sample_text_file)
        
        # 应该检测到3个章节
        assert result['chapters_found'] >= 3
    
    def test_title_extraction(self, parser, sample_text_file):
        """测试标题提取功能"""
        result = parser.parse(sample_text_file)
        
        # 标题应该不为空
        assert len(result['title']) > 0
        assert isinstance(result['title'], str)
    
    def test_content_cleaning(self, parser):
        """测试内容清理功能"""
        dirty_text = "  这是一段    包含多余空格\n\n\n的文本  \t"
        cleaned = parser._clean_text(dirty_text)
        
        # 检查清理效果
        assert cleaned == "这是一段 包含多余空格 的文本"
        assert not cleaned.startswith(' ')
        assert not cleaned.endswith(' ')
    
    def test_empty_file_handling(self, parser):
        """测试空文件处理"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("")  # 空文件
            temp_file = f.name
        
        try:
            result = parser.parse(temp_file)
            # 空文件应该有默认处理
            assert isinstance(result, dict)
            assert result['word_count'] == 0
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)
    
    def test_encoding_detection(self, parser):
        """测试编码检测功能"""
        # 创建不同编码的测试文件
        test_content = "这是一个中文测试文本"
        
        # UTF-8编码
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(test_content)
            utf8_file = f.name
        
        try:
            result = parser.parse(utf8_file)
            assert test_content in result['content']
        finally:
            if os.path.exists(utf8_file):
                os.unlink(utf8_file)
    
    def test_word_count_accuracy(self, parser, sample_text_file):
        """测试字数统计准确性"""
        result = parser.parse(sample_text_file)
        
        # 读取原始内容手动计算字数
        with open(sample_text_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 简单的字数统计（去除空白字符）
        manual_count = len(''.join(content.split()))
        
        # 允许一定的误差范围（±10%）
        assert abs(result['word_count'] - manual_count) <= manual_count * 0.1
    
    def test_file_not_found_handling(self, parser):
        """测试文件不存在的处理"""
        non_existent_file = "/path/to/non/existent/file.txt"
        
        with pytest.raises(Exception):
            parser.parse(non_existent_file)
    
    def test_large_text_handling(self, parser):
        """测试大文本处理"""
        # 创建较大的测试文件
        large_content = "这是一段测试文本。" * 1000  # 约10,000字符
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(large_content)
            large_file = f.name
        
        try:
            result = parser.parse(large_file)
            assert result['word_count'] > 5000  # 应该是较大的数字
        finally:
            if os.path.exists(large_file):
                os.unlink(large_file)
    
    def test_special_characters_handling(self, parser):
        """测试特殊字符处理"""
        special_content = "这是包含特殊字符的文本：「引号」，【括号】，〈书名号〉，以及emoji😀。"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(special_content)
            special_file = f.name
        
        try:
            result = parser.parse(special_file)
            # 应该能正确处理特殊字符
            assert result['word_count'] > 0
            assert len(result['content']) > 0
        finally:
            if os.path.exists(special_file):
                os.unlink(special_file)


def run_parser_tests():
    """运行文本解析器测试"""
    print("运行文本解析器测试...")
    
    # 简化测试运行（不依赖pytest）
    config = {
        'generation': {
            'max_images': 10,
            'final_duration_min': 60,
            'final_duration_max': 180
        },
        'quality_control': {
            'min_text_length': 100
        }
    }
    
    parser = TextParser(config)
    
    # 创建测试文件
    test_content = """第一章：测试开始
    
这是一个用于测试的小说内容。包含多个章节和段落。

第二章：测试继续

更多的测试内容，用来验证解析器的功能。

第三章：测试结束

这是最后一章的内容。"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        f.write(test_content)
        test_file = f.name
    
    try:
        # 运行测试
        print("1. 测试基本解析功能...")
        result = parser.parse(test_file)
        assert isinstance(result, dict)
        assert 'content' in result
        print("✓ 基本解析功能正常")
        
        print("2. 测试章节检测...")
        assert result['chapters_found'] >= 3
        print(f"✓ 检测到 {result['chapters_found']} 个章节")
        
        print("3. 测试字数统计...")
        assert result['word_count'] > 0
        print(f"✓ 统计字数: {result['word_count']}")
        
        print("4. 测试内容清理...")
        cleaned = parser._clean_text("  测试文本  \n\n")
        assert cleaned == "测试文本"
        print("✓ 内容清理功能正常")
        
        print("文本解析器测试全部通过! ✅")
        
    except Exception as e:
        print(f"测试失败: {e}")
        return False
    finally:
        if os.path.exists(test_file):
            os.unlink(test_file)
    
    return True


if __name__ == "__main__":
    run_parser_tests()