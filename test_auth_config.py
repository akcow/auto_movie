#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试通用2.0文生图模型双重认证配置
"""

import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.append(str(Path(__file__).parent))

from utils.file_utils import load_config
from processors.image_gen import ImageGenerator

def test_auth_config():
    """测试双重认证配置"""
    
    print("=" * 80)
    print("测试通用2.0文生图模型双重认证配置")
    print("=" * 80)
    
    try:
        # 加载配置
        config = load_config()
        print("[OK] 配置加载成功")
        
        # 检查API配置
        api_config = config.get('api', {}).get('volcengine', {})
        print(f"\n当前API配置:")
        print(f"  access_key_id: {api_config.get('access_key_id', '未配置')}")
        print(f"  secret_access_key: {'已配置' if api_config.get('secret_access_key') else '未配置'}")
        print(f"  region: {api_config.get('region', '未配置')}")
        print(f"  兼容api_key: {'已配置' if api_config.get('api_key') else '未配置'}")
        
        # 检查配置完整性
        has_dual_auth = bool(api_config.get('access_key_id') and api_config.get('secret_access_key'))
        has_legacy_auth = bool(api_config.get('api_key'))
        
        print(f"\n认证状态:")
        print(f"  双重认证(推荐): {'[OK]' if has_dual_auth else '[ERROR]'}")
        print(f"  单一认证(兼容): {'[OK]' if has_legacy_auth else '[ERROR]'}")
        
        if not has_dual_auth and not has_legacy_auth:
            print("\n[ERROR] 缺少认证配置！请配置以下其中一种：")
            print("1. 推荐方式: access_key_id + secret_access_key")
            print("2. 兼容方式: api_key")
            return False
        
        # 尝试初始化图片生成器
        try:
            image_gen = ImageGenerator(config)
            print(f"\n[OK] 图片生成器初始化成功")
            
            # 显示认证信息
            print(f"\n实际使用的认证信息:")
            print(f"  AccessKey ID: {image_gen.access_key_id[:20]}..." if len(image_gen.access_key_id) > 20 else f"  AccessKey ID: {image_gen.access_key_id}")
            print(f"  SecretAccessKey: {'已配置' if image_gen.secret_access_key else '未配置'}")
            print(f"  Region: {image_gen.region}")
            print(f"  Model: {image_gen.model}")
            
            return True
            
        except ValueError as e:
            print(f"\n[ERROR] 配置验证失败: {e}")
            return False
        
    except Exception as e:
        print(f"[ERROR] 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        return False

def show_config_guide():
    """显示配置指南"""
    
    print("\n" + "=" * 80)
    print("配置指南")
    print("=" * 80)
    
    print("""
Visual Service API密钥获取步骤:

1. 登录火山引擎控制台 (https://console.volcengine.com/)
2. 进入"访问控制" → "API密钥管理"
3. 创建新的密钥对，获取:
   - AccessKey ID
   - SecretAccessKey

4. 在config.yaml中配置:
```yaml
api:
  volcengine:
    access_key_id: "your_access_key_id_here"
    secret_access_key: "your_secret_key_here"
    region: "cn-north-1"
```

注意事项:
- 确保密钥有Visual Service的访问权限
- cn-north-1是通用2.0模型的服务区域
- 请妥善保管SecretAccessKey，不要泄露

兼容性说明:
- 如果只配置api_key，系统也会尝试使用
- 但推荐使用access_key_id + secret_access_key的双重认证
- 双重认证提供更好的安全性和功能支持
""")

if __name__ == "__main__":
    success = test_auth_config()
    
    if not success:
        show_config_guide()
    else:
        print("\n[OK] 认证配置检查通过！可以正常使用通用2.0文生图模型。")