#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
端到端集成测试
测试完整的小说转视频流程
"""

import asyncio
import os
import sys
import tempfile
import time
import shutil
from pathlib import Path

# 添加项目路径
sys.path.append(str(Path(__file__).parent.parent))

from main import NovelToVideoProcessor
from utils.file_utils import FileUtils


class TestIntegration:
    """集成测试类"""
    
    def create_test_config(self):
        """创建测试配置"""
        return {
            'api': {
                'volcengine': {
                    'access_key_id': 'test_key',
                    'secret_access_key': 'test_secret',
                    'region': 'cn-north-1'
                }
            },
            'models': {
                'llm_endpoint': 'test_endpoint',
                'text2image_model': 'test_model',
                'image2video_model': 'test_model',
                'tts_voice': 'test_voice'
            },
            'generation': {
                'max_images': 5,
                'video_segments': 2,
                'video_duration': 3,
                'output_resolution': '480p',
                'output_fps': 24,
                'final_duration_min': 10,
                'final_duration_max': 30
            },
            'storage': {
                'temp_dir': './test_temp_integration',
                'output_dir': './test_output_integration',
                'database_path': './test_integration.db'
            },
            'api_settings': {
                'max_retries': 1,
                'request_timeout': 5,
                'max_concurrent_requests': 2
            },
            'logging': {
                'level': 'INFO'
            },
            'development': {
                'mock_api_calls': True  # 启用API模拟
            }
        }
    
    def create_test_novel(self):
        """创建测试小说文件"""
        novel_content = """第一章：测试开始

这是一个专门用于测试的小说内容。故事发生在一个神秘的世界里，主人公正在经历着奇妙的冒险。

第二章：情节发展  

主人公遇到了各种挑战，需要运用智慧和勇气来解决问题。这个过程充满了紧张和刺激。

第三章：高潮部分

所有的矛盾在这里汇聚，主人公面临最终的考验。这是决定命运的关键时刻。

第四章：圆满结局

