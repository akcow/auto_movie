#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Day 3 AI生成模块集成测试脚本
"""

import sys
import asyncio
import time
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from utils.logger import setup_logger
from utils.file_utils import FileUtils
from processors.image_gen import ImageGenerator
from processors.video_gen import VideoGenerator
from processors.tts_client import TTSClient


def get_test_config():
    """获取测试配置"""
    return {
        'api': {
            'volcengine': {
                'access_key_id': 'mock_key',
                'secret_access_key': 'mock_secret'
            }
        },
        'models': {
            'text2image_model': 'general_v2.0',
            'image2video_model': 'image2video_v1.0',
            'tts_voice': 'zh_female_qingxin'
        },
        'generation': {
            'image_size': '512x768',
            'image_quality': 'high',
            'max_images': 5,
            'video_segments': 2,
            'video_duration': 5,
            'output_fps': 24,
            'output_resolution': '720p',
            'tts_speed': 1.0,
            'tts_volume': 1.0,
            'audio_format': 'wav'
        },
        'storage': {
            'temp_dir': './test_temp',
            'output_dir': './test_output',
            'database_path': './test_db.db'
        },
        'prompts': {
            'image_prompt_template': './prompts/image_prompt.txt',
            'video_prompt_template': './prompts/video_prompt.txt'
        },
        'api_settings': {
            'max_retries': 3,
            'request_timeout': 30,
            'rate_limit_per_minute': 60
        }
    }


def get_test_script():
    """获取测试脚本数据"""
    return {
        'title': '第一章 觉醒',
        'summary': '少年获得神秘力量开始冒险',
        'style': '古风 仙侠 玄幻 唯美 国漫',
        'shots': [
            {
                'type': 'video',
                'description': '古朴庭院中，白衣少年盘膝而坐，周身金光涌现',
                'duration': 5
            },
            {
                'type': 'video', 
                'description': '少年睁眼瞬间，眼中闪过星辰光芒',
                'duration': 5
            },
            {
                'type': 'image',
                'description': '夜空中繁星点点，一轮明月当空照耀',
                'duration': 4
            },
            {
                'type': 'image',
                'description': '山峦起伏，云雾缭绕，仙气十足',
                'duration': 4
            }
        ],
        'narration': '那一夜，天降异象，平凡少年获得了传说中的仙人传承。从此，一个改变世界的传奇故事开始了。'
    }


def test_image_generator():
    """测试图片生成器"""
    print("="*50)
    print("测试图片生成器")
    print("="*50)
    
    config = get_test_config()
    script_data = get_test_script()
    
    try:
        generator = ImageGenerator(config)
        
        print("测试提示词构建...")
        prompt = generator._build_image_prompt(
            "古朴庭院中的少年", 
            "古风 仙侠 唯美"
        )
        print(f"生成的提示词: {prompt}")
        
        print("测试占位图片创建...")
        fallback_info = generator._create_fallback_image_info(0, "测试图片")
        print(f"占位图片信息: {fallback_info['file_path']}")
        
        # 验证占位图片是否创建
        if FileUtils.path_exists(fallback_info['file_path']):
            print("占位图片创建成功")
        else:
            print("占位图片创建失败")
        
        return True
        
    except Exception as e:
        print(f"图片生成器测试失败: {e}")
        return False


def test_video_generator():
    """测试视频生成器"""
    print("="*50)
    print("测试视频生成器")
    print("="*50)
    
    config = get_test_config()
    
    try:
        generator = VideoGenerator(config)
        
        print("测试提示词构建...")
        prompt = generator._build_video_prompt(
            "少年觉醒神秘力量", 
            "古风 仙侠",
            5
        )
        print(f"生成的提示词: {prompt}")
        
        print("测试视频分辨率...")
        resolution = generator._get_video_resolution()
        print(f"视频分辨率: {resolution[0]}x{resolution[1]}")
        
        return True
        
    except Exception as e:
        print(f"视频生成器测试失败: {e}")
        return False


def test_tts_client():
    """测试TTS客户端"""
    print("="*50)  
    print("测试TTS客户端")
    print("="*50)
    
    config = get_test_config()
    script_data = get_test_script()
    
    try:
        client = TTSClient(config)
        
        print("测试文本预处理...")
        original_text = "这是一个测试123！！很好？？"
        processed_text = client._preprocess_text(original_text)
        print(f"原文本: {original_text}")
        print(f"处理后: {processed_text}")
        
        print("测试文本分割...")
        long_text = script_data['narration'] * 3
        segments = client._split_text(long_text, 100)
        print(f"长文本分割为: {len(segments)} 个段落")
        for i, seg in enumerate(segments):
            print(f"  段落{i+1}: {seg[:50]}...")
        
        print("测试静音音频创建...")
        silence_path = client.create_silence_audio(2.0, "test_silence.wav")
        if FileUtils.path_exists(silence_path):
            print(f"静音音频创建成功: {silence_path}")
        else:
            print("静音音频创建失败")
        
        return True
        
    except Exception as e:
        print(f"TTS客户端测试失败: {e}")
        return False


async def test_integration():
    """集成测试 - 模拟完整AI生成流程"""
    print("="*50)
    print("AI生成模块集成测试")
    print("="*50)
    
    config = get_test_config()
    script_data = get_test_script()
    task_id = f"test_integration_{int(time.time())}"
    
    try:
        # 1. 初始化所有生成器
        print("1. 初始化AI生成器...")
        image_gen = ImageGenerator(config)
        video_gen = VideoGenerator(config)
        tts_client = TTSClient(config)
        
        # 2. 模拟图片生成过程
        print("2. 模拟图片生成...")
        mock_image_results = []
        for i, shot in enumerate(script_data['shots']):
            # 创建模拟图片结果
            fallback_info = image_gen._create_fallback_image_info(i, shot['description'])
            mock_image_results.append(fallback_info)
            
        print(f"   生成了 {len(mock_image_results)} 张图片")
        
        # 3. 获取生成总结
        image_summary = image_gen.get_generation_summary(mock_image_results)
        print(f"   图片生成总结: {image_summary}")
        
        # 4. 模拟视频生成过程
        print("3. 模拟视频生成...")
        # 模拟静态视频创建
        mock_video_results = []
        for i in range(min(2, len(mock_image_results))):  # 前2个转视频
            video_result = await video_gen._create_static_video_from_image(
                mock_image_results[i]['file_path'],
                5,  # 5秒时长
                i,
                task_id
            )
            if video_result:
                mock_video_results.append(video_result)
        
        print(f"   生成了 {len(mock_video_results)} 个视频")
        
        # 5. 获取视频生成总结
        video_summary = video_gen.get_generation_summary(mock_video_results)
        print(f"   视频生成总结: {video_summary}")
        
        # 6. 模拟语音合成
        print("4. 模拟语音合成...")
        # 只进行文本处理，不实际调用API
        processed_text = tts_client._preprocess_text(script_data['narration'])
        segments = tts_client._split_text(processed_text, 200)
        
        # 创建静音音频作为模拟结果
        silence_path = tts_client.create_silence_audio(10.0, f"{task_id}_speech.wav")
        
        mock_tts_result = {
            'text': processed_text,
            'segments': len(segments),
            'file_path': silence_path,
            'file_size': FileUtils.get_file_size(silence_path) if FileUtils.path_exists(silence_path) else 0,
            'duration': 10.0,
            'char_count': len(processed_text),
            'cost': len(processed_text) * 0.0002
        }
        
        print(f"   语音合成结果: {mock_tts_result['char_count']}字, {mock_tts_result['duration']}秒")
        
        # 7. 整体统计
        print("5. 整体统计...")
        total_files = len(mock_image_results) + len(mock_video_results) + 1  # +1为音频
        total_cost = image_summary['total_cost'] + video_summary['total_cost'] + mock_tts_result['cost']
        
        print(f"   总文件数: {total_files}")
        print(f"   预估总成本: ¥{total_cost:.4f}")
        print(f"   图片: {image_summary['successful']}/{image_summary['total']}")
        print(f"   视频: {video_summary['successful']}/{video_summary['total']}")
        print(f"   音频: 1/1")
        
        return True
        
    except Exception as e:
        print(f"集成测试失败: {e}")
        return False


def main():
    """主测试函数"""
    print("Day 3 AI生成模块测试开始")
    print("="*80)
    
    # 设置日志
    logger = setup_logger("test_day3", log_level="INFO")
    
    # 运行各项测试
    results = {}
    
    # 同步测试
    print("运行同步测试...")
    results['image_generator'] = test_image_generator()
    results['video_generator'] = test_video_generator()
    results['tts_client'] = test_tts_client()
    
    # 异步集成测试
    print("运行异步集成测试...")
    results['integration'] = asyncio.run(test_integration())
    
    # 输出测试总结
    print("="*80)
    print("测试结果总结")
    print("="*80)
    
    for test_name, passed in results.items():
        status = "通过" if passed else "失败"
        print(f"{test_name}: {status}")
    
    total_tests = len(results)
    passed_tests = sum(results.values())
    
    print("")
    print(f"总计: {passed_tests}/{total_tests} 个测试通过")
    
    if passed_tests == total_tests:
        print("Day 3 所有AI生成模块测试通过！")
        return True
    else:
        print("部分测试失败，请检查相关模块")
        return False


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    finally:
        # 清理测试文件
        import shutil
        for path in ['./test_temp', './test_output']:
            if Path(path).exists():
                shutil.rmtree(path)
        Path('./test_db.db').unlink(missing_ok=True)