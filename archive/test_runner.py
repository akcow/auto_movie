#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试运行器 - Day 8 测试套件
运行所有单元测试、集成测试和异常场景测试
"""

import asyncio
import sys
import time
from pathlib import Path

# 添加项目路径
sys.path.append(str(Path(__file__).parent))

# 导入所有测试模块
from tests.test_text_parser import run_parser_tests
from tests.test_llm_client import run_llm_tests
from tests.test_database import run_database_tests
from tests.test_integration import run_integration_tests
from tests.test_edge_cases import run_edge_case_tests

from utils.performance import performance_monitor, memory_manager, resource_cleaner


class TestRunner:
    """测试运行器"""
    
    def __init__(self):
        self.results = {}
        self.start_time = time.time()
    
    def run_test_suite(self, suite_name: str, test_func) -> bool:
        """
        运行测试套件
        
        Args:
            suite_name: 测试套件名称
            test_func: 测试函数
            
        Returns:
            是否通过
        """
        print(f"\n{'='*60}")
        print(f"运行测试套件: {suite_name}")
        print(f"{'='*60}")
        
        start_time = time.time()
        
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = asyncio.run(test_func())
            else:
                result = test_func()
            
            duration = time.time() - start_time
            
            if result:
                print(f"✅ {suite_name} 通过 ({duration:.2f}秒)")
                self.results[suite_name] = {'status': 'PASS', 'duration': duration}
                return True
            else:
                print(f"❌ {suite_name} 失败 ({duration:.2f}秒)")
                self.results[suite_name] = {'status': 'FAIL', 'duration': duration}
                return False
                
        except Exception as e:
            duration = time.time() - start_time
            print(f"💥 {suite_name} 异常: {e} ({duration:.2f}秒)")
            self.results[suite_name] = {'status': 'ERROR', 'duration': duration, 'error': str(e)}
            return False
    
    def print_summary(self):
        """打印测试汇总"""
        total_time = time.time() - self.start_time
        
        print(f"\n{'='*60}")
        print("测试汇总报告")
        print(f"{'='*60}")
        
        passed = sum(1 for r in self.results.values() if r['status'] == 'PASS')
        failed = sum(1 for r in self.results.values() if r['status'] == 'FAIL')
        errors = sum(1 for r in self.results.values() if r['status'] == 'ERROR')
        total = len(self.results)
        
        print(f"总测试套件: {total}")
        print(f"通过: {passed}")
        print(f"失败: {failed}")
        print(f"错误: {errors}")
        print(f"成功率: {passed/total*100:.1f}%")
        print(f"总耗时: {total_time:.2f}秒")
        
        print(f"\n详细结果:")
        for suite_name, result in self.results.items():
            status_icon = {
                'PASS': '[PASS]',
                'FAIL': '[FAIL]', 
                'ERROR': '[ERROR]'
            }.get(result['status'], '[UNKNOWN]')
            
            print(f"{status_icon} {suite_name}: {result['status']} ({result['duration']:.2f}s)")
            if 'error' in result:
                print(f"    错误: {result['error']}")
        
        # 显示性能信息
        print(f"\n性能信息:")
        memory_usage = memory_manager.get_memory_usage()
        print(f"内存使用: {memory_usage['rss_mb']:.1f}MB")
        print(f"内存占用率: {memory_usage['percent']:.1f}%")
        
        # 显示性能监控报告
        performance_monitor.print_performance_report()
        
        return passed == total
    
    def cleanup(self):
        """清理测试资源"""
        print(f"\n清理测试资源...")
        
        # 清理临时文件
        cleaned_files = resource_cleaner.cleanup_temp_files()
        cleaned_dirs = resource_cleaner.cleanup_temp_dirs()
        
        if cleaned_files > 0 or cleaned_dirs > 0:
            print(f"清理了 {cleaned_files} 个临时文件, {cleaned_dirs} 个临时目录")
        
        # 强制垃圾回收
        memory_manager.force_gc()
        
        print("清理完成")


async def main():
    """主测试函数"""
    print("开始 Day 8 测试套件")
    print(f"Python版本: {sys.version}")
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    runner = TestRunner()
    
    try:
        # 定义测试套件
        test_suites = [
            ("文本解析器单元测试", run_parser_tests),
            ("LLM客户端单元测试", run_llm_tests),
            ("数据库管理器单元测试", run_database_tests),
            ("端到端集成测试", run_integration_tests),
            ("异常场景测试", run_edge_case_tests),
        ]
        
        # 运行所有测试套件
        overall_success = True
        for suite_name, test_func in test_suites:
            success = runner.run_test_suite(suite_name, test_func)
            if not success:
                overall_success = False
        
        # 打印最终汇总
        final_success = runner.print_summary()
        
        # 返回结果
        if final_success:
            print(f"\n所有测试通过！Day 8 测试套件完成")
            return 0
        else:
            print(f"\n部分测试失败，请检查上述报告")
            return 1
            
    except KeyboardInterrupt:
        print(f"\n用户中断测试")
        return 1
    except Exception as e:
        print(f"\n测试运行器异常: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        # 清理资源
        runner.cleanup()


def run_quick_tests():
    """快速测试（只运行单元测试）"""
    print("运行快速测试...")
    
    runner = TestRunner()
    
    quick_suites = [
        ("文本解析器测试", run_parser_tests),
        ("LLM客户端测试", run_llm_tests),
        ("数据库管理器测试", run_database_tests),
    ]
    
    overall_success = True
    for suite_name, test_func in quick_suites:
        success = runner.run_test_suite(suite_name, test_func)
        if not success:
            overall_success = False
    
    runner.print_summary()
    runner.cleanup()
    
    return overall_success


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Day 8 测试套件')
    parser.add_argument('--quick', action='store_true', help='运行快速测试（仅单元测试）')
    parser.add_argument('--suite', type=str, help='运行特定测试套件')
    
    args = parser.parse_args()
    
    if args.quick:
        success = run_quick_tests()
        sys.exit(0 if success else 1)
    elif args.suite:
        # 运行特定套件
        suite_map = {
            'parser': run_parser_tests,
            'llm': run_llm_tests,
            'database': run_database_tests,
            'integration': run_integration_tests,
            'edge_cases': run_edge_case_tests
        }
        
        if args.suite in suite_map:
            try:
                success = suite_map[args.suite]()
                sys.exit(0 if success else 1)
            except Exception as e:
                print(f"测试套件运行失败: {e}")
                sys.exit(1)
        else:
            print(f"未知测试套件: {args.suite}")
            print(f"可用套件: {list(suite_map.keys())}")
            sys.exit(1)
    else:
        # 运行完整测试套件
        exit_code = asyncio.run(main())
        sys.exit(exit_code)