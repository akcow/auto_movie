#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
语音合成模块
负责调用火山引擎TTS API，将文本转换为语音
"""

import os
import asyncio
import base64
import time
import json
import re
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import requests
import sys
sys.path.append(str(Path(__file__).parent.parent))

from utils.logger import LoggerMixin
from utils.api_utils import APIUtils, cost_tracker
from utils.file_utils import FileUtils
from utils.database import DatabaseManager


class TTSClient(LoggerMixin):
    """语音合成客户端"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化TTS客户端
        
        Args:
            config: 配置字典
        """
        self.config = config
        self.api_config = config.get('api', {}).get('volcengine', {})
        self.models_config = config.get('models', {})
        self.generation_config = config.get('generation', {})
        self.storage_config = config.get('storage', {})
        
        # TTS简单认证配置
        self.tts_appid = self.api_config.get('tts_appid')
        self.tts_access_token = self.api_config.get('tts_access_token')
        self.region = self.api_config.get('region', 'cn-beijing')
        self.voice = self.models_config.get('tts_voice', 'zh_female_cancan_mars_bigtts')
        
        if not all([self.tts_appid, self.tts_access_token]):
            raise ValueError("TTS API配置不完整，请在config.yaml中配置 tts_appid 和 tts_access_token")
        
        # API工具
        self.api_utils = APIUtils(config)
        
        # 生成参数
        self.tts_speed = self.generation_config.get('tts_speed', 1.0)
        self.tts_volume = self.generation_config.get('tts_volume', 1.0)
        self.audio_format = self.generation_config.get('audio_format', 'wav')
        
        # 存储配置
        self.temp_dir = self.storage_config.get('temp_dir', './data/temp')
        self.output_dir = self.storage_config.get('output_dir', './data/output')
        
        # 确保目录存在
        FileUtils.ensure_dir(self.temp_dir)
        FileUtils.ensure_dir(self.output_dir)
        
        # 数据库
        self.db = DatabaseManager(self.storage_config.get('database_path', './data/database.db'))
        
        # TTS音色配置（使用官方音色ID）
        self.voice_config = {
            'zh_female_qingxin': 'zh_female_cancan_mars_bigtts',
            'zh_male_yangqi': 'zh_male_M392_conversation_wvae_bigtts',
            'zh_female_wenrou': 'BV705_streaming',
            'zh_male_chunhou': 'BV001_streaming'
        }
    
    def _safe_decode(self, byte_data: bytes) -> str:
        """安全地解码字节数据，处理编码问题"""
        try:
            return byte_data.decode('utf-8')
        except UnicodeDecodeError:
            try:
                return byte_data.decode('gbk')
            except UnicodeDecodeError:
                return byte_data.decode('utf-8', errors='ignore')
    
    async def synthesize_speech(
        self, 
        script_data: Dict[str, Any], 
        task_id: str
    ) -> Dict[str, Any]:
        """
        合成语音
        
        Args:
            script_data: 脚本数据
            task_id: 任务ID
            
        Returns:
            语音文件信息
        """
        try:
            self.logger.info(f"开始语音合成: {script_data['title']}")
            
            # 获取旁白文本
            narration = script_data.get('narration', '')
            self.logger.info(f"旁白文本长度: {len(narration)}, 前100字符: {narration[:100]}")
            
            if not narration:
                # 如果没有旁白，生成简单的介绍
                narration = f"这是{script_data['title']}的故事。"
            
            # 预处理文本
            processed_text = self._preprocess_text(narration)
            
            # 分段处理长文本
            text_segments = self._split_text(processed_text)
            
            # 合成语音段落
            audio_segments = []
            total_duration = 0
            
            for i, segment in enumerate(text_segments):
                segment_result = await self._synthesize_segment(
                    text=segment,
                    segment_index=i,
                    task_id=task_id
                )
                
                if segment_result:
                    audio_segments.append(segment_result)
                    total_duration += segment_result['duration']
            
            if not audio_segments:
                raise ValueError("所有语音段落合成失败")
            
            # 如果有多个段落，需要合并
            if len(audio_segments) > 1:
                final_audio_path = await self._merge_audio_segments(
                    audio_segments, task_id
                )
            else:
                final_audio_path = audio_segments[0]['file_path']
            
            # 验证最终音频
            is_valid, audio_info = self._validate_audio(final_audio_path)
            
            if not is_valid:
                self.logger.warning(f"音频质量不合格: {final_audio_path}")
            
            # 计算成本
            char_count = len(processed_text)
            cost = char_count * 0.0002  # 火山引擎TTS成本约0.0002元/字
            
            # 构建结果
            result = {
                'text': processed_text,
                'segments': len(text_segments),
                'file_path': final_audio_path,
                'file_size': audio_info['file_size'],
                'duration': audio_info['duration'],
                'format': audio_info['format'],
                'sample_rate': audio_info['sample_rate'],
                'char_count': char_count,
                'cost': cost,
                'voice': self.voice
            }
            
            # 保存到数据库
            self.db.save_media_generation(
                task_id=task_id,
                media_type='audio',
                description=f"语音合成: {script_data['title']}",
                file_path=final_audio_path,
                file_size=audio_info['file_size'],
                duration=audio_info['duration'],
                cost=cost,
                processing_time=sum(seg.get('processing_time', 0) for seg in audio_segments)
            )
            
            # 记录成本
            cost_tracker.add_cost('tts', cost, 1)
            
            self.logger.info(f"语音合成完成: {char_count}字, {audio_info['duration']:.1f}秒")
            return result
            
        except Exception as e:
            self.logger.error(f"语音合成失败: {e}")
            raise
    
    def _preprocess_text(self, text: str) -> str:
        """
        预处理文本
        
        Args:
            text: 原始文本
            
        Returns:
            处理后的文本
        """
        # 移除markdown标记
        text = re.sub(r'[#*_`]', '', text)
        
        # 统一标点符号
        text = text.replace('。。。', '...')
        text = text.replace('！！', '！')
        text = text.replace('？？', '？')
        
        # 移除多余的空白
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        # 确保句子结尾有标点
        if text and text[-1] not in '。！？.!?':
            text += '。'
        
        # 处理数字和特殊符号
        text = self._normalize_numbers(text)
        
        return text
    
    def _normalize_numbers(self, text: str) -> str:
        """标准化数字和特殊符号"""
        # 将阿拉伯数字转换为中文数字
        number_map = {
            '0': '零', '1': '一', '2': '二', '3': '三', '4': '四',
            '5': '五', '6': '六', '7': '七', '8': '八', '9': '九'
        }
        
        # 简单的数字转换（仅处理单个数字）
        for num, chinese in number_map.items():
            text = text.replace(num, chinese)
        
        # 处理常见的英文缩写
        text = text.replace('AI', '人工智能')
        text = text.replace('API', '接口')
        text = text.replace('VIP', '会员')
        
        return text
    
    def _split_text(self, text: str, max_length: int = 200) -> List[str]:
        """
        分割长文本
        
        Args:
            text: 文本内容
            max_length: 最大长度
            
        Returns:
            文本段落列表
        """
        if len(text) <= max_length:
            return [text]
        
        segments = []
        sentences = re.split(r'[。！？.!?]', text)
        
        current_segment = ""
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # 加上标点符号
            if sentence:
                if text.find(sentence) + len(sentence) < len(text):
                    # 找到原句的标点符号
                    next_char_pos = text.find(sentence) + len(sentence)
                    if next_char_pos < len(text):
                        punctuation = text[next_char_pos]
                        if punctuation in '。！？.!?':
                            sentence += punctuation
                        else:
                            sentence += '。'
                    else:
                        sentence += '。'
            
            # 检查是否超出长度限制
            if len(current_segment) + len(sentence) > max_length:
                if current_segment:
                    segments.append(current_segment.strip())
                    current_segment = sentence
                else:
                    # 单个句子太长，强制分割
                    segments.append(sentence[:max_length])
                    current_segment = sentence[max_length:]
            else:
                current_segment += sentence
        
        if current_segment:
            segments.append(current_segment.strip())
        
        return [seg for seg in segments if seg.strip()]
    
    async def _synthesize_segment(
        self, 
        text: str, 
        segment_index: int, 
        task_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        合成单个文本段落
        
        Args:
            text: 文本内容
            segment_index: 段落索引
            task_id: 任务ID
            
        Returns:
            语音段落信息
        """
        try:
            start_time = time.time()
            
            # 调用TTS API
            self.logger.info(f"开始合成语音段落 [{segment_index}]: {text[:50]}...")
            audio_data = await self._call_tts_api(text)
            self.logger.info(f"TTS API调用成功，返回 {len(audio_data)} 字节音频数据")
            
            # 保存音频文件
            filename = f"{task_id}_speech_{segment_index:02d}.{self.audio_format}"
            audio_path = await self._save_audio(audio_data, filename)
            self.logger.info(f"音频文件保存成功: {audio_path}")
            
            # 获取音频信息
            is_valid, audio_info = self._validate_audio(audio_path)
            self.logger.info(f"音频验证结果: valid={is_valid}, info={audio_info}")
            
            processing_time = time.time() - start_time
            
            result = {
                'segment_index': segment_index,
                'text': text,
                'file_path': audio_path,
                'file_size': audio_info['file_size'],
                'duration': audio_info['duration'],
                'processing_time': processing_time
            }
            
            self.logger.debug(f"语音段落合成完成: {segment_index} - {len(text)}字")
            return result
            
        except Exception as e:
            self.logger.error(f"语音段落合成失败 [{segment_index}]: {e}")
            return None
    
    async def _call_tts_api(self, text: str) -> bytes:
        """
        调用TTS API
        
        Args:
            text: 文本内容
            
        Returns:
            音频二进制数据
        """
        import uuid
        
        # 获取语音配置
        voice_type = self.voice_config.get(
            self.voice, 
            self.voice_config['zh_female_qingxin']
        )
        
        # 构建请求数据（按照官方TTS参数格式）
        request_data = {
            "app": {
                "appid": self.tts_appid,
                "token": "access_token",    # 固定值
                "cluster": "volcano_tts"    # 固定值
            },
            "user": {
                "uid": "auto_movie_user"
            },
            "audio": {
                "voice_type": voice_type,
                "encoding": "wav" if self.audio_format == 'wav' else 'mp3',
                "speed_ratio": self.tts_speed,
                "volume_ratio": self.tts_volume,
                "pitch_ratio": 1.0
            },
            "request": {
                "reqid": str(uuid.uuid4()),
                "text": text,
                "text_type": "plain",
                "operation": "query"
            }
        }
        
        # 构建请求头（使用简单认证方式）
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer;{self.tts_access_token}",
            "X-TTS-AppId": self.tts_appid,
        }
        
        self.logger.info(f"TTS请求配置 - AppId: {self.tts_appid}, Voice: {voice_type}, Text length: {len(text)}")
        self.logger.debug(f"TTS请求数据: {request_data}")
        
        # 火山引擎TTS API URL（修正的官方地址）
        api_url = "https://openspeech.bytedance.com/api/v1/tts"
        
        try:
            response = await self.api_utils.make_async_request(
                method="POST",
                url=api_url,
                headers=headers,
                json_data=request_data,
                timeout=60
            )
            
            # 处理响应 - 支持多种响应格式
            self.logger.info(f"TTS API响应类型: {type(response)}")
            self.logger.debug(f"TTS API响应内容: {str(response)[:200]}...")
            
            audio_b64 = None
            
            # 情况1: 响应是字典
            if isinstance(response, dict):
                self.logger.info(f"响应字典键: {list(response.keys())}")
                
                # 标准格式: {'code': 0, 'data': 'base64...'}
                if response.get('code') == 0 and 'data' in response:
                    audio_b64 = response['data']
                    self.logger.info("使用标准格式 'data' 字段")
                # 直接返回base64格式: {'binary_data_base64': 'base64...'}
                elif 'binary_data_base64' in response:
                    audio_b64 = response['binary_data_base64']
                    self.logger.info("使用 'binary_data_base64' 字段")
                # 其他可能的格式
                elif 'audio' in response:
                    audio_b64 = response['audio']
                    self.logger.info("使用 'audio' 字段")
                # 查找任何可能的base64字段
                else:
                    for key, value in response.items():
                        if isinstance(value, str) and len(value) > 100:
                            # 检查是否是base64格式
                            try:
                                base64.b64decode(value[:100])
                                audio_b64 = value
                                self.logger.info(f"检测到base64数据在字段: {key}")
                                break
                            except:
                                continue
            
            # 情况2: 响应直接是字符串（可能是base64）
            elif isinstance(response, str) and len(response) > 100:
                try:
                    base64.b64decode(response[:100])
                    audio_b64 = response
                    self.logger.info("响应直接是base64字符串")
                except:
                    pass
            
            if audio_b64:
                try:
                    self.logger.info(f"开始解码base64数据，长度: {len(audio_b64)}")
                    audio_data = base64.b64decode(audio_b64)
                    self.logger.info(f"Base64解码成功，音频数据长度: {len(audio_data)} 字节")
                    return audio_data
                except Exception as decode_error:
                    self.logger.error(f"Base64解码失败: {decode_error}")
                    raise ValueError(f"Base64解码失败: {decode_error}")
            else:
                self.logger.error("未找到有效的音频数据")
                raise ValueError(f"TTS API响应格式异常，无法找到音频数据: {response}")
                
        except Exception as e:
            self.logger.error(f"TTS API调用失败: {e}")
            raise
    
    def _get_access_token(self) -> str:
        """获取访问令牌（TTS使用专用token）"""
        return self.tts_access_token
    
    async def _save_audio(self, audio_data: bytes, filename: str) -> str:
        """
        保存音频文件
        
        Args:
            audio_data: 音频二进制数据
            filename: 文件名
            
        Returns:
            保存的文件路径
        """
        file_path = os.path.join(self.temp_dir, filename)
        
        try:
            with open(file_path, 'wb') as f:
                f.write(audio_data)
            
            self.logger.debug(f"音频保存成功: {file_path}")
            return file_path
            
        except Exception as e:
            self.logger.error(f"音频保存失败: {e}")
            raise
    
    def _validate_audio(self, audio_path: str) -> Tuple[bool, Dict[str, Any]]:
        """
        验证音频质量
        
        Args:
            audio_path: 音频路径
            
        Returns:
            (是否合格, 音频信息)
        """
        try:
            # 使用ffprobe获取音频信息
            import subprocess
            
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_format', '-show_streams', audio_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, encoding='utf-8', errors='ignore')
            
            if result.returncode == 0:
                info = json.loads(result.stdout)
                
                format_info = info.get('format', {})
                duration = float(format_info.get('duration', 0))
                file_size = int(format_info.get('size', 0))
                
                audio_stream = None
                for stream in info.get('streams', []):
                    if stream.get('codec_type') == 'audio':
                        audio_stream = stream
                        break
                
                if audio_stream:
                    sample_rate = int(audio_stream.get('sample_rate', 0))
                    channels = int(audio_stream.get('channels', 0))
                    format_name = format_info.get('format_name', 'unknown')
                else:
                    sample_rate = channels = 0
                    format_name = 'unknown'
                
                audio_info = {
                    'duration': duration,
                    'file_size': file_size,
                    'sample_rate': sample_rate,
                    'channels': channels,
                    'format': format_name
                }
                
                # 基础质量检查
                if duration < 0.5:  # 时长太短
                    return False, audio_info
                
                if file_size < 1024:  # 文件太小
                    return False, audio_info
                
                if sample_rate < 8000:  # 采样率太低
                    return False, audio_info
                
                return True, audio_info
            else:
                # ffprobe失败，使用基础检查
                file_size = FileUtils.get_file_size(audio_path)
                audio_info = {
                    'duration': 0.0,
                    'file_size': file_size,
                    'sample_rate': 24000,
                    'channels': 1,
                    'format': self.audio_format
                }
                
                return file_size > 1024, audio_info
                
        except Exception as e:
            self.logger.error(f"音频验证失败: {e}")
            file_size = FileUtils.get_file_size(audio_path) if FileUtils.path_exists(audio_path) else 0
            audio_info = {
                'duration': 0.0,
                'file_size': file_size,
                'sample_rate': 24000,
                'channels': 1,
                'format': self.audio_format
            }
            return file_size > 0, audio_info
    
    async def _merge_audio_segments(
        self, 
        audio_segments: List[Dict[str, Any]], 
        task_id: str
    ) -> str:
        """
        合并音频段落
        
        Args:
            audio_segments: 音频段落列表
            task_id: 任务ID
            
        Returns:
            合并后的音频文件路径
        """
        output_path = os.path.join(self.temp_dir, f"{task_id}_merged.{self.audio_format}")
        
        try:
            # 使用ffmpeg合并音频
            input_files = [seg['file_path'] for seg in audio_segments]
            
            # 创建输入文件列表
            filelist_path = os.path.join(self.temp_dir, f"{task_id}_filelist.txt")
            with open(filelist_path, 'w', encoding='utf-8') as f:
                for file_path in input_files:
                    f.write(f"file '{file_path}'\n")
            
            # 使用ffmpeg合并
            import subprocess
            
            cmd = [
                'ffmpeg', '-y',  # 覆盖输出文件
                '-f', 'concat',  # 连接模式
                '-safe', '0',    # 允许不安全的文件名
                '-i', filelist_path,
                '-c', 'copy',    # 复制流，不重新编码
                output_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                # 清理临时文件
                Path(filelist_path).unlink(missing_ok=True)
                self.logger.debug(f"音频合并成功: {output_path}")
                return output_path
            else:
                raise RuntimeError(f"FFmpeg合并失败: {self._safe_decode(stderr)}")
                
        except Exception as e:
            self.logger.error(f"音频合并失败: {e}")
            # 返回第一个音频文件
            return audio_segments[0]['file_path'] if audio_segments else ""
    
    def create_silence_audio(
        self, 
        duration: float, 
        filename: str
    ) -> str:
        """
        创建静音音频
        
        Args:
            duration: 时长(秒)
            filename: 文件名
            
        Returns:
            音频文件路径
        """
        output_path = os.path.join(self.temp_dir, filename)
        
        try:
            import subprocess
            
            cmd = [
                'ffmpeg', '-y',
                '-f', 'lavfi',
                '-i', f'anullsrc=channel_layout=mono:sample_rate=24000',
                '-t', str(duration),
                '-c:a', 'pcm_s16le' if self.audio_format == 'wav' else 'mp3',
                output_path
            ]
            
            subprocess.run(cmd, check=True, capture_output=True)
            return output_path
            
        except Exception as e:
            self.logger.error(f"创建静音音频失败: {e}")
            return ""


async def test_tts_client():
    """测试TTS客户端"""
    # 模拟配置
    config = {
        'api': {
            'volcengine': {
                'tts_appid': 'mock_appid',
                'tts_access_token': 'mock_access_token'
            }
        },
        'models': {
            'tts_voice': 'zh_female_qingxin'
        },
        'generation': {
            'tts_speed': 1.0,
            'tts_volume': 1.0,
            'audio_format': 'wav'
        },
        'storage': {
            'temp_dir': './test_temp',
            'output_dir': './test_output',
            'database_path': './test_db.db'
        },
        'api_settings': {
            'max_retries': 3,
            'request_timeout': 30
        }
    }
    
    # 模拟脚本数据
    script_data = {
        'title': '测试故事',
        'narration': '这是一个关于勇气和成长的故事。主角经历了重重困难，最终成为了真正的英雄。'
    }
    
    try:
        client = TTSClient(config)
        
        # 测试文本预处理
        processed = client._preprocess_text("这是一个测试123！！")
        print(f"文本预处理测试: {processed}")
        
        # 测试文本分割
        long_text = "这是第一句。这是第二句！这是第三句？" * 20
        segments = client._split_text(long_text, 100)
        print(f"文本分割测试: {len(segments)} 个段落")
        
        # 测试静音音频创建
        silence_path = client.create_silence_audio(2.0, "test_silence.wav")
        print(f"静音音频测试: {silence_path}")
        
        print("TTS客户端测试完成")
        
    except Exception as e:
        print(f"TTS客户端测试失败: {e}")
    finally:
        # 清理测试文件
        import shutil
        for path in ['./test_temp', './test_output']:
            if Path(path).exists():
                shutil.rmtree(path)
        Path('./test_db.db').unlink(missing_ok=True)


if __name__ == "__main__":
    asyncio.run(test_tts_client())