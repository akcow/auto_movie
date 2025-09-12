#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
API密钥权限诊断工具
"""

import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.append(str(Path(__file__).parent))

from utils.file_utils import load_config
from processors.image_gen import ImageGenerator

def diagnose_api_permissions():
    """诊断API密钥权限问题"""
    
    print("=" * 80)
    print("API密钥权限诊断工具")
    print("=" * 80)
    
    try:
        # 加载配置
        config = load_config()
        print("[OK] 配置加载成功")
        
        # 检查API配置
        api_config = config.get('api', {}).get('volcengine', {})
        
        print(f"\n当前API配置:")
        print(f"  AccessKey ID: {api_config.get('access_key_id', '未配置')[:20]}...")
        print(f"  SecretAccessKey: {'已配置' if api_config.get('secret_access_key') else '未配置'}")
        print(f"  Region: {api_config.get('region', '未配置')}")
        
        # 检查TOS配置对比
        tos_config = api_config.get('tos', {})
        if tos_config:
            print(f"\nTOS配置检测:")
            print(f"  TOS AccessKey ID: {tos_config.get('access_key_id', '未配置')[:20]}...")
            print(f"  TOS SecretAccessKey: {'已配置' if tos_config.get('secret_access_key') else '未配置'}")
            
            # 检查是否使用了TOS密钥
            if (api_config.get('access_key_id') == tos_config.get('access_key_id') and
                api_config.get('secret_access_key') == tos_config.get('secret_access_key')):
                print(f"\n[WARNING] 检测到您使用了TOS对象存储的密钥！")
                print(f"  TOS密钥只能用于对象存储，不能用于Visual Service文生图API")
                print(f"  这是导致Access Denied的主要原因")
        
        # 尝试初始化并测试API
        print(f"\n开始测试API调用...")
        try:
            image_gen = ImageGenerator(config)
            
            # 测试简单提示词
            test_prompt = "庭院内，一位穿白色圆领袍的女性，电影般的意境角度，静态姿势，古风言情动漫风格，超高分辨率，竖屏9:16"
            
            import time
            start_time = time.time()
            
            # 测试API调用
            image_data = asyncio.run(image_gen._call_text2image_api(test_prompt))
            
            if image_data:
                elapsed = time.time() - start_time
                print(f"[SUCCESS] API调用成功！耗时: {elapsed:.2f}秒")
                print(f"返回图片大小: {len(image_data)} bytes")
                return True
            else:
                print(f"[ERROR] API调用成功但未返回数据")
                return False
                
        except Exception as e:
            print(f"[ERROR] API调用失败: {e}")
            
            # 分析错误类型
            error_str = str(e)
            if "Access Denied" in error_str:
                print(f"\n问题诊断:")
                print(f"  1. API密钥没有Visual Service访问权限")
                print(f"  2. 可能需要开通视觉智能服务")
                print(f"  3. 密钥类型可能不正确")
                
            return False
        
    except Exception as e:
        print(f"[ERROR] 诊断过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        return False

def show_solution_guide():
    """显示解决方案指南"""
    
    print("\n" + "=" * 80)
    print("解决方案指南")
    print("=" * 80)
    
    print("""
🔧 解决Access Denied问题的步骤:

1. 确认服务开通
   - 登录火山引擎控制台
   - 检查是否已开通"视觉智能"或"机器学习平台PAI"服务
   - 如果未开通，请先开通相关服务

2. 获取正确的API密钥
   - 进入"访问控制" → "API密钥管理"
   - 创建新的密钥对（专门用于视觉智能服务）
   - 或者使用现有的密钥并添加相应权限

3. 配置权限策略
   - 为密钥添加Visual Service的访问权限
   - 确保权限包含cv_process等操作
   - 区域设置为cn-north-1

4. 更新配置文件
   - 将新获取的密钥配置到config.yaml中
   - 确保access_key_id和secret_access_key都正确配置

5. 验证配置
   - 运行: python test_auth_config.py
   - 运行: python test_new_image_model.py

⚠️  重要提醒:
- TOS对象存储的密钥不能用于Visual Service API
- 需要专门为视觉智能服务配置密钥权限
- 确保密钥有足够的权限访问通用2.0模型

📞 如果问题仍然存在:
1. 检查火山引擎控制台的"权限管理"
2. 确认账号余额充足
3. 联系火山引擎技术支持
""")

if __name__ == "__main__":
    success = diagnose_api_permissions()
    
    if not success:
        show_solution_guide()
    else:
        print("\n[SUCCESS] API权限正常，可以正常使用通用2.0文生图模型。")