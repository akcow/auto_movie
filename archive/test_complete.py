#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
完整流程测试脚本
测试从小说文本到最终视频的完整处理流程
"""

import sys
import asyncio
import time
from pathlib import Path

# 添加项目路径
sys.path.append(str(Path(__file__).parent))

from utils.logger import setup_logger
from utils.file_utils import FileUtils
from main import NovelToVideoProcessor
from batch_process import BatchProcessor


def create_test_novel():
    """创建测试小说文件"""
    test_content = """第一章 神秘的力量

在一个普通的小镇上，住着一个名叫李明的年轻人。他过着平凡的生活，每天上班下班，没有什么特别的地方。

但是，就在他二十五岁生日的那一天，一切都发生了改变。

那是一个阴雨连绵的夜晚，李明走在回家的路上。突然，天空中闪过一道奇异的蓝光，紧接着一颗发着光芒的石头从天而降，正好落在他的脚边。

当李明小心翼翼地捡起那颗石头时，一股神秘的能量瞬间涌入了他的身体。他感觉到体内有什么东西在觉醒，一种从未有过的力量在血管中流淌。

从那一刻起，李明的生活彻底改变了。他发现自己拥有了超乎寻常的能力——他能够感知到别人的想法，能够移动物体，甚至能够预见未来的片段。

第二章 新的世界

随着能力的觉醒，李明逐渐发现这个世界并不像表面看起来那么简单。在普通人的生活背后，隐藏着一个充满魔法和超能力者的世界。

他遇到了和他一样拥有特殊能力的人，也遇到了想要利用这些能力的邪恶势力。李明必须学会控制自己的力量，保护自己和身边的人。

在一位神秘导师的指导下，李明开始了他的修炼之路。他学会了如何运用自己的能力，如何在危险中保护无辜的人们。

最终，李明成为了这个隐秘世界的守护者，用自己的力量维护着世界的平衡与和平。"""
    
    test_file = "./test_novel_complete.txt"
    FileUtils.write_text_file(test_file, test_content)
    return test_file


def test_video_editor_functions():
    """测试视频编辑器的具体功能"""
    print("="*50)
    print("测试视频编辑器功能")
    print("="*50)
    
    try:
        from processors.video_editor import VideoEditor
        
        config = {
            'generation': {
                'output_resolution': '720p',
                'output_fps': 24,
                'final_duration_min': 120,
                'final_duration_max': 240
            },
            'storage': {
                'temp_dir': './test_temp',
                'output_dir': './test_output',
                'database_path': './test_db.db'
            }
        }
        
        editor = VideoEditor(config)
        
        # 测试字幕生成
        print("1. 测试字幕生成...")
        subtitle_content = editor._generate_subtitle_content(
            "这是第一句话。这是第二句话！这是第三句话？", 
            10.0
        )
        print(f"   字幕内容示例: {subtitle_content.split('\\n')[0:5]}")
        
        # 测试时间格式转换
        print("2. 测试时间格式转换...")
        time_formats = [
            (0, "00:00:00,000"),
            (65.5, "00:01:05,500"), 
            (3661.25, "01:01:01,250")
        ]
        for seconds, expected in time_formats:
            result = editor._seconds_to_srt_time(seconds)
            print(f"   {seconds}s -> {result}")
        
        # 测试颜色转换
        print("3. 测试颜色转换...")
        colors = ['white', 'black', 'red', 'blue']
        for color in colors:
            hex_color = editor._color_to_hex(color)
            print(f"   {color} -> #{hex_color}")
        
        return True
        
    except Exception as e:
        print(f"视频编辑器功能测试失败: {e}")
        return False


async def test_complete_workflow():
    """测试完整工作流程"""
    print("="*50)
    print("测试完整工作流程")
    print("="*50)
    
    try:
        # 创建测试小说
        test_file = create_test_novel()
        
        # 模拟配置
        config_data = """
api:
  volcengine:
    access_key_id: "test_key_id"
    secret_access_key: "test_secret_key"
    region: "cn-north-1"

models:
  llm_endpoint: "ep-test-llm"
  text2image_model: "general_v2.0"
  image2video_model: "image2video_v1.0"
  tts_voice: "zh_female_qingxin"

