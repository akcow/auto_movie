#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Day 6 增强功能测试脚本
测试字幕系统、视频效果、转场等新功能
"""

import asyncio
import os
import sys
import time
import tempfile
import shutil
from pathlib import Path

# 添加项目路径
sys.path.append(str(Path(__file__).parent))

from utils.file_utils import load_config, FileUtils
from processors.video_editor import VideoEditor


def create_test_config():
    """创建测试配置"""
    return {
        'generation': {
            'output_resolution': '720p',
            'output_fps': 24,
            'final_duration_min': 60,
            'final_duration_max': 120
        },
        'storage': {
            'temp_dir': './test_temp_day6',
            'output_dir': './test_output_day6',
            'database_path': './test_day6.db'
        },
        'quality_control': {
            'video_quality': 'medium'
        },
        'subtitle': {
            'font_size': 32,
            'font_family': 'Arial Black',
            'font_color': 'white',
            'outline_color': 'black',
            'outline_width': 2,
            'shadow_color': 'gray',
            'shadow_offset': 2,
            'position': 'bottom',
            'margin': 40,
            'alignment': 'center',
            'fade_in': True,
            'fade_duration': 0.5
        },
        'video_effects': {
            'enable_static_motion': True,
            'enable_transitions': False,  # 先关闭转场效果测试
            'stabilization': False,
            'denoise': False,
            'sharpen': False,
            'enhance_colors': True
        }
    }


def create_test_image(image_path: str, width: int = 512, height: int = 768):
    """创建测试图片"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        
        # 创建纯色背景
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8']
        img_index = hash(image_path) % len(colors)
        
        img = Image.new('RGB', (width, height), colors[img_index])
        draw = ImageDraw.Draw(img)
        
        # 添加文字
        try:
            font = ImageFont.truetype("arial.ttf", 60)
        except:
            font = ImageFont.load_default()
        
        text = f"测试图片 {os.path.basename(image_path)}"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        x = (width - text_width) // 2
        y = (height - text_height) // 2
        
        draw.text((x, y), text, fill='white', font=font)
        
        img.save(image_path)
        print(f"创建测试图片: {image_path}")
        
    except ImportError:
        print("PIL未安装，跳过图片创建")
    except Exception as e:
        print(f"创建测试图片失败: {e}")


async def test_subtitle_system():
    """测试字幕系统"""
    print("\n=== 测试字幕系统 ===")
    
    config = create_test_config()
    editor = VideoEditor(config)
    
    # 测试智能文本分割
    test_text = "这是一个测试句子。这是另一个测试句子！这是第三个很长很长很长很长的测试句子，需要进行分割处理。"
    sentences = editor._smart_text_split(test_text)
    print(f"文本分割结果: {sentences}")
    
    # 测试字幕内容生成
    subtitle_content = editor._generate_subtitle_content(test_text, 15.0)
    print(f"字幕内容:\n{subtitle_content[:200]}...")
    
    # 测试文本格式化
    long_text = "这是一个非常长的字幕文本，需要进行换行处理"
    formatted_text = editor._format_subtitle_text(long_text)
    print(f"格式化文本: {repr(formatted_text)}")
    
    print("字幕系统测试完成")


async def test_video_effects():
    """测试视频效果"""
    print("\n=== 测试视频效果 ===")
    
    config = create_test_config()
    editor = VideoEditor(config)
    
    # 测试质量参数
    for quality in ['low', 'medium', 'high']:
        params = editor._get_quality_params(quality)
        print(f"{quality}质量参数: {params}")
    
    # 测试视频滤镜构建
    filters = editor._build_video_filters(720, 1280)
    print(f"视频滤镜: {filters}")
    
    # 测试动态效果滤镜
    for motion_type in ['zoom_in', 'zoom_out', 'pan_left', 'pan_right']:
        motion_filter = editor._get_motion_filter(motion_type, 720, 1280, 5)
        print(f"{motion_type}滤镜: {motion_filter[:60]}...")
    
    print("视频效果测试完成")


