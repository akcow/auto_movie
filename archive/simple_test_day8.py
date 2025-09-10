#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Day 8 简化测试脚本
避免Unicode字符问题，直接测试核心功能
"""

import sys
import time
import tempfile
import os
from pathlib import Path

# 添加项目路径
sys.path.append(str(Path(__file__).parent))

from processors.parser import TextParser
from processors.llm_client import LLMClient
from utils.database import DatabaseManager
from utils.performance import memory_manager, performance_monitor, resource_cleaner


def test_text_parser():
    """测试文本解析器"""
    print("测试文本解析器...")
    
    config = {
        'generation': {'max_images': 10, 'final_duration_min': 60, 'final_duration_max': 180},
        'quality_control': {'min_text_length': 100}
    }
    
    parser = TextParser(config)
    
    # 创建测试文件
    test_content = """第一章：测试开始
    
这是一个用于测试的小说内容。包含多个章节和段落。

第二章：测试继续

更多的测试内容，用来验证解析器的功能。

第三章：测试结束

这是最后一章的内容。"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        f.write(test_content)
        test_file = f.name
    
    try:
        # 运行测试
        result = parser.parse(test_file)
        
        # 验证结果
        assert isinstance(result, dict)
        assert 'content' in result
        assert 'word_count' in result
        assert 'chapters_found' in result
        assert result['chapters_found'] >= 3
        
        print(f"  - 检测到 {result['chapters_found']} 个章节")
        print(f"  - 统计字数: {result['word_count']}")
        print("  - 文本解析器测试通过")
        return True
        
    except Exception as e:
        print(f"  - 文本解析器测试失败: {e}")
        return False
    finally:
        if os.path.exists(test_file):
            os.unlink(test_file)


def test_llm_client():
    """测试LLM客户端"""
    print("测试LLM客户端...")
    
    config = {
        'api': {'volcengine': {'access_key_id': 'test', 'secret_access_key': 'test'}},
        'models': {'llm_endpoint': 'test'},
        'generation': {'max_images': 5}
    }
    
    client = LLMClient(config)
    
    try:
        # 测试脚本验证
        valid_script = {
            "title": "测试视频",
            "shots": [
                {"description": "第一个镜头", "duration": 5},
                {"description": "第二个镜头", "duration": 3}
            ],
            "narration": "这是旁白内容"
        }
        
        result = client._validate_script_format(valid_script)
        assert result is True
        
        # 测试降级脚本生成
        text_data = {
            'title': '测试小说',
            'content': '这是一个测试小说的内容',
            'word_count': 50,
            'chapters_found': 1
        }
        
        fallback_script = client._create_fallback_script(text_data)
        assert isinstance(fallback_script, dict)
        assert 'shots' in fallback_script
        assert len(fallback_script['shots']) > 0
        
        print("  - 脚本验证功能正常")
        print("  - 降级脚本生成正常")
        print("  - LLM客户端测试通过")
        return True
        
    except Exception as e:
        print(f"  - LLM客户端测试失败: {e}")
        return False


def test_database():
    """测试数据库管理器"""
    print("测试数据库管理器...")
    
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        test_db_path = f.name
    
    try:
        db = DatabaseManager(test_db_path)
        
        # 测试任务操作
        task_id = "test_task_001"
        db.create_task(task_id, "测试任务", "test_input.txt")
        
        task = db.get_task(task_id)
        assert task is not None
        assert task['task_id'] == task_id
        assert task['status'] == 'pending'
        
        # 更新任务状态
        db.update_task_status(task_id, 'completed')
        task = db.get_task(task_id)
        assert task['status'] == 'completed'
        
        print("  - 任务创建和更新正常")
        print("  - 数据库管理器测试通过")
        return True
        
    except Exception as e:
        print(f"  - 数据库管理器测试失败: {e}")
        return False
    finally:
        if os.path.exists(test_db_path):
            os.unlink(test_db_path)


def test_performance_tools():
    """测试性能工具"""
    print("测试性能工具...")
    
    try:
        # 测试内存管理
        memory_usage = memory_manager.get_memory_usage()
        assert 'rss_mb' in memory_usage
        assert memory_usage['rss_mb'] > 0
        
        # 测试性能监控
        from utils.performance import timing_decorator
        
        @timing_decorator(performance_monitor)
        def test_function():
            time.sleep(0.01)
            return "测试完成"
        
        # 运行测试函数
        for _ in range(3):
            test_function()
        
        # 获取性能汇总
        summary = performance_monitor.get_performance_summary()
        assert 'test_function' in summary
        
        print(f"  - 内存使用: {memory_usage['rss_mb']:.1f}MB")
        print("  - 性能监控功能正常")
        print("  - 性能工具测试通过")
        return True
        
    except ImportError:
        print("  - psutil未安装，跳过内存测试")
        return True
    except Exception as e:
        print(f"  - 性能工具测试失败: {e}")
        return False


def main():
    """主测试函数"""
    print("=" * 50)
    print("Day 8 简化测试套件")
    print("=" * 50)
    
    start_time = time.time()
    
    # 运行测试
    tests = [
        ("文本解析器", test_text_parser),
        ("LLM客户端", test_llm_client),
        ("数据库管理器", test_database),
        ("性能工具", test_performance_tools),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        try:
            if test_func():
                passed += 1
                print(f"[PASS] {test_name}")
            else:
                print(f"[FAIL] {test_name}")
        except Exception as e:
            print(f"[ERROR] {test_name}: {e}")
    
    # 汇总结果
    total_time = time.time() - start_time
    success_rate = passed / total * 100
    
    print("\n" + "=" * 50)
    print("测试汇总")
    print("=" * 50)
    print(f"总测试: {total}")
    print(f"通过: {passed}")
    print(f"失败: {total - passed}")
    print(f"成功率: {success_rate:.1f}%")
    print(f"总耗时: {total_time:.2f}秒")
    
    # 显示性能报告
    print(f"\n性能报告:")
    memory_usage = memory_manager.get_memory_usage()
    print(f"内存使用: {memory_usage['rss_mb']:.1f}MB")
    
    # 清理资源
    print(f"\n清理测试资源...")
    resource_cleaner.cleanup_temp_files()
    print("清理完成")
    
    if passed == total:
        print("\n所有测试通过！Day 8 测试完成")
        return True
    else:
        print(f"\n{total - passed} 个测试失败，请检查")
        return False


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n用户中断测试")
        sys.exit(1)
    except Exception as e:
        print(f"\n测试异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)