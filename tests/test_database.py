#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
数据库管理器单元测试
"""

import os
import sys
import tempfile
import time
from pathlib import Path

# 添加项目路径
sys.path.append(str(Path(__file__).parent.parent))

from utils.database import DatabaseManager


class TestDatabaseManager:
    """数据库管理器测试类"""
    
    def test_database_initialization(self):
        """测试数据库初始化"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            test_db_path = f.name
        
        try:
            db = DatabaseManager(test_db_path)
            
            # 检查数据库文件是否创建
            assert os.path.exists(test_db_path)
            
            # 检查表是否创建
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
            
            expected_tables = ['tasks', 'text_parsing', 'media_generation', 'api_costs']
            for table in expected_tables:
                assert table in tables, f"表 {table} 未创建"
            
            print("✓ 数据库初始化正常")
            
        finally:
            if os.path.exists(test_db_path):
                os.unlink(test_db_path)
    
    def test_task_operations(self):
        """测试任务操作"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            test_db_path = f.name
        
        try:
            db = DatabaseManager(test_db_path)
            
            # 创建任务
            task_id = "test_task_001"
            db.create_task(task_id, "测试任务", "test_input.txt")
            
            # 获取任务
            task = db.get_task(task_id)
            assert task is not None
            assert task['task_id'] == task_id
            assert task['title'] == "测试任务"
            assert task['status'] == 'pending'
            
            # 更新任务状态
            db.update_task_status(task_id, 'processing')
            task = db.get_task(task_id)
            assert task['status'] == 'processing'
            
            # 完成任务
            db.update_task_status(task_id, 'completed')
            task = db.get_task(task_id)
            assert task['status'] == 'completed'
            
            print("✓ 任务操作功能正常")
            
        finally:
            if os.path.exists(test_db_path):
                os.unlink(test_db_path)
    
    def test_text_parsing_storage(self):
        """测试文本解析存储"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            test_db_path = f.name
        
        try:
            db = DatabaseManager(test_db_path)
            
            # 保存文本解析结果
            task_id = "test_task_002"
            db.create_task(task_id, "文本解析测试", "test.txt")
            
            db.save_text_parsing(
                task_id=task_id,
                original_content="原始内容",
                parsed_content="解析后内容",
                word_count=100,
                chapters_found=3,
                processing_time=1.5
            )
            
            # 验证存储
            cursor = db.conn.cursor()
            cursor.execute("SELECT * FROM text_parsing WHERE task_id = ?", (task_id,))
            result = cursor.fetchone()
            
            assert result is not None
            assert result[2] == 100  # word_count
            assert result[3] == 3    # chapters_found
            
            print("✓ 文本解析存储功能正常")
            
        finally:
            if os.path.exists(test_db_path):
                os.unlink(test_db_path)
    
    def test_media_generation_storage(self):
        """测试媒体生成存储"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            test_db_path = f.name
        
        try:
            db = DatabaseManager(test_db_path)
            
            # 保存媒体生成结果
            task_id = "test_task_003"
            db.create_task(task_id, "媒体生成测试", "test.txt")
            
            db.save_media_generation(
                task_id=task_id,
                media_type="image",
                description="测试图片",
                file_path="/path/to/image.jpg",
                file_size=1024000,
                duration=0.0,
                cost=0.025,
                processing_time=5.0
            )
            
            # 验证存储
            cursor = db.conn.cursor()
            cursor.execute("SELECT * FROM media_generation WHERE task_id = ?", (task_id,))
            result = cursor.fetchone()
            
            assert result is not None
            assert result[2] == "image"  # media_type
            assert result[5] == 1024000  # file_size
            
            print("✓ 媒体生成存储功能正常")
            
        finally:
            if os.path.exists(test_db_path):
                os.unlink(test_db_path)
    
    def test_cost_tracking(self):
        """测试成本跟踪"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            test_db_path = f.name
        
        try:
            db = DatabaseManager(test_db_path)
            
            # 记录API成本
            db.save_api_cost("llm", "豆包API调用", 0.012, 1000, "tokens")
            db.save_api_cost("image", "图片生成", 0.025, 1, "images")
            
            # 获取成本汇总
            today = time.strftime('%Y-%m-%d')
            cost_summary = db.get_daily_cost_summary(today)
            
            assert cost_summary['total_cost'] > 0
            assert cost_summary['total_requests'] == 2
            assert 'llm' in cost_summary['services']
            assert 'image' in cost_summary['services']
            
            print("✓ 成本跟踪功能正常")
            
        finally:
            if os.path.exists(test_db_path):
                os.unlink(test_db_path)
    
    def test_task_statistics(self):
        """测试任务统计"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            test_db_path = f.name
        
        try:
            db = DatabaseManager(test_db_path)
            
            # 创建多个任务
            for i in range(5):
                task_id = f"test_task_{i:03d}"
                db.create_task(task_id, f"测试任务 {i}", f"test_{i}.txt")
                if i < 3:
                    db.update_task_status(task_id, 'completed')
                elif i == 3:
                    db.update_task_status(task_id, 'failed', "测试失败")
            
            # 获取统计信息
            stats = db.get_task_statistics()
            
            assert stats['total_tasks'] == 5
            assert stats['completed_tasks'] == 3
            assert stats['failed_tasks'] == 1
            assert stats['pending_tasks'] == 1
            
            print("✓ 任务统计功能正常")
            
        finally:
            if os.path.exists(test_db_path):
                os.unlink(test_db_path)
    
    def test_list_tasks(self):
        """测试任务列表功能"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            test_db_path = f.name
        
        try:
            db = DatabaseManager(test_db_path)
            
            # 创建任务
            for i in range(3):
                task_id = f"list_task_{i:03d}"
                db.create_task(task_id, f"列表测试任务 {i}", f"test_{i}.txt")
            
            # 获取任务列表
            tasks = db.list_tasks(limit=10)
            
            assert len(tasks) == 3
            assert all('task_id' in task for task in tasks)
            assert all('title' in task for task in tasks)
            
            print("✓ 任务列表功能正常")
            
        finally:
            if os.path.exists(test_db_path):
                os.unlink(test_db_path)


def run_database_tests():
    """运行数据库测试"""
    print("运行数据库管理器测试...")
    
    test_db = TestDatabaseManager()
    
    try:
        test_db.test_database_initialization()
        test_db.test_task_operations()
        test_db.test_text_parsing_storage()
        test_db.test_media_generation_storage()
        test_db.test_cost_tracking()
        test_db.test_task_statistics()
        test_db.test_list_tasks()
        
        print("数据库管理器测试全部通过! ✅")
        return True
        
    except Exception as e:
        print(f"数据库测试失败: {e}")
        return False


if __name__ == "__main__":
    run_database_tests()