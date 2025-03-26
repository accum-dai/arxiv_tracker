# ArXiv论文摘要助手

## 项目简介

ArXiv论文摘要助手是一个自动化工具，用于检索、下载和总结ArXiv上的最新学术论文。该工具会根据预设的主题关键词搜索最新论文，下载PDF文件，使用大型语言模型（如GPT-4）生成详细的结构化摘要，并可选择通过邮件发送摘要报告。

## 主要功能

- 🔍 **主题检索**：支持多个研究主题的并行检索
- 📄 **自动下载**：自动下载论文PDF文件并提取文本内容
- 🤖 **AI摘要**：使用OpenAI API生成结构化的论文摘要（支持中文或英文）
- 💾 **历史记录**：使用SQLite数据库避免重复处理已下载的论文
- 📧 **邮件通知**：支持通过邮件发送摘要报告（可选功能）

## 安装步骤

1. 克隆仓库:
```bash
git clone https://github.com/accum-dai/arxiv_tracker.git
cd arxiv-summary-assistant
```

2. 安装依赖:
```bash
pip install -r requirements.txt
```

3. 创建配置文件:
   - 复制`.env.example`文件为`.env`
   - 编辑`.env`文件，填入您的API密钥和其他配置

## 配置说明

在`.env`文件中配置以下参数:

```
# API配置
OPENAI_API_KEY=您的OpenAI API密钥
OPENAI_API_BASE=https://api.openai.com/v1  # 可选，使用自定义API端点
LLM_MODEL=gpt-4-1106-preview  # 或其他支持的模型

# 搜索配置
SEARCH_TOPICS=large language models,reinforcement learning,computer vision
MAX_PAPERS_PER_TOPIC=30  # 每个主题最多检索的论文数量
DAYS_BACK=3  # 搜索最近几天的论文
SUMMARY_LANGUAGE=zh  # 摘要语言，支持 'zh'(中文) 或 'en'(英文)

# 文件路径
PDF_DIR=papers_pdf  # PDF存储路径
DATABASE_FILE=arxiv_papers.db  # 数据库文件
OUTPUT_DIR=summaries  # 摘要输出目录

# 延迟设置（秒）
MIN_API_DELAY=0.5  # API调用最小延迟
MAX_API_DELAY=1.0  # API调用最大延迟
MIN_DOWNLOAD_DELAY=1  # 下载最小延迟
MAX_DOWNLOAD_DELAY=3  # 下载最大延迟

# 邮件配置（可选）
EMAIL_ENABLED=true  # 是否启用邮件发送
EMAIL_DISPLAY_NAME=ArXiv Summary Assistant
EMAIL_SENDER=your_email@163.com  # 发件人邮箱
EMAIL_PASSWORD=your_auth_code  # 授权码（非登录密码）
EMAIL_RECEIVERS=receiver1@example.com,receiver2@example.com  # 收件人邮箱
SMTP_SERVER=smtp.163.com  # SMTP服务器
SMTP_PORT=465  # SMTP端口
```

## 使用方法

运行主程序:
```bash
python arxiv_tracker.py
```

程序将会:
1. 搜索配置的主题关键词
2. 下载新论文的PDF文件
3. 生成结构化摘要
4. 创建摘要文本文件
5. 如果启用了邮件功能，将摘要发送至指定邮箱

## 自动化运行

### Linux/Mac (使用cron)

1. 打开终端，编辑crontab:
```bash
crontab -e
```

2. 添加以下行来每天早上8点运行脚本(请根据需要调整路径):
```
0 8 * * * cd /path/to/arxiv_tracker && /usr/bin/python /path/to/arxiv_tracker/arxiv_tracker.py >> /path/to/arxiv_tracker/cron.log 2>&1
```

### Windows (使用任务计划程序)

1. 打开任务计划程序(Task Scheduler)
2. 点击"创建基本任务"
3. 输入任务名称(如 "ArXiv论文追踪器")和描述
4. 选择"每天"作为触发器
5. 设置每天运行的时间(如早上8:00)
6. 选择"启动程序"作为操作
7. 浏览并选择Python解释器(如 `C:\Python310\python.exe`)
8. 在"添加参数"中输入脚本的完整路径(如 `C:\path\to\arxiv_tracker\arxiv_tracker.py`)
9. 在"起始于"中输入脚本所在的目录(如 `C:\path\to\arxiv_tracker`)
10. 完成设置

### Docker (可选)

如果您使用Docker，可以在docker-compose.yml文件中设置:

```yaml
version: '3'
services:
  arxiv-tracker:
    build: .
    volumes:
      - ./:/app
    environment:
      - TZ=Asia/Shanghai
    restart: unless-stopped
    command: sh -c "cron && crond -f"
```

确保Dockerfile中包含了cron的设置:

```Dockerfile
# 在Dockerfile中添加
RUN apt-get update && apt-get -y install cron
RUN echo "0 8 * * * cd /app && python /app/arxiv_tracker.py >> /app/cron.log 2>&1" > /etc/cron.d/arxiv-tracker-cron
RUN chmod 0644 /etc/cron.d/arxiv-tracker-cron
RUN crontab /etc/cron.d/arxiv-tracker-cron
```

## 摘要结构

每篇论文的摘要包含以下六个部分:

1. **研究背景与动机**：论文的研究背景和研究动机
2. **核心问题**：论文试图解决的关键问题
3. **方法与技术**：论文采用的方法和技术
4. **关键结果**：论文的主要研究结果
5. **创新与贡献**：论文的创新点和主要贡献
6. **意义与展望**：研究的意义和未来展望

## 注意事项

- OpenAI API调用会产生费用，请确保您的账户有足够余额
- 邮件功能需要使用授权码而非登录密码
- 下载论文时请遵守ArXiv的使用条款和访问频率限制

## 许可证

[MIT](LICENSE)