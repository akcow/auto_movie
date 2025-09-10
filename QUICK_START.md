# 🚀 快速入门指南

**从零开始使用小说转视频自动化工具**

## 📋 第一步：系统准备

### 1.1 检查Python环境
```bash
# 确保Python版本3.8+
python --version
# 输出应该是: Python 3.8.x 或更高版本
```

### 1.2 安装FFmpeg
```bash
# Windows用户：
# 1. 访问 https://ffmpeg.org/download.html
# 2. 下载Windows版本
# 3. 解压到目录（如 C:\ffmpeg）
# 4. 将 C:\ffmpeg\bin 添加到PATH环境变量

# 验证FFmpeg安装
ffmpeg -version
# 应该显示FFmpeg版本信息
```

## 📦 第二步：安装依赖

```bash
# 在项目根目录执行
pip install -r requirements.txt
```

## 🔑 第三步：申请API服务

### 3.1 申请火山引擎API
1. **阅读指南**: 打开 `docs/API申请指南.md`
2. **访问控制台**: https://console.volcengine.com/
3. **申请服务**:
   - 豆包大语言模型
   - 文生图服务
   - 图生视频服务  
   - TTS语音合成服务

### 3.2 获取必要信息
- AccessKey (访问密钥)
- SecretKey (私密密钥)
- 各服务的endpoint地址

## ⚙️ 第四步：配置系统

### 4.1 创建配置文件
```bash
# 复制简化配置模板（推荐新手）
cp config.simple.yaml config.yaml

# 或复制完整配置模板（高级用户）
cp config.yaml.example config.yaml
```

### 4.2 编辑配置文件
打开 `config.yaml`，填入你的API信息：

```yaml
# 必填项
api:
  volcengine:
    access_key: "你的AccessKey"        # ← 替换这里
    secret_key: "你的SecretKey"        # ← 替换这里
    region: "cn-beijing"

models:
  llm_endpoint: "你的LLM endpoint"              # ← 替换这里
  text_to_image_endpoint: "你的文生图endpoint"   # ← 替换这里  
  image_to_video_endpoint: "你的图生视频endpoint" # ← 替换这里
  tts_endpoint: "你的TTS endpoint"             # ← 替换这里
```

## 🎬 第五步：开始使用

### 5.1 准备小说文件
- **格式要求**: .txt文件，UTF-8编码
- **长度建议**: 500-2000字（适合2-4分钟视频）
- **内容建议**: 有清晰情节和场景描述

### 5.2 启动程序

#### 方法一：交互式界面（推荐新手）
```bash
python enhanced_main.py
```
然后按照界面提示操作：
1. 选择"开始新任务"
2. 选择你的小说文件
3. 等待处理完成
4. 查看生成的视频

#### 方法二：命令行模式
```bash
python main.py "你的小说.txt"
```

## 💰 第六步：成本控制

### 6.1 首次使用建议
```yaml
# 在config.yaml中设置较低的成本限制
cost_control:
  enable_cost_limit: true
  daily_limit_yuan: 5          # 每日5元限制
  single_task_limit_yuan: 2    # 单任务2元限制
```

### 6.2 测试建议
- 先用`sample_novel.txt`测试
- 确认功能正常后再处理自己的小说
- 观察第一次的成本消耗情况

## 📊 第七步：查看结果

### 7.1 输出位置
生成的视频会保存在：
```
data/output/小说标题_时间戳/
├── final_video.mp4          # 最终视频
├── storyboard.json          # 分镜脚本
├── images/                  # 生成的图片
└── audio/                   # 语音文件
```

### 7.2 查看统计
```bash
# 查看任务历史
python main.py --stats

# 查看成本统计  
python main.py --cost
```

## 🔧 第八步：问题排查

### 8.1 常见问题
- **API调用失败**: 检查密钥和网络连接
- **FFmpeg错误**: 确认FFmpeg已正确安装
- **内存不足**: 降低并发数或图片质量

### 8.2 查看日志
```bash
# 查看详细日志
tail -f logs/app.log

# 搜索错误信息
grep ERROR logs/app.log
```

### 8.3 获取帮助
- 详细说明: `docs/使用说明.md`
- 项目结构: `PROJECT_STRUCTURE.md`
- 故障排除: `docs/使用说明.md` 的故障排除章节

## 🎯 成功使用的标志

✅ **环境准备完成**
- Python 3.8+ ✓
- FFmpeg安装 ✓
- 依赖包安装 ✓

✅ **配置正确设置**
- API密钥填写 ✓
- Endpoint配置 ✓
- 成本控制设置 ✓

✅ **功能测试通过**
- 示例文件处理成功 ✓
- 视频生成质量满意 ✓
- 成本在预期范围内 ✓

## 🚨 新手注意事项

1. **💰 成本控制**: 首次使用务必设置成本限制
2. **📝 文件准备**: 确保小说文件格式正确
3. **🔑 API配置**: 仔细检查所有API配置
4. **🌐 网络环境**: 确保网络连接稳定
5. **💾 磁盘空间**: 预留足够的磁盘空间

## 📞 获取支持

如果遇到问题：
1. 首先查看 `logs/app.log` 日志文件
2. 参考 `docs/使用说明.md` 故障排除部分
3. 检查配置文件是否正确
4. 确认API服务状态正常

---

**🎉 现在你可以开始将小说转换为精彩的视频了！**

**让AI为你的文字插上视频的翅膀！** 🎬✨