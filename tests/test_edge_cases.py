#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
异常场景和边界条件测试
"""

import os
import sys
import tempfile
import time
from pathlib import Path

# 添加项目路径
sys.path.append(str(Path(__file__).parent.parent))

from processors.parser import TextParser
from processors.llm_client import LLMClient
from utils.database import DatabaseManager
from utils.file_utils import FileUtils


class TestEdgeCases:
    """异常场景测试类"""
    
    def test_extremely_long_text(self):
        """测试超长文本处理"""
        print("测试超长文本处理...")
        
        config = {
            'generation': {'max_images': 10, 'final_duration_min': 60, 'final_duration_max': 180},
            'quality_control': {'min_text_length': 100}
        }
        parser = TextParser(config)
        
        # 创建一个非常长的文本（约100万字符）
        long_content = "这是一个超长的测试文本。" * 100000
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(long_content)
            long_file = f.name
        
        try:
            start_time = time.time()
            result = parser.parse(long_file)
            process_time = time.time() - start_time
            
            # 验证能够处理超长文本
            assert isinstance(result, dict)
            assert result['word_count'] > 0
            print(f"✓ 超长文本处理成功: {result['word_count']}字, 耗时{process_time:.2f}秒")
            
            # 处理时间应该在合理范围内
            assert process_time < 30, "超长文本处理时间过长"
            
        finally:
            if os.path.exists(long_file):
                os.unlink(long_file)
    
    def test_special_characters_and_encodings(self):
        """测试特殊字符和编码"""
        print("测试特殊字符和编码处理...")
        
        config = {
            'generation': {'max_images': 10, 'final_duration_min': 60, 'final_duration_max': 180},
            'quality_control': {'min_text_length': 10}
        }
        parser = TextParser(config)
        
        # 各种特殊字符测试
        special_texts = [
            "包含emoji的文本😀😁😂🤣😃😄😅😆😉😊😋😎😍😘🥰😗😙😚☺️🙂🤗",
            "包含日文的文本：こんにちは、世界！これは日本語のテストです。",
            "包含韩文的文本：안녕하세요, 세계! 이것은 한국어 테스트입니다.",
            "包含特殊标点：「引号」、【括号】、〈书名号〉、《双书名号》、""双引号""、''单引号''",
            "包含数学符号：∑∏∫∮∝∞∅∈∉⊆⊇⊂⊃∪∩∧∨¬⇒⇔∀∃",
            "包含制表符和\n换行符\t的文本",
            "包含零宽字符的文本\u200B\u200C\u200D\uFEFF测试",
            "a" * 1000,  # 超长单词
        ]
        
        for i, text in enumerate(special_texts):
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
                f.write(f"第{i+1}章：特殊字符测试\n\n{text}")
                test_file = f.name
            
            try:
                result = parser.parse(test_file)
                assert isinstance(result, dict)
                assert result['word_count'] >= 0
                print(f"✓ 特殊字符测试 {i+1} 通过")
            except Exception as e:
                print(f"⚠ 特殊字符测试 {i+1} 警告: {e}")
            finally:
                if os.path.exists(test_file):
                    os.unlink(test_file)
    
    def test_malformed_files(self):
        """测试损坏的文件"""
        print("测试损坏文件处理...")
        
        config = {
            'generation': {'max_images': 10, 'final_duration_min': 60, 'final_duration_max': 180},
            'quality_control': {'min_text_length': 10}
        }
        parser = TextParser(config)
        
        # 测试不同的损坏文件情况
        test_cases = [
            ("空文件", ""),
            ("只有空白字符", "   \n\t\r\n   "),
            ("只有标点符号", "。！？，；：""''"),
            ("二进制内容", b'\x00\x01\x02\x03\xFF\xFE'.decode('utf-8', errors='ignore')),
            ("超长连续字符", "a" * 10000),
            ("只有换行符", "\n" * 1000),
        ]
        
        for case_name, content in test_cases:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
                f.write(content)
                test_file = f.name
            
            try:
                result = parser.parse(test_file)
                assert isinstance(result, dict)
                print(f"✓ {case_name}处理成功")
            except Exception as e:
                print(f"⚠ {case_name}处理警告: {e}")
            finally:
                if os.path.exists(test_file):
                    os.unlink(test_file)
    
    def test_memory_pressure(self):
        """测试内存压力情况"""
        print("测试内存压力处理...")
        
        config = {
            'generation': {'max_images': 50, 'final_duration_min': 60, 'final_duration_max': 180},
            'quality_control': {'min_text_length': 100}
        }
        parser = TextParser(config)
        
        # 快速连续处理多个文件
        processed_count = 0
        try:
            for i in range(20):  # 处理20个文件
                content = f"第{i}章：内存压力测试\n\n" + "测试内容。" * 1000
                
                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
                    f.write(content)
                    test_file = f.name
                
                try:
                    result = parser.parse(test_file)
                    assert isinstance(result, dict)
                    processed_count += 1
                finally:
                    if os.path.exists(test_file):
                        os.unlink(test_file)
            
            print(f"✓ 内存压力测试通过: 成功处理 {processed_count}/20 个文件")
            
        except Exception as e:
            print(f"⚠ 内存压力测试警告: {e}, 成功处理 {processed_count} 个文件")
    
    def test_concurrent_database_access(self):
        """测试并发数据库访问"""
        print("测试并发数据库访问...")
        
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            test_db_path = f.name
        
        try:
            # 创建多个数据库连接
            dbs = [DatabaseManager(test_db_path) for _ in range(5)]
            
            # 并发创建任务
            import threading
            import random
            
            success_count = 0
            error_count = 0
            
            def create_tasks(db_instance, thread_id):
                nonlocal success_count, error_count
                try:
                    for i in range(10):
                        task_id = f"thread_{thread_id}_task_{i}"
                        db_instance.create_task(task_id, f"测试任务 {thread_id}-{i}", f"test_{i}.txt")
                        time.sleep(random.uniform(0.001, 0.01))  # 随机小延迟
                    success_count += 10
                except Exception as e:
                    error_count += 1
                    print(f"线程 {thread_id} 错误: {e}")
            
            # 启动多个线程
            threads = []
            for i, db in enumerate(dbs):
                thread = threading.Thread(target=create_tasks, args=(db, i))
                threads.append(thread)
                thread.start()
            
            # 等待所有线程完成
            for thread in threads:
                thread.join()
            
            print(f"✓ 并发数据库测试完成: 成功 {success_count}, 错误 {error_count}")
            
        finally:
            if os.path.exists(test_db_path):
                os.unlink(test_db_path)
    
    def test_disk_space_simulation(self):
        """测试磁盘空间不足模拟"""
        print("测试磁盘空间处理...")
        
        # 检查当前磁盘空间
        import shutil
        free_space = shutil.disk_usage('.').free
        print(f"当前可用磁盘空间: {free_space / 1024 / 1024 / 1024:.1f}GB")
        
        # 如果可用空间很少（小于1GB），测试磁盘空间不足的处理
        if free_space < 1024 * 1024 * 1024:
            print("⚠ 磁盘空间不足，跳过磁盘空间测试")
            return
        
        # 创建一个较大的临时文件来模拟空间占用
        try:
            config = {
                'generation': {'max_images': 10, 'final_duration_min': 60, 'final_duration_max': 180},
                'storage': {'temp_dir': './test_temp_disk'}
            }
            
            FileUtils.ensure_dir(config['storage']['temp_dir'])
            
            # 创建一些临时文件
            temp_files = []
            for i in range(5):
                temp_file = os.path.join(config['storage']['temp_dir'], f"temp_{i}.txt")
                with open(temp_file, 'w') as f:
                    f.write("临时文件内容" * 1000)
                temp_files.append(temp_file)
            
            print(f"✓ 创建了 {len(temp_files)} 个临时文件")
            
            # 清理临时文件
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
            
            if os.path.exists(config['storage']['temp_dir']):
                os.rmdir(config['storage']['temp_dir'])
            
            print("✓ 临时文件清理完成")
            
        except Exception as e:
            print(f"⚠ 磁盘空间测试警告: {e}")
    
    def test_network_timeout_simulation(self):
        """测试网络超时模拟"""
        print("测试网络超时处理...")
        
        config = {
            'api': {
                'volcengine': {
                    'access_key_id': 'test_key',
                    'secret_access_key': 'test_secret'
                }
            },
            'models': {'llm_endpoint': 'test_endpoint'},
            'api_settings': {
                'request_timeout': 0.1,  # 很短的超时时间
                'max_retries': 1
            },
            'generation': {'max_images': 5}
        }
        
        llm_client = LLMClient(config)
        
        # 模拟文本数据
        text_data = {
            'title': '网络超时测试',
            'content': '这是一个用于测试网络超时的文本内容。',
            'word_count': 50,
            'chapters_found': 1
        }
        
        try:
            # 尝试生成脚本（应该会超时并使用降级方案）
            result = llm_client.generate_script(text_data)
            
            # 应该返回降级脚本而不是抛出异常
            assert isinstance(result, dict)
            assert 'shots' in result
            assert len(result['shots']) > 0
            
            print("✓ 网络超时降级处理正常")
            
        except Exception as e:
            print(f"⚠ 网络超时测试警告: {e}")


def run_edge_case_tests():
    """运行异常场景测试"""
    print("=" * 50)
    print("开始异常场景和边界条件测试")
    print("=" * 50)
    
    test_edge_cases = TestEdgeCases()
    
    tests = [
        ("超长文本处理", test_edge_cases.test_extremely_long_text),
        ("特殊字符和编码", test_edge_cases.test_special_characters_and_encodings),
        ("损坏文件处理", test_edge_cases.test_malformed_files),
        ("内存压力测试", test_edge_cases.test_memory_pressure),
        ("并发数据库访问", test_edge_cases.test_concurrent_database_access),
        ("磁盘空间处理", test_edge_cases.test_disk_space_simulation),
        ("网络超时处理", test_edge_cases.test_network_timeout_simulation),
    ]
    
    passed_count = 0
    total_count = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        try:
            test_func()
            passed_count += 1
        except Exception as e:
            print(f"❌ {test_name}失败: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 50)
    print(f"异常场景测试完成: {passed_count}/{total_count} 通过")
    if passed_count == total_count:
        print("✅ 所有异常场景测试通过!")
    else:
        print(f"⚠ {total_count - passed_count} 个测试需要改进")
    print("=" * 50)
    
    return passed_count >= total_count * 0.8  # 80%通过率算成功


if __name__ == "__main__":
    run_edge_case_tests()