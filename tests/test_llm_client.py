#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LLM客户端单元测试
"""

import json
import sys
import tempfile
from pathlib import Path

# 添加项目路径
sys.path.append(str(Path(__file__).parent.parent))

from processors.llm_client import LLMClient


class TestLLMClient:
    """LLM客户端测试类"""
    
    def test_script_validation(self):
        """测试脚本验证功能"""
        config = {
            'api': {'volcengine': {'access_key_id': 'test', 'secret_access_key': 'test'}},
            'models': {'llm_endpoint': 'test'},
            'generation': {'max_images': 10}
        }
        
        client = LLMClient(config)
        
        # 测试有效的脚本格式
        valid_script = {
            "title": "测试视频",
            "shots": [
                {"description": "第一个镜头", "duration": 5},
                {"description": "第二个镜头", "duration": 3}
            ],
            "narration": "这是旁白内容"
        }
        
        result = client._validate_script_format(valid_script)
        assert result is True
        
        # 测试无效的脚本格式
        invalid_script = {
            "title": "测试视频"
            # 缺少shots和narration
        }
        
        result = client._validate_script_format(invalid_script)
        assert result is False
        
        print("✓ LLM脚本验证功能正常")
    
    def test_prompt_loading(self):
        """测试提示词加载功能"""
        config = {
            'api': {'volcengine': {'access_key_id': 'test', 'secret_access_key': 'test'}},
            'models': {'llm_endpoint': 'test'},
            'prompts': {'storyboard_template': './prompts/storyboard.txt'},
            'generation': {'max_images': 10}
        }
        
        client = LLMClient(config)
        
        # 创建临时提示词文件
        prompt_content = "这是一个测试提示词模板 {title} {content}"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(prompt_content)
            temp_prompt = f.name
        
        try:
            # 更新配置路径
            client.storyboard_template_path = temp_prompt
            loaded_prompt = client._load_prompt_template()
            
            assert loaded_prompt == prompt_content
            print("✓ 提示词加载功能正常")
            
        finally:
            import os
            if os.path.exists(temp_prompt):
                os.unlink(temp_prompt)
    
    def test_json_extraction(self):
        """测试JSON提取功能"""
        config = {
            'api': {'volcengine': {'access_key_id': 'test', 'secret_access_key': 'test'}},
            'models': {'llm_endpoint': 'test'},
            'generation': {'max_images': 10}
        }
        
        client = LLMClient(config)
        
        # 测试包含JSON的文本
        text_with_json = """
        这是一些前缀文本
        ```json
        {
            "title": "测试视频",
            "shots": [{"description": "测试镜头", "duration": 5}],
            "narration": "测试旁白"
        }
        ```
        这是一些后缀文本
        """
        
        result = client._extract_json_from_response(text_with_json)
        
        assert isinstance(result, dict)
        assert result["title"] == "测试视频"
        assert len(result["shots"]) == 1
        
        print("✓ JSON提取功能正常")
    
    def test_fallback_script_generation(self):
        """测试降级脚本生成"""
        config = {
            'api': {'volcengine': {'access_key_id': 'test', 'secret_access_key': 'test'}},
            'models': {'llm_endpoint': 'test'},
            'generation': {'max_images': 10}
        }
        
        client = LLMClient(config)
        
        text_data = {
            'title': '测试小说',
            'content': '这是一个测试小说的内容，包含一些情节描述。',
            'word_count': 50,
            'chapters_found': 1
        }
        
        fallback_script = client._create_fallback_script(text_data)
        
        # 验证降级脚本的结构
        assert isinstance(fallback_script, dict)
        assert 'title' in fallback_script
        assert 'shots' in fallback_script
        assert 'narration' in fallback_script
        assert len(fallback_script['shots']) > 0
        
        # 验证镜头数量合理
        assert len(fallback_script['shots']) <= 10
        
        print("✓ 降级脚本生成功能正常")


def run_llm_tests():
    """运行LLM客户端测试"""
    print("运行LLM客户端测试...")
    
    test_client = TestLLMClient()
    
    try:
        test_client.test_script_validation()
        test_client.test_prompt_loading()
        test_client.test_json_extraction()
        test_client.test_fallback_script_generation()
        
        print("LLM客户端测试全部通过! ✅")
        return True
        
    except Exception as e:
        print(f"LLM客户端测试失败: {e}")
        return False


if __name__ == "__main__":
    run_llm_tests()