async def test_color_and_alignment():
    """测试颜色和对齐"""
    print("\n=== 测试颜色和对齐 ===")
    
    config = create_test_config()
    editor = VideoEditor(config)
    
    # 测试颜色转换
    colors = ['white', 'black', 'red', 'blue', 'yellow', 'unknown']
    for color in colors:
        hex_color = editor._color_to_hex(color)
        print(f"{color} -> {hex_color}")
    
    # 测试对齐值
    test_configs = [
        {'position': 'bottom', 'alignment': 'center'},
        {'position': 'top', 'alignment': 'left'},
        {'position': 'center', 'alignment': 'right'}
    ]
    
    for test_config in test_configs:
        editor.subtitle_style.update(test_config)
        alignment_value = editor._get_alignment_value()
        print(f"{test_config} -> {alignment_value}")
    
    print("颜色和对齐测试完成")


async def test_transition_effects():
    """测试转场效果"""
    print("\n=== 测试转场效果 ===")
    
    config = create_test_config()
    editor = VideoEditor(config)
    
    # 测试转场滤镜构建
    transition_types = ['fade', 'dissolve', 'wipeleft', 'wiperight']
    filter_complex = editor._build_transition_filter_complex(
        3, transition_types, 0.5
    )
    print(f"转场滤镜复合: {filter_complex[:100]}...")
    
    print("转场效果测试完成")


async def test_complete_workflow():
    """测试完整工作流程"""
    print("\n=== 测试完整工作流程 ===")
    
    config = create_test_config()
    editor = VideoEditor(config)
    task_id = "test_day6_workflow"
    
    try:
        # 创建测试目录
        temp_dir = config['storage']['temp_dir']
        output_dir = config['storage']['output_dir']
        FileUtils.ensure_dir(temp_dir)
        FileUtils.ensure_dir(output_dir)
        
        # 创建模拟的图片文件
        image_results = []
        for i in range(3):
            image_path = os.path.join(temp_dir, f"test_image_{i}.jpg")
            create_test_image(image_path)
            if os.path.exists(image_path):
                image_results.append({
                    'file_path': image_path,
                    'description': f'测试图片 {i+1}'
                })
        
        if not image_results:
            print("无法创建测试图片，跳过工作流程测试")
            return
            
        # 模拟数据
        video_results = []  # 空的视频结果
        audio_result = {
            'file_path': '',  # 空的音频文件
            'duration': 10.0
        }
        script_data = {
            'title': '测试视频',
            'narration': '这是一个测试视频的旁白内容。用于测试字幕生成和视频合成功能。',
            'shots': [
                {'duration': 4, 'description': '第一个镜头'},
                {'duration': 3, 'description': '第二个镜头'},
                {'duration': 3, 'description': '第三个镜头'}
            ]
        }
        
        # 测试视频片段创建
        print("创建视频片段...")
        segments = await editor._create_video_segments(
            image_results, video_results, script_data, task_id
        )
        print(f"创建了 {len(segments)} 个视频片段")
        
        # 验证创建的片段
        for i, segment in enumerate(segments):
            if segment['file_path'] and os.path.exists(segment['file_path']):
                file_size = os.path.getsize(segment['file_path'])
                print(f"片段 {i+1}: {segment['type']}, 大小: {file_size} bytes")
        
        # 测试字幕创建
        print("创建字幕...")
        subtitle_file = await editor._create_subtitles(script_data, audio_result, task_id)
        if subtitle_file and os.path.exists(subtitle_file):
            with open(subtitle_file, 'r', encoding='utf-8') as f:
                subtitle_preview = f.read()[:200]
            print(f"字幕预览: {subtitle_preview}...")
        
        print("完整工作流程测试完成")
        
    except Exception as e:
        print(f"工作流程测试失败: {e}")


async def main():
    """主测试函数"""
    print("开始Day 6增强功能测试...")
    
    try:
        # 运行各项测试
        await test_subtitle_system()
        await test_video_effects()
        await test_color_and_alignment()
        await test_transition_effects()
        await test_complete_workflow()
        
        print("\n所有测试完成!")
        
    except Exception as e:
        print(f"测试失败: {e}")
    finally:
        # 清理测试文件
        cleanup_paths = ['./test_temp_day6', './test_output_day6', './test_day6.db']
        for path in cleanup_paths:
            try:
                if os.path.exists(path):
                    if os.path.isdir(path):
                        shutil.rmtree(path)
                    else:
                        os.remove(path)
            except Exception:
                pass


if __name__ == "__main__":
    asyncio.run(main())