#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
火山引擎TOS对象存储客户端
用于图生视频API所需的图片上传功能
"""

import os
import asyncio
import time
from typing import Dict, Any, Optional
from pathlib import Path
import uuid

from .logger import LoggerMixin


class TOSClient(LoggerMixin):
    """TOS对象存储客户端"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化TOS客户端
        
        Args:
            config: 配置字典
        """
        self.config = config
        api_config = config.get('api', {}).get('volcengine', {})
        tos_config = api_config.get('tos', {})
        
        self.region = tos_config.get('region')
        self.bucket = tos_config.get('bucket') 
        self.access_key_id = tos_config.get('access_key_id')
        self.secret_access_key = tos_config.get('secret_access_key')
        self.endpoint = tos_config.get('endpoint')
        
        # 验证配置
        if not all([self.region, self.bucket, self.access_key_id, self.secret_access_key]):
            raise ValueError("TOS配置不完整，请检查config.yaml中的tos配置")
        
        self._client = None
        self.logger.info(f"TOS客户端初始化完成: bucket={self.bucket}, region={self.region}")
    
    def _get_client(self):
        """获取TOS客户端实例（延迟初始化）"""
        if self._client is None:
            try:
                import tos
                from tos import TosClientV2
                
                # 按照TOS SDK的实际参数格式创建客户端
                endpoint = f"tos-{self.region}.volces.com"
                self._client = TosClientV2(
                    ak=self.access_key_id,
                    sk=self.secret_access_key,
                    endpoint=endpoint,
                    region=self.region
                )
                
                self.logger.info(f"TOS客户端创建成功: bucket={self.bucket}, endpoint={endpoint}")
                
            except ImportError:
                self.logger.error("缺少tos依赖，请安装：pip install tos")
                raise
                
        return self._client
    
    async def upload_image(self, image_path: str, task_id: str = None) -> str:
        """
        上传图片到TOS并返回公网URL
        
        Args:
            image_path: 本地图片路径
            task_id: 任务ID（用于组织文件）
            
        Returns:
            图片的公网访问URL
        """
        try:
            if not os.path.exists(image_path):
                raise FileNotFoundError(f"图片文件不存在: {image_path}")
            
            # 生成对象键（路径）
            file_ext = Path(image_path).suffix.lower()
            timestamp = int(time.time())
            random_id = str(uuid.uuid4())[:8]
            
            if task_id:
                object_key = f"images/{task_id}/{timestamp}_{random_id}{file_ext}"
            else:
                object_key = f"images/{timestamp}_{random_id}{file_ext}"
            
            # 在线程池中执行同步上传
            loop = asyncio.get_event_loop()
            url = await loop.run_in_executor(None, self._sync_upload, image_path, object_key)
            
            self.logger.info(f"图片上传成功: {object_key} -> {url}")
            return url
            
        except Exception as e:
            self.logger.error(f"图片上传失败: {e}")
            raise
    
    def _sync_upload(self, image_path: str, object_key: str) -> str:
        """同步上传图片"""
        client = self._get_client()
        
        # 使用put_object_from_file方法（参照官方项目）
        result = client.put_object_from_file(
            bucket=self.bucket,
            key=object_key, 
            file_path=image_path
        )
        
        # 生成预签名URL（参照官方项目方式）
        import tos
        pre_signed_result = client.pre_signed_url(
            tos.HttpMethodType.Http_Method_Get,
            bucket=self.bucket, 
            key=object_key,
            expires=86400  # 24小时有效期
        )
        
        return pre_signed_result.signed_url
    
    async def upload_multiple_images(self, image_paths: list, task_id: str = None) -> list:
        """
        批量上传图片
        
        Args:
            image_paths: 图片路径列表
            task_id: 任务ID
            
        Returns:
            上传结果列表：[{'local_path': str, 'url': str, 'success': bool}]
        """
        results = []
        
        # 并行上传（限制并发数）
        semaphore = asyncio.Semaphore(3)  # 最多3个并发上传
        
        async def upload_single(path):
            async with semaphore:
                try:
                    url = await self.upload_image(path, task_id)
                    return {'local_path': path, 'url': url, 'success': True}
                except Exception as e:
                    self.logger.error(f"上传失败 {path}: {e}")
                    return {'local_path': path, 'url': None, 'success': False, 'error': str(e)}
        
        # 创建上传任务
        tasks = [upload_single(path) for path in image_paths]
        results = await asyncio.gather(*tasks)
        
        success_count = sum(1 for r in results if r['success'])
        self.logger.info(f"批量上传完成: {success_count}/{len(image_paths)} 成功")
        
        return results
    
    async def delete_object(self, object_key: str) -> bool:
        """
        删除TOS对象
        
        Args:
            object_key: 对象键
            
        Returns:
            删除是否成功
        """
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._sync_delete, object_key)
            self.logger.info(f"对象删除成功: {object_key}")
            return True
        except Exception as e:
            self.logger.error(f"对象删除失败: {object_key}, {e}")
            return False
    
    def _sync_delete(self, object_key: str):
        """同步删除对象"""
        client = self._get_client()
        client.delete_object(bucket=self.bucket, key=object_key)
    
    async def cleanup_task_images(self, task_id: str) -> int:
        """
        清理任务相关的图片
        
        Args:
            task_id: 任务ID
            
        Returns:
            删除的文件数量
        """
        try:
            prefix = f"images/{task_id}/"
            loop = asyncio.get_event_loop()
            deleted_count = await loop.run_in_executor(None, self._sync_cleanup, prefix)
            
            self.logger.info(f"任务图片清理完成: {deleted_count} 个文件")
            return deleted_count
        except Exception as e:
            self.logger.error(f"任务图片清理失败: {e}")
            return 0
    
    def _sync_cleanup(self, prefix: str) -> int:
        """同步清理指定前缀的对象"""
        client = self._get_client()
        
        # 列出对象
        try:
            response = client.list_objects_v2(bucket=self.bucket, prefix=prefix)
            objects = response.contents if hasattr(response, 'contents') else []
            
            # 批量删除
            deleted_count = 0
            for obj in objects:
                try:
                    client.delete_object(bucket=self.bucket, key=obj.key)
                    deleted_count += 1
                except Exception as e:
                    self.logger.warning(f"删除对象失败: {obj.key}, {e}")
            
            return deleted_count
        except Exception as e:
            self.logger.error(f"列出对象失败: {e}")
            return 0


if __name__ == "__main__":
    # 测试代码
    import asyncio
    from utils.file_utils import load_config
    
    async def test_tos():
        config = load_config("config.yaml")
        client = TOSClient(config)
        
        # 创建测试图片
        test_image = "./test_image.jpg"
        with open(test_image, "wb") as f:
            f.write(b"fake image data for testing")
        
        try:
            # 测试上传
            url = await client.upload_image(test_image, "test_task")
            print(f"上传成功: {url}")
            
            # 测试清理
            deleted = await client.cleanup_task_images("test_task")
            print(f"清理完成: {deleted} 个文件")
            
        finally:
            # 清理测试文件
            if os.path.exists(test_image):
                os.remove(test_image)
    
    # 运行测试
    # asyncio.run(test_tos())