#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
数据库管理模块
使用SQLite作为本地数据库，管理任务记录、生成历史等数据
"""

import sqlite3
import json
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from .logger import LoggerMixin
from .file_utils import FileUtils


class DatabaseManager(LoggerMixin):
    """数据库管理器"""
    
    def __init__(self, db_path: str = "./data/database.db"):
        """
        初始化数据库管理器
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        
        # 确保数据库目录存在
        FileUtils.ensure_dir(Path(db_path).parent)
        
        # 初始化数据库
        self._init_database()
    
    def get_connection(self):
        """获取数据库连接（主要用于测试）"""
        return sqlite3.connect(self.db_path)
    
    def _init_database(self):
        """初始化数据库表结构"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 任务记录表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS tasks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        task_id TEXT UNIQUE NOT NULL,
                        title TEXT NOT NULL,
                        source_file TEXT NOT NULL,
                        status TEXT DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        started_at TIMESTAMP NULL,
                        completed_at TIMESTAMP NULL,
                        error_message TEXT NULL,
                        retry_count INTEGER DEFAULT 0,
                        metadata TEXT NULL
                    )
                ''')
                
                # 文本解析记录表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS text_parsing (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        task_id TEXT NOT NULL,
                        original_content TEXT NOT NULL,
                        parsed_content TEXT NOT NULL,
                        word_count INTEGER NOT NULL,
                        chapters_found INTEGER DEFAULT 0,
                        processing_time REAL NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (task_id) REFERENCES tasks (task_id)
                    )
                ''')
                
                # LLM脚本生成记录表  
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS llm_scripts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        task_id TEXT NOT NULL,
                        prompt TEXT NOT NULL,
                        response TEXT NOT NULL,
                        script_data TEXT NOT NULL,
                        tokens_used INTEGER DEFAULT 0,
                        cost REAL DEFAULT 0.0,
                        processing_time REAL NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (task_id) REFERENCES tasks (task_id)
                    )
                ''')
                
                # 媒体生成记录表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS media_generation (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        task_id TEXT NOT NULL,
                        media_type TEXT NOT NULL, -- 'image', 'video', 'audio'
                        description TEXT NOT NULL,
                        file_path TEXT NOT NULL,
                        file_size INTEGER DEFAULT 0,
                        duration REAL DEFAULT 0.0,
                        cost REAL DEFAULT 0.0,
                        processing_time REAL NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (task_id) REFERENCES tasks (task_id)
                    )
                ''')
                
                # 最终视频记录表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS final_videos (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        task_id TEXT NOT NULL,
                        video_path TEXT NOT NULL,
                        duration REAL NOT NULL,
                        file_size INTEGER NOT NULL,
                        resolution TEXT NOT NULL,
                        total_cost REAL DEFAULT 0.0,
                        total_processing_time REAL NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (task_id) REFERENCES tasks (task_id)
                    )
                ''')
                
                # 成本统计表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS cost_tracking (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date TEXT NOT NULL, -- YYYY-MM-DD格式
                        service_type TEXT NOT NULL, -- 'llm', 'text2image', 'image2video', 'tts'
                        request_count INTEGER DEFAULT 0,
                        total_cost REAL DEFAULT 0.0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(date, service_type)
                    )
                ''')
                
                # 系统配置表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS system_config (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # 创建索引
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_media_task_id ON media_generation(task_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_cost_date ON cost_tracking(date)')
                
                conn.commit()
                self.logger.info("数据库初始化完成")
                
        except Exception as e:
            self.logger.error(f"数据库初始化失败: {e}")
            raise
    
    def create_task(
        self, 
        task_id: str, 
        title: str, 
        source_file: str, 
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        创建新任务
        
        Args:
            task_id: 任务ID
            title: 任务标题
            source_file: 源文件路径
            metadata: 元数据
            
        Returns:
            是否成功
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO tasks (task_id, title, source_file, metadata)
                    VALUES (?, ?, ?, ?)
                ''', (
                    task_id, 
                    title, 
                    source_file,
                    json.dumps(metadata) if metadata else None
                ))
                
                conn.commit()
                self.logger.info(f"任务创建成功: {task_id}")
                return True
                
        except sqlite3.IntegrityError:
            self.logger.warning(f"任务已存在: {task_id}")
            return False
        except Exception as e:
            self.logger.error(f"创建任务失败: {e}")
            return False
    
    def update_task_status(
        self, 
        task_id: str, 
        status: str, 
        error_message: Optional[str] = None
    ) -> bool:
        """
        更新任务状态
        
        Args:
            task_id: 任务ID
            status: 新状态 (pending, processing, completed, failed)
            error_message: 错误信息
            
        Returns:
            是否成功
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 准备更新字段
                update_fields = ['status = ?', 'updated_at = CURRENT_TIMESTAMP']
                params = [status]
                
                if status == 'processing':
                    update_fields.append('started_at = CURRENT_TIMESTAMP')
                elif status in ['completed', 'failed']:
                    update_fields.append('completed_at = CURRENT_TIMESTAMP')
                
                if error_message:
                    update_fields.append('error_message = ?')
                    params.append(error_message)
                
                params.append(task_id)
                
                sql = f"UPDATE tasks SET {', '.join(update_fields)} WHERE task_id = ?"
                cursor.execute(sql, params)
                
                if cursor.rowcount == 0:
                    self.logger.warning(f"任务不存在: {task_id}")
                    return False
                
                conn.commit()
                self.logger.debug(f"任务状态更新: {task_id} -> {status}")
                return True
                
        except Exception as e:
            self.logger.error(f"更新任务状态失败: {e}")
            return False
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务信息
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务信息字典
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('SELECT * FROM tasks WHERE task_id = ?', (task_id,))
                row = cursor.fetchone()
                
                if row:
                    task = dict(row)
                    if task['metadata']:
                        task['metadata'] = json.loads(task['metadata'])
                    return task
                
                return None
                
        except Exception as e:
            self.logger.error(f"获取任务失败: {e}")
            return None
    
    def list_tasks(
        self, 
        status: Optional[str] = None, 
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        列出任务
        
        Args:
            status: 筛选状态
            limit: 限制数量  
            offset: 偏移量
            
        Returns:
            任务列表
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                if status:
                    cursor.execute('''
                        SELECT * FROM tasks 
                        WHERE status = ? 
                        ORDER BY created_at DESC 
                        LIMIT ? OFFSET ?
                    ''', (status, limit, offset))
                else:
                    cursor.execute('''
                        SELECT * FROM tasks 
                        ORDER BY created_at DESC 
                        LIMIT ? OFFSET ?
                    ''', (limit, offset))
                
                tasks = []
                for row in cursor.fetchall():
                    task = dict(row)
                    if task['metadata']:
                        task['metadata'] = json.loads(task['metadata'])
                    tasks.append(task)
                
                return tasks
                
        except Exception as e:
            self.logger.error(f"列出任务失败: {e}")
            return []
    
    def save_text_parsing(
        self,
        task_id: str,
        original_content: str,
        parsed_content: str,
        word_count: int,
        chapters_found: int,
        processing_time: float
    ) -> bool:
        """保存文本解析结果"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO text_parsing 
                    (task_id, original_content, parsed_content, word_count, chapters_found, processing_time)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (task_id, original_content, parsed_content, word_count, chapters_found, processing_time))
                
                conn.commit()
                return True
                
        except Exception as e:
            self.logger.error(f"保存文本解析结果失败: {e}")
            return False
    
    def save_llm_script(
        self,
        task_id: str,
        prompt: str,
        response: str,
        script_data: Dict[str, Any],
        tokens_used: int,
        cost: float,
        processing_time: float
    ) -> bool:
        """保存LLM脚本生成结果"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO llm_scripts 
                    (task_id, prompt, response, script_data, tokens_used, cost, processing_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    task_id, 
                    prompt, 
                    response, 
                    json.dumps(script_data),
                    tokens_used,
                    cost,
                    processing_time
                ))
                
                conn.commit()
                return True
                
        except Exception as e:
            self.logger.error(f"保存LLM脚本结果失败: {e}")
            return False
    
    def save_media_generation(
        self,
        task_id: str,
        media_type: str,
        description: str,
        file_path: str,
        file_size: int,
        duration: float,
        cost: float,
        processing_time: float
    ) -> bool:
        """保存媒体生成记录"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO media_generation 
                    (task_id, media_type, description, file_path, file_size, duration, cost, processing_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (task_id, media_type, description, file_path, file_size, duration, cost, processing_time))
                
                conn.commit()
                return True
                
        except Exception as e:
            self.logger.error(f"保存媒体生成记录失败: {e}")
            return False
    
    def track_daily_cost(self, service_type: str, cost: float, request_count: int = 1):
        """记录日成本"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 尝试更新现有记录
                cursor.execute('''
                    UPDATE cost_tracking 
                    SET request_count = request_count + ?, 
                        total_cost = total_cost + ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE date = ? AND service_type = ?
                ''', (request_count, cost, today, service_type))
                
                # 如果没有现有记录，插入新记录
                if cursor.rowcount == 0:
                    cursor.execute('''
                        INSERT INTO cost_tracking (date, service_type, request_count, total_cost)
                        VALUES (?, ?, ?, ?)
                    ''', (today, service_type, request_count, cost))
                
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"记录日成本失败: {e}")
    
    def get_daily_cost_summary(self, date: Optional[str] = None) -> Dict[str, Any]:
        """获取日成本汇总"""
        try:
            if not date:
                date = datetime.now().strftime('%Y-%m-%d')
            
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT service_type, request_count, total_cost
                    FROM cost_tracking 
                    WHERE date = ?
                ''', (date,))
                
                rows = cursor.fetchall()
                summary = {
                    'date': date,
                    'services': {},
                    'total_cost': 0.0,
                    'total_requests': 0
                }
                
                for row in rows:
                    service = row['service_type']
                    summary['services'][service] = {
                        'requests': row['request_count'],
                        'cost': row['total_cost']
                    }
                    summary['total_cost'] += row['total_cost']
                    summary['total_requests'] += row['request_count']
                
                return summary
                
        except Exception as e:
            self.logger.error(f"获取日成本汇总失败: {e}")
            return {'date': date, 'services': {}, 'total_cost': 0.0, 'total_requests': 0}
    
    def get_task_statistics(self) -> Dict[str, Any]:
        """获取任务统计"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 各状态任务数量
                cursor.execute('''
                    SELECT status, COUNT(*) as count 
                    FROM tasks 
                    GROUP BY status
                ''')
                status_counts = dict(cursor.fetchall())
                
                # 今日任务数量
                cursor.execute('''
                    SELECT COUNT(*) 
                    FROM tasks 
                    WHERE date(created_at) = date('now')
                ''')
                today_tasks = cursor.fetchone()[0]
                
                # 总处理时长
                cursor.execute('''
                    SELECT AVG(
                        CASE 
                            WHEN completed_at IS NOT NULL AND started_at IS NOT NULL 
                            THEN (julianday(completed_at) - julianday(started_at)) * 86400
                            ELSE NULL 
                        END
                    ) as avg_processing_time
                    FROM tasks
                    WHERE status = 'completed'
                ''')
                result = cursor.fetchone()
                avg_processing_time = result[0] if result[0] else 0
                
                return {
                    'status_counts': status_counts,
                    'today_tasks': today_tasks,
                    'avg_processing_time': avg_processing_time
                }
                
        except Exception as e:
            self.logger.error(f"获取任务统计失败: {e}")
            return {'status_counts': {}, 'today_tasks': 0, 'avg_processing_time': 0}
    
    def cleanup_old_records(self, days: int = 30):
        """清理旧记录"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 清理N天前的已完成任务
                cursor.execute('''
                    DELETE FROM tasks 
                    WHERE status IN ('completed', 'failed') 
                    AND created_at < datetime('now', '-{} days')
                '''.format(days))
                
                deleted_tasks = cursor.rowcount
                
                # 清理孤立的相关记录
                cursor.execute('''
                    DELETE FROM text_parsing 
                    WHERE task_id NOT IN (SELECT task_id FROM tasks)
                ''')
                
                cursor.execute('''
                    DELETE FROM llm_scripts 
                    WHERE task_id NOT IN (SELECT task_id FROM tasks)
                ''')
                
                cursor.execute('''
                    DELETE FROM media_generation 
                    WHERE task_id NOT IN (SELECT task_id FROM tasks)
                ''')
                
                cursor.execute('''
                    DELETE FROM final_videos 
                    WHERE task_id NOT IN (SELECT task_id FROM tasks)
                ''')
                
                conn.commit()
                self.logger.info(f"清理了 {deleted_tasks} 个旧任务记录")
                
        except Exception as e:
            self.logger.error(f"清理旧记录失败: {e}")


def test_database():
    """测试数据库功能"""
    db = DatabaseManager("./test_db.sqlite")
    
    # 测试创建任务
    task_id = f"test_task_{int(time.time())}"
    success = db.create_task(task_id, "测试任务", "./test.txt", {"test": True})
    print(f"创建任务: {success}")
    
    # 测试更新状态
    success = db.update_task_status(task_id, "processing")
    print(f"更新状态: {success}")
    
    # 测试获取任务
    task = db.get_task(task_id)
    print(f"获取任务: {task}")
    
    # 测试列出任务
    tasks = db.list_tasks()
    print(f"任务列表: {len(tasks)} 个任务")
    
    # 测试统计
    stats = db.get_task_statistics()
    print(f"任务统计: {stats}")
    
    # 清理测试数据
    Path("./test_db.sqlite").unlink(missing_ok=True)
    print("测试完成")


if __name__ == "__main__":
    test_database()