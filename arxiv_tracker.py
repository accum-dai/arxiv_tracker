import os
import time
import random
import sqlite3
import arxiv
import openai
import PyPDF2
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Iterator
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class Config:
    # API配置
    API_KEY = os.getenv("OPENAI_API_KEY")
    API_BASE = os.getenv("OPENAI_API_BASE")
    LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4-1106-preview")
    
    # 搜索配置
    SEARCH_TOPICS = [t.strip() for t in os.getenv("SEARCH_TOPICS", "large language models,reinforcement learning,computer vision").split(",")]
    MAX_PAPERS_PER_TOPIC = int(os.getenv("MAX_PAPERS_PER_TOPIC", 30))
    DAYS_BACK = int(os.getenv("DAYS_BACK", 3))
    
    # 文件路径
    PDF_DIR = os.getenv("PDF_DIR", "papers_pdf")
    DATABASE_FILE = os.getenv("DATABASE_FILE", "arxiv_papers.db")
    OUTPUT_DIR = os.getenv("OUTPUT_DIR", "summaries")
    
    # 延迟设置
    MIN_API_DELAY = float(os.getenv("MIN_API_DELAY", 0.5))
    MAX_API_DELAY = float(os.getenv("MAX_API_DELAY", 1.0))
    MIN_DOWNLOAD_DELAY = float(os.getenv("MIN_DOWNLOAD_DELAY", 1))
    MAX_DOWNLOAD_DELAY = float(os.getenv("MAX_DOWNLOAD_DELAY", 3))
    
    # 邮件配置
    EMAIL_ENABLED = os.getenv("EMAIL_ENABLED", "true").lower() == "true"
    EMAIL_SENDER = os.getenv("EMAIL_SENDER")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
    EMAIL_RECEIVERS = [email.strip() for email in os.getenv("EMAIL_RECEIVERS", "").split(",") if email.strip()]
    SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", 587))

# 初始化客户端
arxiv_client = arxiv.Client()
openai_client = openai.OpenAI(
    api_key=Config.API_KEY,
    base_url=Config.API_BASE
)

def send_email(subject: str, content: str, attachment_path: str = None):
    """发送邮件（适配163邮箱）"""
    if not Config.EMAIL_ENABLED or not Config.EMAIL_RECEIVERS:
        print("邮件功能未启用或未配置收件人")
        return False
    
    try:
        msg = MIMEMultipart()
        msg['From'] = Config.EMAIL_SENDER
        msg['To'] = ", ".join(Config.EMAIL_RECEIVERS)
        msg['Subject'] = subject
        
        # 邮件正文（UTF-8编码）
        msg.attach(MIMEText(content, 'plain', 'utf-8'))
        
        # 添加附件
        if attachment_path and os.path.exists(attachment_path):
            with open(attachment_path, "rb") as f:
                part = MIMEApplication(f.read(), Name=os.path.basename(attachment_path))
            part['Content-Disposition'] = f'attachment; filename="{os.path.basename(attachment_path)}"'
            msg.attach(part)
        
        # 163邮箱专用连接方式
        with smtplib.SMTP_SSL(Config.SMTP_SERVER, Config.SMTP_PORT) as server:
            server.login(Config.EMAIL_SENDER, Config.EMAIL_PASSWORD)
            server.sendmail(Config.EMAIL_SENDER, Config.EMAIL_RECEIVERS, msg.as_string())
        
        print(f"邮件成功发送到 {len(Config.EMAIL_RECEIVERS)} 个收件人")
        return True
    except Exception as e:
        print(f"邮件发送失败: {str(e)}")
        return False

def get_output_filename(topic: str) -> str:
    """生成带日期时间和主题的输出文件名"""
    now = datetime.now()
    safe_topic = "".join(c if c.isalnum() else "_" for c in topic)
    filename = f"arxiv_{safe_topic}_{now.strftime('%Y%m%d_%H%M%S')}.txt"
    return os.path.join(Config.OUTPUT_DIR, filename)