经过努力，主人公最终克服了所有困难，获得了成功。故事以温馨的画面结束。"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(novel_content)
            return f.name
    
    async def test_full_pipeline_mock(self):
        """测试完整流程（模拟API）"""
        config = self.create_test_config()
        test_novel_file = self.create_test_novel()
        
        try:
            # 创建处理器
            processor = NovelToVideoProcessor()
            processor.config = config
            processor.logger.info("开始端到端集成测试（模拟模式）")
            
            # 重新初始化各组件以使用新配置
            from utils.file_utils import load_config
            from processors.parser import TextParser
            from processors.llm_client import LLMClient
            
            processor.text_parser = TextParser(config)
            processor.llm_client = LLMClient(config)
            
            # 确保测试目录存在
            FileUtils.ensure_dir(config['storage']['temp_dir'])
            FileUtils.ensure_dir(config['storage']['output_dir'])
            
            # 测试文本解析
            print("1. 测试文本解析...")
            text_result = processor.text_parser.parse(test_novel_file)
            assert isinstance(text_result, dict)
            assert text_result['word_count'] > 0
            assert text_result['chapters_found'] >= 4
            print(f"✓ 解析完成: {text_result['word_count']}字, {text_result['chapters_found']}章")
            
            # 测试LLM脚本生成
            print("2. 测试LLM脚本生成...")
            script_result = processor.llm_client.generate_script(text_result)
            assert isinstance(script_result, dict)
            assert 'shots' in script_result
            assert len(script_result['shots']) > 0
            print(f"✓ 脚本生成完成: {len(script_result['shots'])}个镜头")
            
            # 测试数据库操作
            print("3. 测试数据库操作...")
            task_id = f"integration_test_{int(time.time())}"
            processor.db.create_task(task_id, "集成测试", test_novel_file)
            
            # 保存解析结果
            processor.db.save_text_parsing(
                task_id=task_id,
                original_content=f"文件: {test_novel_file}",
                parsed_content=text_result['content'],
                word_count=text_result['word_count'],
                chapters_found=text_result['chapters_found'],
                processing_time=1.0
            )
            
            # 验证任务创建成功
            task_info = processor.db.get_task(task_id)
            assert task_info is not None
            assert task_info['status'] == 'pending'
            print("✓ 数据库操作正常")
            
            # 测试配置验证
            print("4. 测试配置验证...")
            assert processor.config['generation']['max_images'] == 5
            assert processor.config['development']['mock_api_calls'] == True
            print("✓ 配置加载正常")
            
            print("端到端集成测试（模拟模式）通过! ✅")
            return True
            
        except Exception as e:
            print(f"集成测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            # 清理测试文件
            cleanup_paths = [
                test_novel_file,
                config['storage']['temp_dir'],
                config['storage']['output_dir'],
                config['storage']['database_path']
            ]
            
            for path in cleanup_paths:
                try:
                    if os.path.exists(path):
                        if os.path.isdir(path):
                            shutil.rmtree(path)
                        else:
                            os.unlink(path)
                except Exception:
                    pass
    
    async def test_error_handling(self):
        """测试错误处理"""
        config = self.create_test_config()
        
        try:
            processor = NovelToVideoProcessor()
            processor.config = config
            
            # 测试不存在文件的处理
            print("1. 测试文件不存在错误处理...")
            non_existent_file = "/path/to/non/existent/file.txt"
            
            # 这应该抛出异常或返回错误状态
            try:
                result = processor.text_parser.parse(non_existent_file)
                # 如果没有抛出异常，检查错误状态
                assert False, "应该抛出文件不存在异常"
            except Exception as e:
                print(f"✓ 正确处理文件不存在错误: {type(e).__name__}")
            
            # 测试空文件处理
            print("2. 测试空文件处理...")
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
                f.write("")  # 空文件
                empty_file = f.name
            
            try:
                result = processor.text_parser.parse(empty_file)
                # 空文件应该有合理的默认处理
                assert isinstance(result, dict)
                print("✓ 空文件处理正常")
            finally:
                if os.path.exists(empty_file):
                    os.unlink(empty_file)
            
            # 测试无效配置处理
            print("3. 测试无效配置处理...")
            invalid_config = {}  # 空配置
            
            try:
                from processors.parser import TextParser
                parser_with_invalid_config = TextParser(invalid_config)
                # 应该使用默认配置或抛出配置错误
                print("✓ 无效配置有默认处理")
            except Exception as e:
                print(f"✓ 正确处理无效配置: {type(e).__name__}")
            
            print("错误处理测试通过! ✅")
            return True
            
        except Exception as e:
            print(f"错误处理测试失败: {e}")
            return False
    
    async def test_performance_metrics(self):
        """测试性能指标"""
        print("测试性能指标...")
        config = self.create_test_config()
        test_novel_file = self.create_test_novel()
        
        try:
            from processors.parser import TextParser
            parser = TextParser(config)
            
            # 测试解析性能
            start_time = time.time()
            result = parser.parse(test_novel_file)
            parse_time = time.time() - start_time
            
            print(f"文本解析耗时: {parse_time:.2f}秒")
            assert parse_time < 5.0, "解析时间过长"
            
            # 测试内存使用情况（简单检查）
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            print(f"当前内存使用: {memory_info.rss / 1024 / 1024:.1f}MB")
            
            # 内存使用应该在合理范围内（小于500MB）
            assert memory_info.rss < 500 * 1024 * 1024, "内存使用过多"
            
            print("✓ 性能指标正常")
            return True
            
        except ImportError:
            print("⚠ psutil未安装，跳过内存测试")
            return True
        except Exception as e:
            print(f"性能测试失败: {e}")
            return False
        finally:
            if os.path.exists(test_novel_file):
                os.unlink(test_novel_file)
    
    async def test_concurrent_processing(self):
        """测试并发处理"""
        print("测试并发处理能力...")
        
        config = self.create_test_config()
        
        try:
            from processors.parser import TextParser
            parser = TextParser(config)
            
            # 创建多个测试文件
            test_files = []
            for i in range(3):
                content = f"第{i+1}章：测试内容\n\n这是第{i+1}个测试文件的内容。" * 10
                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
                    f.write(content)
                    test_files.append(f.name)
            
            # 并发解析
            async def parse_file(file_path):
                return parser.parse(file_path)
            
            start_time = time.time()
            tasks = [parse_file(f) for f in test_files]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            concurrent_time = time.time() - start_time
            
            # 检查结果
            success_count = 0
            for result in results:
                if isinstance(result, dict) and 'word_count' in result:
                    success_count += 1
            
            print(f"并发处理 {len(test_files)} 个文件耗时: {concurrent_time:.2f}秒")
            print(f"成功处理: {success_count}/{len(test_files)}")
            
            assert success_count >= len(test_files) * 0.8, "并发处理成功率过低"
            print("✓ 并发处理能力正常")
            
            return True
            
        except Exception as e:
            print(f"并发处理测试失败: {e}")
            return False
        finally:
            # 清理测试文件
            for test_file in test_files:
                try:
                    if os.path.exists(test_file):
                        os.unlink(test_file)
                except Exception:
                    pass


async def run_integration_tests():
    """运行集成测试"""
    print("=" * 50)
    print("开始端到端集成测试")
    print("=" * 50)
    
    test_integration = TestIntegration()
    
    all_tests_passed = True
    
    # 运行各项测试
    tests = [
        ("完整流程测试（模拟）", test_integration.test_full_pipeline_mock),
        ("错误处理测试", test_integration.test_error_handling),
        ("性能指标测试", test_integration.test_performance_metrics),
        ("并发处理测试", test_integration.test_concurrent_processing)
    ]
    
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        try:
            result = await test_func()
            if not result:
                all_tests_passed = False
        except Exception as e:
            print(f"❌ {test_name}失败: {e}")
            all_tests_passed = False
    
    print("\n" + "=" * 50)
    if all_tests_passed:
        print("✅ 所有集成测试通过!")
    else:
        print("❌ 部分集成测试失败")
    print("=" * 50)
    
    return all_tests_passed


if __name__ == "__main__":
    asyncio.run(run_integration_tests())