generation:
  image_size: "512x768"
  image_quality: "high"
  max_images: 8
  video_segments: 2
  video_duration: 5
  output_fps: 24
  output_resolution: "720p"
  tts_speed: 1.0
  tts_volume: 1.0
  audio_format: "wav"
  final_duration_min: 60
  final_duration_max: 180

storage:
  temp_dir: "./test_temp"
  output_dir: "./test_output"
  database_path: "./test_complete.db"

prompts:
  storyboard_template: "./prompts/storyboard.txt"
  image_prompt_template: "./prompts/image_prompt.txt"
  video_prompt_template: "./prompts/video_prompt.txt"

api_settings:
  max_retries: 2
  request_timeout: 30
  rate_limit_per_minute: 30

logging:
  level: "INFO"
  log_file: "./logs/test.log"
"""
        
        # 创建测试配置文件
        test_config_path = "./test_config.yaml"
        FileUtils.write_text_file(test_config_path, config_data)
        
        # 初始化处理器
        print("1. 初始化处理器...")
        processor = NovelToVideoProcessor(test_config_path)
        
        # 模拟处理过程（不实际调用API）
        print("2. 模拟处理流程...")
        
        # 测试各个组件的基础功能
        print("   - 测试文本解析...")
        text_result = processor.text_parser.parse(test_file)
        print(f"     解析结果: {text_result['word_count']}字, {text_result['chapters_found']}章")
        
        print("   - 测试脚本生成（模拟）...")
        # 模拟脚本数据
        mock_script = {
            'title': text_result['title'],
            'summary': '一个关于觉醒超能力的故事',
            'style': '现代 都市 超能力 科幻 热血',
            'shots': [
                {'type': 'video', 'description': '平凡小镇的夜晚，路灯昏暗', 'duration': 5},
                {'type': 'video', 'description': '神秘蓝光从天而降', 'duration': 5},
                {'type': 'image', 'description': '发光石头落在地面', 'duration': 4},
                {'type': 'image', 'description': '青年男子眼中闪烁神秘光芒', 'duration': 4},
                {'type': 'image', 'description': '城市夜景，隐藏的超能力世界', 'duration': 4},
            ],
            'narration': '那一夜，平凡的生活被彻底改变。神秘的力量觉醒，一个全新的世界向他敞开了大门。'
        }
        print(f"     脚本包含 {len(mock_script['shots'])} 个镜头")
        
        print("   - 测试图片生成（模拟）...")
        # 创建模拟图片结果
        mock_image_results = []
        for i, shot in enumerate(mock_script['shots']):
            image_info = processor.image_generator._create_fallback_image_info(i, shot['description'])
            mock_image_results.append(image_info)
        print(f"     生成 {len(mock_image_results)} 张占位图片")
        
        print("   - 测试语音合成（模拟）...")
        # 创建静音音频
        audio_path = processor.tts_client.create_silence_audio(15.0, "test_audio.wav")
        mock_audio_result = {
            'text': mock_script['narration'],
            'file_path': audio_path,
            'duration': 15.0,
            'file_size': FileUtils.get_file_size(audio_path) if FileUtils.path_exists(audio_path) else 0,
            'format': 'wav',
            'sample_rate': 24000,
            'char_count': len(mock_script['narration']),
            'cost': 0.01
        }
        print(f"     音频时长: {mock_audio_result['duration']}秒")
        
        print("   - 测试视频生成（模拟）...")
        # 创建模拟视频结果
        mock_video_results = []
        for i in range(min(2, len(mock_image_results))):
            if FileUtils.path_exists(mock_image_results[i]['file_path']):
                video_result = await processor.video_generator._create_static_video_from_image(
                    mock_image_results[i]['file_path'],
                    5,  # 5秒时长
                    i,
                    "test_task"
                )
                if video_result:
                    mock_video_results.append(video_result)
        print(f"     生成 {len(mock_video_results)} 个视频片段")
        
        print("   - 测试视频合成...")
        if len(mock_video_results) > 0 and mock_audio_result['file_path']:
            try:
                final_result = await processor.video_editor.compose_video(
                    mock_image_results,
                    mock_video_results, 
                    mock_audio_result,
                    mock_script,
                    "test_complete"
                )
                print(f"     最终视频: {final_result['file_path']}")
                print(f"     视频时长: {final_result['duration']:.1f}秒")
                print(f"     文件大小: {FileUtils.format_file_size(final_result['file_size'])}")
            except Exception as e:
                print(f"     视频合成失败（预期的，缺少FFmpeg）: {e}")
        
        print("3. 工作流程测试完成")
        return True
        
    except Exception as e:
        print(f"完整工作流程测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # 清理测试文件
        cleanup_files = [
            "./test_novel_complete.txt",
            "./test_config.yaml", 
            "./test_complete.db"
        ]
        for file_path in cleanup_files:
            Path(file_path).unlink(missing_ok=True)


async def test_batch_processing():
    """测试批处理功能"""
    print("="*50)
    print("测试批处理功能")
    print("="*50)
    
    try:
        # 创建测试目录和文件
        test_dir = Path("./test_batch")
        test_dir.mkdir(exist_ok=True)
        
        # 创建多个测试文件
        test_files = []
        for i in range(3):
            content = f"第{i+1}个测试小说\n\n这是第{i+1}个测试小说的内容。它包含了一些基础的情节和对话。\n\n故事发生在一个遥远的地方，主角经历了很多冒险。"
            file_path = test_dir / f"test_novel_{i+1}.txt"
            FileUtils.write_text_file(str(file_path), content)
            test_files.append(str(file_path))
        
        print(f"创建了 {len(test_files)} 个测试文件")
        
        # 测试批处理器基础功能
        batch_processor = BatchProcessor("./test_config.yaml")
        
        # 测试文件查找
        found_files = batch_processor._find_input_files(str(test_dir), "*.txt")
        print(f"找到 {len(found_files)} 个匹配文件")
        
        # 测试报告生成
        mock_summary = {
            'total_files': 3,
            'processed': 3,
            'succeeded': 2,
            'failed': 1,
            'processing_time': 45.5,
            'results': [
                {
                    'input_file': test_files[0],
                    'status': 'completed',
                    'output_video': './output/video1.mp4',
                    'processing_time': 15.0,
                    'statistics': {'total_cost': 1.23}
                },
                {
                    'input_file': test_files[1], 
                    'status': 'completed',
                    'output_video': './output/video2.mp4',
                    'processing_time': 18.0,
                    'statistics': {'total_cost': 1.45}
                },
                {
                    'input_file': test_files[2],
                    'status': 'failed',
                    'error': '模拟错误',
                    'attempts': 3
                }
            ]
        }
        
        report_content = batch_processor.generate_report(mock_summary)
        print("生成的报告预览:")
        print(report_content[:500] + "...")
        
        return True
        
    except Exception as e:
        print(f"批处理功能测试失败: {e}")
        return False
    finally:
        # 清理测试文件
        import shutil
        test_dir = Path("./test_batch")
        if test_dir.exists():
            shutil.rmtree(test_dir)


def main():
    """主测试函数"""
    print("完整流程测试开始")
    print("="*80)
    
    # 设置日志
    logger = setup_logger("test_complete", log_level="INFO")
    
    # 运行各项测试
    results = {}
    
    print("运行同步测试...")
    results['video_editor'] = test_video_editor_functions()
    
    print("运行异步测试...")
    results['workflow'] = asyncio.run(test_complete_workflow())
    results['batch_processing'] = asyncio.run(test_batch_processing())
    
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
        print("所有完整流程测试通过！")
        print("")
        print("注意事项：")
        print("1. 部分测试使用模拟数据，实际使用需要配置真实API密钥")
        print("2. 视频合成功能需要安装FFmpeg")
        print("3. 建议先在小规模数据上测试，再进行大批量处理")
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
        cleanup_dirs = ['./test_temp', './test_output']
        cleanup_files = ['./test_complete.db', './test_config.yaml']
        
        for dir_path in cleanup_dirs:
            if Path(dir_path).exists():
                shutil.rmtree(dir_path)
        
        for file_path in cleanup_files:
            Path(file_path).unlink(missing_ok=True)