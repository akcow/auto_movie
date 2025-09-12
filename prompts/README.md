# 提示词文件说明

本目录包含了所有模型调用的提示词模板，您可以根据需要自定义修改。

## 提示词文件列表

### 1. 口播文案生成相关

#### `narration_generation.txt`
- **功能**: 用于根据小说内容生成口播文案
- **调用位置**: `processors/narration_generator.py` - `_build_narration_prompt()` 方法
- **参数**: `{novel_title}`, `{content}`, `{style_desc}`, `{target_duration}`, `{target_word_count}`
- **说明**: 生成适合视频解说的完整文案，包含标题、正文、关键点等

#### `narration_expansion.txt`
- **功能**: 扩展过短的口播文案
- **调用位置**: `processors/narration_generator.py` - `_expand_narration()` 方法
- **参数**: `{target_duration}`, `{narration}`
- **说明**: 在保持原有风格的基础上增加细节描述

#### `narration_compression.txt`
- **功能**: 压缩过长的口播文案
- **调用位置**: `processors/narration_generator.py` - `_compress_narration()` 方法
- **参数**: `{target_duration}`, `{narration}`
- **说明**: 保留核心信息，删除次要细节

### 2. 分镜脚本生成相关

#### `shot_script_generation.txt`
- **功能**: 根据口播文案生成分镜脚本
- **调用位置**: `processors/shot_planner.py` - `_build_shot_script_prompt()` 方法
- **参数**: `{title}`, `{target_duration}`, `{shot_count}`, `{narration}`, `{key_points}`, `{dynamic_shot_count}`, `{static_duration}`, `{min_shot_duration}`, `{max_shot_duration}`
- **说明**: 智能决策分镜数量和时长，生成详细的视觉描述

#### `shot_description_enhancement.txt`
- **功能**: 增强分镜的视觉描述
- **调用位置**: `processors/shot_planner.py` - `_enhance_shot_description()` 方法
- **参数**: `{shot_type}`, `{current_desc}`, `{narration}`
- **说明**: 为AI图像生成提供更详细的视觉指导

### 3. 传统分镜脚本生成

#### `storyboard_generation.txt`
- **功能**: 直接从小说内容生成传统分镜脚本
- **调用位置**: `processors/llm_client.py` - `_get_default_storyboard_template()` 方法
- **参数**: `{title}`, `{content}`, `{word_count}`, `{max_images}`, `{video_segments}`, `{video_duration}`
- **说明**: 旧版工作流使用的分镜生成模板

### 4. 图像生成相关

#### `image_generation.txt`
- **功能**: 图像生成的提示词模板
- **调用位置**: `processors/image_gen.py` - `_build_image_prompt()` 方法
- **参数**: `{style}`, `{description}`
- **说明**: 用于通义万相等图像生成API的提示词

### 5. 视频生成相关

#### `video_generation.txt`
- **功能**: 视频生成的提示词模板
- **调用位置**: `processors/video_gen.py` - `_build_video_prompt()` 方法
- **参数**: `{duration}`, `{description}`, `{style}`
- **说明**: 用于图生视频API的提示词

## 修改建议

### 风格自定义
- 修改 `narration_generation.txt` 中的风格描述（第148行），可选择：
  - `engaging`: 生动有趣、富有感染力
  - `documentary`: 客观严谨、纪录片风格
  - `storytelling`: 故事性强、娓娓道来
  - `casual`: 轻松随意、贴近观众

### 图像质量控制
- 修改 `image_generation.txt` 添加更多质量控制参数
- 调整分辨率比例和质量参数

### 视频效果调整
- 修改 `video_generation.txt` 中的动画效果描述
- 可以调整摄像机运动方式和风格

## 注意事项

1. 所有提示词文件使用UTF-8编码
2. 参数占位符使用 `{parameter_name}` 格式
3. 修改后重启程序生效
4. 建议先备份原文件再进行修改
5. 提示词长度不要超过API限制（通常500-1000字符）

## 调试技巧

如果生成效果不理想，可以：
1. 增加更具体的描述词汇
2. 调整提示词的顺序和结构
3. 添加负向提示词（避免某些内容）
4. 根据具体模型特点优化提示词风格