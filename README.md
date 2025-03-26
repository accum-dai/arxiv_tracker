# ArXiv Paper Summary Assistant

## Project Overview

ArXiv Paper Summary Assistant is an automation tool for retrieving, downloading, and summarizing the latest academic papers from ArXiv. The tool searches for recent papers based on predefined topic keywords, downloads PDF files, generates detailed structured summaries using large language models (such as GPT-4), and optionally sends summary reports via email.

## Key Features

- 🔍 **Topic Search**: Supports parallel searches across multiple research topics
- 📄 **Automatic Downloads**: Automatically downloads paper PDFs and extracts text content
- 🤖 **AI Summaries**: Generates structured paper summaries using OpenAI API (supports Chinese or English)
- 💾 **History Tracking**: Uses SQLite database to avoid reprocessing previously downloaded papers
- 📧 **Email Notifications**: Supports sending summary reports via email (optional feature)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/accum-dai/arxiv_tracker.git
cd arxiv-summary-assistant
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create configuration file:
   - Copy `.env.example` file to `.env`
   - Edit the `.env` file with your API keys and other configurations

## Configuration

Configure the following parameters in the `.env` file:

```
# API Configuration
OPENAI_API_KEY=your_openai_api_key
OPENAI_API_BASE=https://api.openai.com/v1  # Optional, for custom API endpoints
LLM_MODEL=gpt-4-1106-preview  # Or other supported models

# Search Configuration
SEARCH_TOPICS=large language models,reinforcement learning,computer vision
MAX_PAPERS_PER_TOPIC=30  # Maximum number of papers to retrieve per topic
DAYS_BACK=3  # Search for papers from the last few days
SUMMARY_LANGUAGE=zh  # Summary language, supports 'zh' (Chinese) or 'en' (English)

# File Paths
PDF_DIR=papers_pdf  # PDF storage path
DATABASE_FILE=arxiv_papers.db  # Database file
OUTPUT_DIR=summaries  # Summary output directory

# Delay Settings (seconds)
MIN_API_DELAY=0.5  # Minimum delay between API calls
MAX_API_DELAY=1.0  # Maximum delay between API calls
MIN_DOWNLOAD_DELAY=1  # Minimum delay between downloads
MAX_DOWNLOAD_DELAY=3  # Maximum delay between downloads

# Email Configuration (optional)
EMAIL_ENABLED=true  # Enable email sending
EMAIL_DISPLAY_NAME=ArXiv Summary Assistant
EMAIL_SENDER=your_email@163.com  # Sender email address
EMAIL_PASSWORD=your_auth_code  # Authentication code (not login password)
EMAIL_RECEIVERS=receiver1@example.com,receiver2@example.com  # Recipient email addresses
SMTP_SERVER=smtp.163.com  # SMTP server
SMTP_PORT=465  # SMTP port
```

## Usage

Run the main program:
```bash
python arxiv_tracker.py
```

The program will:
1. Search for the configured topic keywords
2. Download PDF files of new papers
3. Generate structured summaries
4. Create summary text files
5. Send summaries to specified email addresses (if email feature is enabled)

## Automated Execution

### Linux/Mac (using cron)

1. Open terminal and edit crontab:
```bash
crontab -e
```

2. Add the following line to run the script daily at 8 AM (adjust paths as needed):
```
0 8 * * * cd /path/to/arxiv_tracker && /usr/bin/python /path/to/arxiv_tracker/arxiv_tracker.py >> /path/to/arxiv_tracker/cron.log 2>&1
```

### Windows (using Task Scheduler)

1. Open Task Scheduler
2. Click "Create Basic Task"
3. Enter a name (e.g., "ArXiv Paper Tracker") and description
4. Select "Daily" as the trigger
5. Set the time to run daily (e.g., 8:00 AM)
6. Choose "Start a program" as the action
7. Browse and select the Python interpreter (e.g., `C:\Python310\python.exe`)
8. In "Add arguments" enter the full path to the script (e.g., `C:\path\to\arxiv_tracker\arxiv_tracker.py`)
9. In "Start in" enter the directory containing the script (e.g., `C:\path\to\arxiv_tracker`)
10. Complete the setup

### Docker (optional)

If you're using Docker, you can set up in a docker-compose.yml file:

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

Ensure your Dockerfile includes cron setup:

```Dockerfile
# Add to Dockerfile
RUN apt-get update && apt-get -y install cron
RUN echo "0 8 * * * cd /app && python /app/arxiv_tracker.py >> /app/cron.log 2>&1" > /etc/cron.d/arxiv-tracker-cron
RUN chmod 0644 /etc/cron.d/arxiv-tracker-cron
RUN crontab /etc/cron.d/arxiv-tracker-cron
```

## Summary Structure

Each paper summary includes the following six sections:

1. **Background and Motivation**: Research background and motivation of the paper
2. **Core Problem**: Key problems the paper attempts to solve
3. **Methodology**: Methods and techniques employed in the paper
4. **Key Results**: Main research findings of the paper
5. **Innovations and Contributions**: Innovation points and main contributions of the paper
6. **Implications and Future Work**: Significance of the research and future prospects

## Important Notes

- OpenAI API calls will incur charges, ensure your account has sufficient balance
- Email functionality requires an authentication code rather than a login password
- When downloading papers, please comply with ArXiv's terms of use and access frequency limitations

## License

[MIT](LICENSE)