def init_database():
    """初始化SQLite数据库"""
    os.makedirs(Config.OUTPUT_DIR, exist_ok=True)
    os.makedirs(Config.PDF_DIR, exist_ok=True)
    conn = sqlite3.connect(Config.DATABASE_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS processed_papers
                 (paper_id TEXT PRIMARY KEY,
                  processed_date TEXT)''')
    conn.commit()
    conn.close()

def is_paper_processed(paper_id: str) -> bool:
    """检查论文是否已处理过"""
    conn = sqlite3.connect(Config.DATABASE_FILE)
    c = conn.cursor()
    c.execute("SELECT 1 FROM processed_papers WHERE paper_id=?", (paper_id,))
    result = c.fetchone()
    conn.close()
    return result is not None

def mark_paper_as_processed(paper_id: str):
    """将论文标记为已处理"""
    conn = sqlite3.connect(Config.DATABASE_FILE)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO processed_papers VALUES (?, ?)",
              (paper_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def search_arxiv_papers(topic: str) -> Iterator[arxiv.Result]:
    """搜索ArXiv论文"""
    search = arxiv.Search(
        query=topic,
        max_results=Config.MAX_PAPERS_PER_TOPIC,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending
    )
    return arxiv_client.results(search)

def download_pdf(paper: arxiv.Result) -> Optional[tuple]:
    """下载论文PDF并返回文本内容"""
    paper_id = paper.get_short_id()
    filename = f"{paper_id}.pdf"
    filepath = os.path.join(Config.PDF_DIR, filename)
    
    try:
        delay = random.uniform(Config.MIN_DOWNLOAD_DELAY, Config.MAX_DOWNLOAD_DELAY)
        print(f"等待 {delay:.1f} 秒后下载PDF...")
        time.sleep(delay)
        
        paper.download_pdf(filename=filepath)
        
        with open(filepath, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            text = "\n".join(page.extract_text() for page in reader.pages if page.extract_text())
        
        return text, filepath
    except Exception as e:
        print(f"下载或处理PDF失败: {str(e)}")
        return None

def generate_llm_summary(paper: arxiv.Result, paper_text: str, topic: str) -> str:
    """使用LLM生成中文结构化论文摘要"""
    prompt = f"""请为以下学术论文生成详细的中文摘要，必须包含以下六个部分：

1. 研究背景与动机
2. 核心问题
3. 方法与技术
4. 关键结果
5. 创新与贡献
6. 意义与展望

论文信息:
标题: {paper.title}
作者: {', '.join(author.name for author in paper.authors)}
发表日期: {paper.published.date() if paper.published else '未知'}
ArXiv链接: {paper.entry_id}

请基于以下论文内容生成摘要:
{paper_text[:12000]}..."""

    try:
        delay = random.uniform(Config.MIN_API_DELAY, Config.MAX_API_DELAY)
        print(f"等待 {delay:.1f} 秒后调用API生成中文摘要...")
        time.sleep(delay)
        
        response = openai_client.chat.completions.create(
            model=Config.LLM_MODEL,
            messages=[
                {"role": "system", "content": "你是一位资深学术研究员，需要用中文总结论文核心内容。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"生成摘要时出错: {str(e)}")
        return f"无法生成中文摘要: {str(e)}"

def process_topic(topic: str) -> List[Dict]:
    """处理单个主题，返回论文摘要列表"""
    print(f"\n{'='*40}")
    print(f"开始处理主题: {topic}")
    
    papers = list(search_arxiv_papers(topic))
    new_papers = [p for p in papers if not is_paper_processed(p.get_short_id())]
    
    if not new_papers:
        print(f"没有发现新论文。")
        return []
    
    print(f"\n找到 {len(new_papers)} 篇新论文，开始处理...")
    summaries = []
    
    for i, paper in enumerate(new_papers, 1):
        print(f"\n[进度 {i}/{len(new_papers)}] {paper.title}")
        
        try:
            result = download_pdf(paper)
            if not result:
                continue
                
            paper_text, pdf_path = result
            llm_summary = generate_llm_summary(paper, paper_text, topic)
            
            summary = {
                "title": paper.title,
                "url": paper.entry_id,
                "arxiv_summary": paper.summary,
                "llm_summary": llm_summary,
                "pdf_path": pdf_path
            }
            
            summaries.append(summary)
            mark_paper_as_processed(paper.get_short_id())
            print("论文处理完成!")
            
        except Exception as e:
            print(f"处理论文时出错: {str(e)}")
            continue
    
    return summaries

def main():
    print("初始化数据库...")
    init_database()
    
    start_time = time.time()
    all_summaries = []
    email_attachments = []
    
    # 处理所有主题
    for topic in Config.SEARCH_TOPICS:
        topic_summaries = process_topic(topic)
        all_summaries.extend(topic_summaries)
        
        # 保存当前主题结果
        if topic_summaries:
            output_file = get_output_filename(topic)
            email_attachments.append(output_file)
            
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(f"ArXiv论文AI摘要汇总\n")
                f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"主题: {topic}\n")
                f.write(f"共处理 {len(topic_summaries)} 篇新论文\n\n")
                
                for summary in topic_summaries:
                    f.write(f"【论文标题】 {summary['title']}\n")
                    f.write(f"【ArXiv链接】 {summary['url']}\n\n")
                    f.write("=== AI生成中文摘要 ===\n")
                    f.write(f"{summary['llm_summary']}\n")
                    f.write("="*80 + "\n\n")
    
    # 发送汇总邮件
    if all_summaries and Config.EMAIL_ENABLED and Config.EMAIL_RECEIVERS:
        email_content = f"今日ArXiv论文摘要汇总 ({datetime.now().strftime('%Y-%m-%d')})\n\n"
        email_content += f"共找到 {len(all_summaries)} 篇新论文\n\n"
        email_content += "详细信息请查看附件中的摘要文件。\n\n"
        email_content += "以下是各论文基本信息：\n\n"
        
        for summary in all_summaries:
            email_content += f"论文标题: {summary['title']}\n"
            email_content += f"ArXiv链接: {summary['url']}\n"
            email_content += "-"*60 + "\n"
        
        # 发送邮件（带所有附件）
        for attachment in email_attachments:
            send_email(
                subject=f"ArXiv论文摘要 {datetime.now().strftime('%Y-%m-%d')}",
                content=email_content,
                attachment_path=attachment
            )
    
    elapsed = time.time() - start_time
    print(f"\n{'='*40}")
    print(f"完成所有主题 | 用时: {elapsed:.1f}秒")
    print(f"总处理论文数: {len(all_summaries)}")
    print(f"生成摘要文件: {len(email_attachments)} 个")
    print(f"{'='*40}")

if __name__ == "__main__":
    main()