#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Day 2 功能测试脚本
测试文本解析模块、LLM客户端、数据库等核心功能
"""

import sys
import json
import time
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from utils.logger import setup_logger
from utils.database import DatabaseManager
from utils.file_utils import FileUtils, load_config
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

但是，他也意识到，这种力量的背后隐藏着巨大的责任。

第三章 选择

一天，李明遇到了一个神秘的老者。老者告诉他，他是传说中的"天选之子"，注定要拯救这个世界。

"力量伴随着责任。"老者说道，"你必须做出选择：是用这份力量来保护人们，还是让它沉睡在你心中。"

李明陷入了沉思。他知道，无论做出什么选择，他的生活都将彻底改变。

最终，他决定接受这个使命。从那一刻起，他开始了自己的英雄之路。"""
    
    test_file = "./test_novel.txt"
    FileUtils.write_text_file(test_file, test_content)
    return test_file


def test_text_parser():
    """测试文本解析模块"""
    print("=" * 60)
    print("测试文本解析模块")
    print("=" * 60)
    
    # 创建配置
    config = {
        'generation': {
            'final_duration_min': 120,
            'final_duration_max': 240
        }
    }
    
    # 创建测试文件
    test_file = create_test_novel()
    
    try:
        # 初始化解析器
        parser = TextParser(config)
        
        # 解析文本
        print("开始解析文本...")
        start_time = time.time()
        result = parser.parse(test_file)
        end_time = time.time()
        
        # 输出结果
        print(f"✅ 解析完成 (耗时: {end_time - start_time:.2f}秒)")
        print(f"📖 标题: {result['title']}")
        print(f"📝 字数: {result['word_count']}")
        print(f"🕒 预计时长: {result['estimated_duration']:.1f}秒")
        print(f"📚 章节数: {result['chapters_found']}")
        print(f"📄 内容预览: {result['content'][:200]}...")
        
        # 验证文本质量
        is_valid, error_msg = parser.validate_text(result['content'])
        print(f"✅ 文本验证: {'通过' if is_valid else f'失败 - {error_msg}'}")
        
        return result
        
    except Exception as e:
        print(f"❌ 文本解析测试失败: {e}")
        return None
    finally:
        # 清理测试文件
        Path(test_file).unlink(missing_ok=True)


def test_llm_client():
    """测试LLM客户端(模拟模式)"""
    print("=" * 60)
    print("测试LLM客户端 (模拟模式)")
    print("=" * 60)
    
    # 模拟配置
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
    
    # 模拟文本数据
    text_data = {
        'title': '第一章 觉醒',
        'content': '年轻的李明获得了神秘的力量，从此开始了他的英雄之路。这是一个关于成长、责任和勇气的故事。',
        'word_count': 500,
        'estimated_duration': 120
    }
    
    try:
        # 初始化LLM客户端
        client = LLMClient(config)
        
        print("🤖 测试提示词构建...")
        # 测试提示词构建
        prompt = client._build_prompt(text_data)
        print(f"✅ 提示词长度: {len(prompt)} 字符")
        
        print("📝 测试脚本验证...")
        # 测试脚本验证
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
        print(f"✅ 脚本验证通过: {len(validated_script['shots'])} 个镜头")
        
        # 输出验证后的脚本
        print("📄 脚本内容:")
        print(json.dumps(validated_script, indent=2, ensure_ascii=False))
        
        return validated_script
        
    except Exception as e:
        print(f"❌ LLM客户端测试失败: {e}")
        return None


def test_database():
    """测试数据库功能"""
    print("=" * 60)
    print("测试数据库功能")
    print("=" * 60)
    
    db_path = "./test_database.db"
    
    try:
        # 初始化数据库
        db = DatabaseManager(db_path)
        print("✅ 数据库初始化完成")
        
        # 测试创建任务
        task_id = f"test_task_{int(time.time())}"
        success = db.create_task(task_id, "测试任务", "./test.txt", {"test": True})
        print(f"✅ 创建任务: {success}")
        
        # 测试更新状态
        success = db.update_task_status(task_id, "processing")
        print(f"✅ 更新状态: {success}")
        
        # 测试获取任务
        task = db.get_task(task_id)
        print(f"✅ 获取任务: {task['title'] if task else 'None'}")
        
        # 测试保存文本解析结果
        success = db.save_text_parsing(
            task_id=task_id,
            original_content="原始内容",
            parsed_content="解析后内容",
            word_count=100,
            chapters_found=3,
            processing_time=1.5
        )
        print(f"✅ 保存解析结果: {success}")
        
        # 测试成本跟踪
        db.track_daily_cost('llm', 0.05, 1)
        cost_summary = db.get_daily_cost_summary()
        print(f"✅ 成本跟踪: 总成本 ¥{cost_summary['total_cost']:.4f}")
        
        # 测试任务统计
        stats = db.get_task_statistics()
        print(f"✅ 任务统计: 今日任务 {stats['today_tasks']} 个")
        
        # 完成任务
        db.update_task_status(task_id, "completed")
        print("✅ 任务已完成")
        
        return True
        
    except Exception as e:
        print(f"❌ 数据库测试失败: {e}")
        return False
    finally:
        # 清理测试数据库
        Path(db_path).unlink(missing_ok=True)


