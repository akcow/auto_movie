#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试通用2.0文生图模型集成
"""

import asyncio
import sys
import time
from pathlib import Path

# 添加项目路径
sys.path.append(str(Path(__file__).parent))

from utils.file_utils import load_config
from utils.logger import setup_logger
from processors.image_gen import ImageGenerator

async def test_new_image_model():
    """测试新的通用2.0文生图模型"""
    
    print("=" * 60)
    print("测试通用2.0文生图模型集成")
    print("=" * 60)
    
    try:
        # 加载配置
        config = load_config()
        print("[OK] 配置加载成功")
        
        # 简单初始化（跳过复杂的日志设置）
        
        # 初始化图片生成器
        image_gen = ImageGenerator(config)
        print("[OK] 图片生成器初始化成功")
        
        # 测试提示词构建
        prompt = image_gen._build_image_prompt(
            description="古风庭院，月光如水，白衣女子独立庭院中央",
            style="古风 唯美 仙侠"
        )
        print(f"[OK] 提示词构建成功: {prompt[:100]}...")
        
        # 测试图片生成（如果API配置正确）
        print("\n开始测试图片生成...")
        start_time = time.time()
        
        try:
            image_data = await image_gen._call_text2image_api(prompt)
            
            if image_data and len(image_data) > 0:
                elapsed = time.time() - start_time
                print(f"[OK] 图片生成成功！耗时: {elapsed:.2f}秒")
                print(f"图片大小: {len(image_data)} bytes")
                
                # 保存测试图片
                test_output = Path("./data/temp/test_image_v2.jpg")
                test_output.parent.mkdir(parents=True, exist_ok=True)
                
                with open(test_output, 'wb') as f:
                    f.write(image_data)
                
                print(f"[OK] 测试图片已保存到: {test_output}")
                
            else:
                print("[ERROR] 图片生成失败：未返回图片数据")
                
        except Exception as e:
            print(f"[ERROR] 图片生成失败: {e}")
            print("可能的原因：")
            print("1. API密钥配置错误")
            print("2. 缺少volcengine依赖包")
            print("3. 网络连接问题")
            print("4. API服务暂时不可用")
        
        print("\n" + "=" * 60)
        print("测试完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"[ERROR] 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_new_image_model())