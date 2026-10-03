# Ecommerce Pajama Batch Studio

这是一个面向电商睡衣图片生产的 MVP，目标是把“换衣、换脸、批量处理、ZIP 导出”放进一个简单网页里。

## 当前功能

- 批量上传模特原图
- 单张睡衣 / 服装参考图批量套用
- 单张授权脸部参考图批量替换
- 一次完成“换衣 + 换脸”
- 生成结果预览
- 自动打包 ZIP
- 单张失败不会中断整批，失败项写入 failures.txt
- 支持切换 GPT Image 2.5 Sunburst / Flare

## 运行

安装：

```bash
pip install -r ecommerce_studio/requirements.txt
```

运行前确保环境中已存在 `OPENAI_API_KEY`，然后：

```bash
python ecommerce_studio/app.py
```

默认打开 Gradio Web UI。

## 建议的产品架构

### MVP
- UI：Gradio
- 图像编辑：OpenAI Image API
- 批处理：单进程队列
- 导出：ZIP

### 商业版
- 前端：Next.js
- API：FastAPI
- 队列：Redis + Celery / RQ
- 文件：S3 / R2 / OSS
- 数据库：PostgreSQL
- GPU 本地 VTON：通过 Provider Adapter 接入
- OpenAI：用于高精度换脸、修复、失败兜底
- 任务状态：pending / running / completed / failed
- SKU 批次：一个服装款式可关联多张模特图和多个输出尺寸

## 关于当前 CatVTON 仓库

当前 CatVTON 原项目和权重采用 CC BY-NC-SA 4.0，明确限制为非商业用途。
因此本目录的商业 MVP 不把 CatVTON 作为默认生产引擎。

如果后续取得商业授权，或替换成可商业使用的 VTON 模型，可把它接入统一的
`try_on_provider` 接口，再由 UI 选择“本地 GPU / OpenAI / 其他商业 API”。

## 下一步建议

1. 增加 SKU/批次命名规则
2. 增加并行 worker 和断点续跑
3. 增加失败图片“一键重试”
4. 增加背景锁定、脸部锁定、衣服花纹锁定三个精度开关
5. 增加 1:1、3:4、4:5、9:16 电商尺寸预设
6. 增加生成前后对比和人工质检
7. 增加账号、套餐、用量与成本统计
