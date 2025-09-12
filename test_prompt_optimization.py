#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试通用2.0文生图模型提示词优化
"""

import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.append(str(Path(__file__).parent))

from utils.file_utils import load_config
from processors.image_gen import ImageGenerator

def test_prompt_building():
    """测试提示词构建功能"""
    
    print("=" * 80)
    print("测试通用2.0文生图模型提示词优化")
    print("=" * 80)
    
    try:
        # 加载配置
        config = load_config()
        print("[OK] 配置加载成功")
        
        # 初始化图片生成器
        image_gen = ImageGenerator(config)
        print("[OK] 图片生成器初始化成功")
        
        # 测试用例
        test_cases = [
            {
                "description": "古风庭院，月光如水，白衣女子独立庭院中央",
                "style": "古风 唯美 仙侠"
            },
            {
                "description": "森林深处，黑衣男子站立在巨树下，表情冷峻",
                "style": "古风 仙侠"
            },
            {
                "description": "海边悬崖，女子长发飘飘，眺望远方",
                "style": "唯美 写实"
            },
            {
                "description": "大学教室内，男生坐在桌前认真看书",
                "style": "写实"
            },
            {
                "description": "山顶寺庙，僧人打坐冥想，云雾缭绕",
                "style": "古风 唯美"
            }
        ]
        
        print(f"\n开始测试 {len(test_cases)} 个用例...\n")
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"--- 测试用例 {i} ---")
            print(f"原始描述: {test_case['description']}")
            print(f"原始风格: {test_case['style']}")
            
            # 构建优化后的提示词
            optimized_prompt = image_gen._build_image_prompt(
                test_case['description'], 
                test_case['style']
            )
            
            print(f"优化后提示词: {optimized_prompt}")
            
            # 解析组件（用于调试）
            components = image_gen._parse_description_for_v2_model(
                test_case['description'], 
                test_case['style']
            )
            print(f"解析组件:")
            for key, value in components.items():
                if value:
                    print(f"  {key}: {value}")
            
            print("-" * 50)
        
        print("\n" + "=" * 80)
        print("提示词优化测试完成！")
        print("=" * 80)
        
        # 提供使用建议
        print("\n使用建议:")
        print("1. 新的提示词结构遵循通用2.0模型推荐格式")
        print("2. 按照'场景→角色→构图→动作→风格'的顺序组织")
        print("3. 避免使用人名、地名等模型无法理解的概念")
        print("4. 使用'圆领袍'避免V领问题")
        print("5. 添加质量控制词确保输出质量")
        
    except Exception as e:
        print(f"[ERROR] 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_prompt_building()