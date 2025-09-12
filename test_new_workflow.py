#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
新工作流程测试脚本
测试基于口播文案的智能分镜生成流程
"""

import asyncio
import os
import sys
from pathlib import Path

# 添加项目路径
sys.path.append(str(Path(__file__).parent))

from utils.logger import setup_logger, get_logger
from utils.file_utils import load_config
from processors.llm_client import LLMClient
from processors.narration_generator import NarrationGenerator
from processors.shot_planner import ShotPlanner


async def test_new_workflow():
    """测试新的工作流程"""
    
    # 设置日志
    logger = setup_logger("test_workflow", log_level="INFO")
    logger.info("开始测试新的工作流程")
    
    try:
        # 加载配置
        config = load_config("config.yaml")
        
        # 初始化客户端
        llm_client = LLMClient(config)
        narration_generator = NarrationGenerator(llm_client, config)
        shot_planner = ShotPlanner(llm_client, config)
        
        # 测试小说内容
        test_novel = """
        在一个古老的村庄里，住着一位名叫李明的年轻人。他从小就对神秘的传说充满好奇。
        
        一天晚上，李明在村外的森林中迷路了。就在他绝望的时候，突然看到远处有一道奇异的光芒。
        
        他小心翼翼地走向光源，发现那是一座被遗忘的古庙。庙门上刻着古老的符文，散发着微弱的蓝光。
        
        李明推开庙门，里面供奉着一尊神秘的雕像。雕像的眼睛突然亮了起来，仿佛在注视着他。
        
        "年轻人，你终于来了。"一个古老的声音在庙中回荡。
        
        原来，这座古庙守护着一个关于村庄起源的秘密。李明的到来并非偶然，而是命运的安排。
        
        在雕像的指引下，李明了解了村庄的真正历史，也明白了自己的使命。
        
        从那以后，李明成为了村庄的守护者，继承了祖先留下的智慧和力量。
        """
        
        target_duration = 180  # 3分钟
        
        logger.info("=" * 60)
        logger.info("步骤1: 测试口播文案生成")
        logger.info("=" * 60)
        
        # 生成口播文案
        narration_result = await narration_generator.generate_narration(
            test_novel, 
            target_duration,
            "神秘古庙传说"
        )
        
        logger.info(f"口播文案生成完成:")
        logger.info(f"   标题: {narration_result.get('title', 'N/A')}")
        logger.info(f"   字数: {narration_result.get('word_count', 0)}")
        logger.info(f"   预估时长: {narration_result.get('estimated_duration', 0)}秒")
        logger.info(f"   分段数: {len(narration_result.get('segments', []))}")
        
        print("\n" + "="*80)
        print("生成的口播文案:")
        print("="*80)
        print(narration_result.get('narration', ''))
        print("="*80)
        
        logger.info("=" * 60)
        logger.info("步骤2: 测试智能分镜决策")
        logger.info("=" * 60)
        
        # 生成分镜脚本
        script_result = await shot_planner.plan_shots(narration_result, target_duration)
        
        logger.info(f"分镜脚本生成完成:")
        logger.info(f"   总分镜数: {script_result.get('shot_count', 0)}")
        logger.info(f"   总时长: {script_result.get('total_duration', 0)}秒")
        
        stats = script_result.get('shot_statistics', {})
        logger.info(f"   动态分镜: {stats.get('dynamic_shots', 0)}")
        logger.info(f"   静态分镜: {stats.get('static_shots', 0)}")
        logger.info(f"   平均时长: {stats.get('average_shot_duration', 0):.1f}秒")
        
        print("\n" + "="*80)
        print("分镜脚本详情:")
        print("="*80)
        
        shots = script_result.get('shots', [])
        for i, shot in enumerate(shots, 1):
            shot_type = shot.get('type', 'unknown')
            duration = shot.get('duration', 0)
            description = shot.get('visual_description', '')
            narration_text = shot.get('narration_text', '')
            
            print(f"\n【分镜 {i:2d}】({shot_type.upper()}) - {duration}秒")
            print(f"  视觉: {description[:100]}...")
            print(f"  配音: {narration_text[:80]}...")
        
        print("="*80)
        
        logger.info("=" * 60)
        logger.info("步骤3: 验证流程完整性")
        logger.info("=" * 60)
        
        # 验证数据完整性
        validation_results = validate_workflow_results(narration_result, script_result, target_duration)
        
        for category, checks in validation_results.items():
            logger.info(f"{category}:")
            for check_name, (passed, message) in checks.items():
                status = "PASS" if passed else "FAIL"
                logger.info(f"    {status} {check_name}: {message}")
        
        logger.info("=" * 60)
        logger.info("新工作流程测试完成!")
        logger.info("=" * 60)
        
        return True
        
    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        logger.error(f"错误详情: {traceback.format_exc()}")
        return False


def validate_workflow_results(narration_result, script_result, target_duration):
    """验证工作流程结果的完整性"""
    
    validation_results = {
        "口播文案验证": {},
        "分镜脚本验证": {},
        "时长控制验证": {}
    }
    
    # 口播文案验证
    narration = narration_result.get('narration', '')
    validation_results["口播文案验证"]["文案长度"] = (
        len(narration) > 50, 
        f"{len(narration)} 字符"
    )
    validation_results["口播文案验证"]["预估时长"] = (
        narration_result.get('estimated_duration', 0) > 0,
        f"{narration_result.get('estimated_duration', 0)} 秒"
    )
    validation_results["口播文案验证"]["分段数量"] = (
        len(narration_result.get('segments', [])) > 0,
        f"{len(narration_result.get('segments', []))} 段"
    )
    
    # 分镜脚本验证  
    shots = script_result.get('shots', [])
    validation_results["分镜脚本验证"]["分镜数量"] = (
        len(shots) >= 8 and len(shots) <= 15,
        f"{len(shots)} 个分镜"
    )
    
    dynamic_shots = len([s for s in shots if s.get('type') == 'dynamic'])
    validation_results["分镜脚本验证"]["动态分镜"] = (
        dynamic_shots == 3,
        f"{dynamic_shots} 个动态分镜"
    )
    
    all_have_descriptions = all(s.get('visual_description') for s in shots)
    validation_results["分镜脚本验证"]["描述完整性"] = (
        all_have_descriptions,
        "所有分镜都有视觉描述" if all_have_descriptions else "部分分镜缺少描述"
    )
    
    # 时长控制验证
    total_duration = script_result.get('total_duration', 0)
    duration_diff = abs(total_duration - target_duration)
    validation_results["时长控制验证"]["总时长准确性"] = (
        duration_diff <= 10,
        f"目标{target_duration}秒, 实际{total_duration}秒, 差异{duration_diff}秒"
    )
    
    shot_durations = [s.get('duration', 0) for s in shots]
    min_duration = min(shot_durations) if shot_durations else 0
    max_duration = max(shot_durations) if shot_durations else 0
    validation_results["时长控制验证"]["分镜时长范围"] = (
        min_duration >= 5 and max_duration <= 30,
        f"范围 {min_duration}-{max_duration} 秒"
    )
    
    return validation_results


async def main():
    """主函数"""
    print("开始测试新的智能分镜工作流程...")
    print("基于口播文案 -> 智能分镜决策 -> 分镜脚本生成")
    print()
    
    success = await test_new_workflow()
    
    if success:
        print("\n测试成功! 新工作流程可以正常运行")
        print("\n下一步操作建议:")
        print("   1. 检查生成的口播文案是否符合预期")  
        print("   2. 确认分镜脚本的视觉描述是否详细")
        print("   3. 运行完整的视频生成流程测试")
        print("   4. 根据测试结果调整配置参数")
    else:
        print("\n测试失败! 请检查错误信息并修复问题")
        print("\n常见问题排查:")
        print("   1. 检查API密钥和endpoint配置")
        print("   2. 确认网络连接正常")  
        print("   3. 查看日志文件了解详细错误信息")
        return 1
    
    return 0


if __name__ == "__main__":
    # 设置Windows编码
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    
    # 运行测试
    exit_code = asyncio.run(main())
    sys.exit(exit_code)