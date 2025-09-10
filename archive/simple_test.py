#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
简化版Day 2测试脚本
"""

import sys
import time
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from utils.logger import setup_logger
from utils.database import DatabaseManager
from utils.file_utils import FileUtils
from processors.parser import TextParser
from processors.llm_client import LLMClient


def create_test_novel():
    """创建测试小说文件"""
    test_content = """第一章 觉醒

在这个充满神秘力量的世界里，年轻的李明一直过着平凡的生活。他是一个普通的高中生，每天在学校和家之间往返。

但是，就在他十八岁生日的那一天，一切都发生了改变。

那是一个月圆之夜，李明独自走在回家的路上。突然，天空中划过一道奇异的光芒，紧接着一颗闪烁着蓝色光芒的流星坠落在他面前。

当他小心翼翼地接近流星时，一股神秘的力量涌入了他的身体。刹那间，他感到体内涌现出前所未有的能量。

第二章 发现

李明发现自己拥有了超乎寻常的能力。他能够控制身边的物体，甚至可以预知即将发生的事情。

这种力量既让他兴奋，也让他恐惧。他知道，自己的人生从此不再平凡。

在接下来的几天里，他开始练习控制这些新获得的能力。他发现，随着练习的深入，他的力量变得越来越强大。

但是，他也意识到，这种力量的背后隐藏着巨大的责任。"""
    
    test_file = "./test_novel.txt"
    FileUtils.write_text_file(test_file, test_content)
    return test_file


def test_text_parser():
    """测试文本解析模块"""
    print("="*50)
    print("测试文本解析模块")
    print("="*50)
    
    config = {
        'generation': {
            'final_duration_min': 120,
            'final_duration_max': 240
        }
    }
    
    test_file = create_test_novel()
    
    try:
        parser = TextParser(config)
        
        print("开始解析文本...")
        start_time = time.time()
        result = parser.parse(test_file)
        end_time = time.time()
        
        print("解析完成，耗时: {:.2f}秒".format(end_time - start_time))
        print("标题: {}".format(result['title']))
        print("字数: {}".format(result['word_count']))
        print("预计时长: {:.1f}秒".format(result['estimated_duration']))
        print("章节数: {}".format(result['chapters_found']))
        print("内容预览: {}...".format(result['content'][:200]))
        
        is_valid, error_msg = parser.validate_text(result['content'])
        print("文本验证: {}".format("通过" if is_valid else "失败 - " + error_msg))
        
        return True
        
    except Exception as e:
        print("文本解析测试失败: {}".format(e))
        return False
    finally:
        Path(test_file).unlink(missing_ok=True)


def test_database():
    """测试数据库功能"""
    print("="*50)
    print("测试数据库功能")
    print("="*50)
    
    db_path = "./test_database.db"
    
    try:
        db = DatabaseManager(db_path)
        print("数据库初始化完成")
        
        task_id = "test_task_{}".format(int(time.time()))
        success = db.create_task(task_id, "测试任务", "./test.txt", {"test": True})
        print("创建任务: {}".format(success))
        
        success = db.update_task_status(task_id, "processing")
        print("更新状态: {}".format(success))
        
        task = db.get_task(task_id)
        print("获取任务: {}".format(task['title'] if task else 'None'))
        
        success = db.save_text_parsing(
            task_id=task_id,
            original_content="原始内容",
            parsed_content="解析后内容",
            word_count=100,
            chapters_found=3,
            processing_time=1.5
        )
        print("保存解析结果: {}".format(success))
        
        db.track_daily_cost('llm', 0.05, 1)
        cost_summary = db.get_daily_cost_summary()
        print("成本跟踪: 总成本 {:.4f}元".format(cost_summary['total_cost']))
        
        stats = db.get_task_statistics()
        print("任务统计: 今日任务 {} 个".format(stats['today_tasks']))
        
        db.update_task_status(task_id, "completed")
        print("任务已完成")
        
        return True
        
    except Exception as e:
        print("数据库测试失败: {}".format(e))
        return False
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_llm_client():
    """测试LLM客户端(模拟模式)"""
    print("="*50)
    print("测试LLM客户端 (模拟模式)")
    print("="*50)
    
    config = {
        'api': {
            'volcengine': {
                'access_key_id': 'mock_key',
                'secret_access_key': 'mock_secret',
                'region': 'cn-north-1'
            }
        },
        'models': {
            'llm_endpoint': 'mock_endpoint'
        },
        'generation': {
            'max_images': 15,
            'video_segments': 3,
            'video_duration': 5
        },
        'prompts': {
            'storyboard_template': './prompts/storyboard.txt'
        },
        'api_settings': {
            'max_retries': 3,
            'request_timeout': 30,
            'rate_limit_per_minute': 60
        }
    }
    
    text_data = {
        'title': '第一章 觉醒',
        'content': '年轻的李明获得了神秘的力量，从此开始了他的英雄之路。',
        'word_count': 500,
        'estimated_duration': 120
    }
    
    try:
        client = LLMClient(config)
        
        print("测试提示词构建...")
        prompt = client._build_prompt(text_data)
        print("提示词长度: {} 字符".format(len(prompt)))
        
        print("测试脚本验证...")
        mock_script = {
            'title': '测试脚本',
            'summary': '这是一个测试脚本',
            'style': '现代 都市 青春 励志 温馨',
            'shots': [
                {'type': 'video', 'description': '主角出现', 'duration': 5},
                {'type': 'image', 'description': '环境展示', 'duration': 4}
            ],
            'narration': '这是一个精彩的故事。'
        }
        
        validated_script = client._validate_script(mock_script)
        print("脚本验证通过: {} 个镜头".format(len(validated_script['shots'])))
        
        return True
        
    except Exception as e:
        print("LLM客户端测试失败: {}".format(e))
        return False


def main():
    """主测试函数"""
    print("Day 2 功能测试开始")
    print("="*80)
    
    # 设置日志
    logger = setup_logger("test_day2", log_level="INFO")
    
    # 运行各项测试
    results = {}
    
    results['text_parser'] = test_text_parser()
    results['database'] = test_database() 
    results['llm_client'] = test_llm_client()
    
    # 输出测试总结
    print("="*80)
    print("测试结果总结")
    print("="*80)
    
    for test_name, passed in results.items():
        status = "通过" if passed else "失败"
        print("{}: {}".format(test_name, status))
    
    total_tests = len(results)
    passed_tests = sum(results.values())
    
    print("")
    print("总计: {}/{} 个测试通过".format(passed_tests, total_tests))
    
    if passed_tests == total_tests:
        print("Day 2 所有功能测试通过！")
        return True
    else:
        print("部分测试失败，请检查相关模块")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)