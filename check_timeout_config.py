#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
检查超时配置是否正确
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from utils.file_utils import load_config
from utils.api_utils import APIUtils
from processors.llm_client import LLMClient

def check_timeout_config():
    """检查超时配置"""
    print("检查超时配置...")
    print("=" * 50)
    
    # 加载配置
    config = load_config("config.yaml")
    
    # 检查配置文件中的设置
    performance_config = config.get('performance', {})
    print(f"配置文件中的超时设置:")
    print(f"  performance.request_timeout: {performance_config.get('request_timeout', 'N/A')}")
    
    # 检查APIUtils的实际设置
    api_utils = APIUtils(config)
    print(f"\nAPIUtils实际使用的超时:")
    print(f"  request_timeout: {api_utils.request_timeout}秒")
    
    # 检查LLMClient
    try:
        llm_client = LLMClient(config)
        print(f"\nLLMClient初始化成功")
        print(f"  使用的APIUtils超时: {llm_client.api_utils.request_timeout}秒")
    except Exception as e:
        print(f"\nLLMClient初始化失败: {e}")
    
    print("\n" + "=" * 50)
    print("配置检查完成")
    
    if api_utils.request_timeout >= 120:
        print("✅ 超时设置已调整为120秒或更长")
        print("现在应该能更好地处理网络延迟问题")
    else:
        print("❌ 超时设置仍然过短")
        print("建议调整config.yaml中performance.request_timeout为300")

if __name__ == "__main__":
    check_timeout_config()