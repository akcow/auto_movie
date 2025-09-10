# TTS语音合成配置指南

## 🎯 已修复的问题

### 修改内容
1. **API端点修正**: `openspeech.volcengineapi.com` → `openspeech.bytedance.com`
2. **认证方式修正**: `Bearer token` → `Bearer;token`（分号分隔）
3. **参数配置修正**: 使用实际的appid和access_token，而不是硬编码示例值
4. **音色ID更新**: 使用官方正确的音色标识符

### 新增配置项
在 `config.yaml` 中需要添加：
```yaml
api:
  volcengine:
    # TTS专用配置
    tts_appid: "你的TTS应用ID"
    tts_access_token: "你的TTS访问令牌"
```

## 🔑 如何获取TTS配置信息

### 1. 登录火山引擎控制台
访问：https://console.volcengine.com/

### 2. 进入语音合成服务
- 搜索"语音合成"或"TTS"
- 进入语音合成控制台

### 3. 获取必要信息

#### 获取APP ID
- 在控制台找到"应用管理"或"App管理"
- 查看或创建应用，获取APP ID
- 格式类似：`appid123456`

#### 获取Access Token
- 在应用详情中找到"访问令牌"或"Access Token"
- 复制Token值
- 格式类似：`token_abcdef123456`

#### 选择音色
确认你有权限使用的音色ID，例如：
- `zh_female_cancan_mars_bigtts` (女声)
- `zh_male_M392_conversation_wvae_bigtts` (男声)
- `BV001_streaming` (免费音色)
- `BV705_streaming` (免费音色)

### 4. 配置示例
```yaml
api:
  volcengine:
    access_key_id: "AKLTxxxxxxxxxxxxxxxx"  # 其他服务用
    secret_access_key: "xxxxxxxxxxxxxxxxx"  # 其他服务用
    region: "cn-beijing"
    
    # TTS专用配置
    tts_appid: "你的实际APP ID"           # 从控制台获取
    tts_access_token: "你的实际Token"      # 从控制台获取

style:
  tts_voice: "zh_female_qingxin"          # 音色选择
```

## ⚠️ 重要注意事项

1. **TTS认证独立**: TTS服务的认证方式与其他火山引擎服务不同
2. **免费音色**: 优先使用免费音色进行测试
3. **权限确认**: 确保选择的音色已获得使用授权
4. **唯一性要求**: 每次调用的reqid必须唯一（已自动处理）

## 🧪 测试建议

1. **先测试免费音色**: 使用 `BV001_streaming` 等免费音色
2. **短文本测试**: 先用简短文本测试连通性
3. **查看日志**: 检查 `logs/app.log` 了解详细错误信息

## 🎉 修改完成

TTS代码已按照火山引擎官方文档标准修改，现在需要：
1. 填入正确的 `tts_appid` 和 `tts_access_token`
2. 选择合适的音色
3. 测试运行

修改完配置后，TTS服务应该能够正常工作！