def test_integration():
    """集成测试"""
    print("=" * 60)
    print("集成测试")
    print("=" * 60)
    
    try:
        # 创建临时数据库
        db = DatabaseManager("./test_integration.db")
        task_id = f"integration_test_{int(time.time())}"
        
        # 1. 创建任务
        print("1️⃣ 创建任务...")
        db.create_task(task_id, "集成测试任务", "./test.txt")
        db.update_task_status(task_id, "processing")
        
        # 2. 文本解析
        print("2️⃣ 文本解析...")
        config = {
            'generation': {
                'final_duration_min': 120,
                'final_duration_max': 240
            }
        }
        
        test_file = create_test_novel()
        parser = TextParser(config)
        text_result = parser.parse(test_file)
        
        # 保存解析结果
        db.save_text_parsing(
            task_id=task_id,
            original_content="原始小说内容...",
            parsed_content=text_result['content'],
            word_count=text_result['word_count'],
            chapters_found=text_result['chapters_found'],
            processing_time=1.0
        )
        
        # 3. LLM脚本生成(模拟)
        print("3️⃣ LLM脚本生成...")
        mock_script = {
            'title': text_result['title'],
            'summary': '一个关于觉醒与成长的故事',
            'style': '玄幻 修仙 热血 成长 国漫',
            'shots': [
                {'type': 'video', 'description': '少年在月夜下觉醒神秘力量', 'duration': 5},
                {'type': 'video', 'description': '流星划过夜空，蓝光闪现', 'duration': 5},
                {'type': 'video', 'description': '少年眼中闪烁着决心的光芒', 'duration': 5},
                {'type': 'image', 'description': '神秘老者出现在山巅', 'duration': 4},
                {'type': 'image', 'description': '少年踏上英雄之路', 'duration': 4}
            ],
            'narration': '那一夜，命运的齿轮开始转动。少年李明获得了改变世界的力量，也承担起了守护的责任。'
        }
        
        # 保存脚本结果
        db.save_llm_script(
            task_id=task_id,
            prompt="模拟提示词...",
            response="模拟响应...",
            script_data=mock_script,
            tokens_used=800,
            cost=0.02,
            processing_time=3.0
        )
        
        # 4. 完成任务
        print("4️⃣ 完成任务...")
        db.update_task_status(task_id, "completed")
        
        # 5. 查看结果
        print("5️⃣ 查看结果...")
        final_task = db.get_task(task_id)
        print(f"✅ 任务状态: {final_task['status']}")
        
        cost_summary = db.get_daily_cost_summary()
        print(f"✅ 今日成本: ¥{cost_summary['total_cost']:.4f}")
        
        stats = db.get_task_statistics()
        print(f"✅ 任务统计: {stats}")
        
        return True
        
    except Exception as e:
        print(f"❌ 集成测试失败: {e}")
        return False
    finally:
        # 清理测试文件
        Path("./test_integration.db").unlink(missing_ok=True)
        Path("./test_novel.txt").unlink(missing_ok=True)


def main():
    """主测试函数"""
    print("Day 2 功能测试开始")
    print("=" * 80)
    
    # 设置日志
    logger = setup_logger("test_day2", log_level="INFO")
    
    # 运行各项测试
    results = {}
    
    # 1. 文本解析测试
    results['text_parser'] = test_text_parser() is not None
    
    # 2. LLM客户端测试
    results['llm_client'] = test_llm_client() is not None
    
    # 3. 数据库测试
    results['database'] = test_database()
    
    # 4. 集成测试
    results['integration'] = test_integration()
    
    # 输出测试总结
    print("=" * 80)
    print("📊 测试结果总结")
    print("=" * 80)
    
    for test_name, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{test_name}: {status}")
    
    total_tests = len(results)
    passed_tests = sum(results.values())
    
    print(f"\n🎯 总计: {passed_tests}/{total_tests} 个测试通过")
    
    if passed_tests == total_tests:
        print("🎉 Day 2 所有功能测试通过！")
        return True
    else:
        print("⚠️ 部分测试失败，请检查相关模块")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)