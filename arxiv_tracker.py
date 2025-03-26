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
from email.utils import formataddr
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Iterator, Tuple
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    # API Configuration
    API_KEY = os.getenv("OPENAI_API_KEY")
    API_BASE = os.getenv("OPENAI_API_BASE")
    LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4-1106-preview")
    
    # Search Configuration
    SEARCH_TOPICS = [t.strip() for t in os.getenv("SEARCH_TOPICS", "large language models,reinforcement learning,computer vision").split(",")]
    MAX_PAPERS_PER_TOPIC = int(os.getenv("MAX_PAPERS_PER_TOPIC", 30))
    DAYS_BACK = int(os.getenv("DAYS_BACK", 3))
    SUMMARY_LANGUAGE = os.getenv("SUMMARY_LANGUAGE", "zh").lower()  # 'zh' or 'en'
    
    # File Paths
    PDF_DIR = os.getenv("PDF_DIR", "papers_pdf")
    DATABASE_FILE = os.getenv("DATABASE_FILE", "arxiv_papers.db")
    OUTPUT_DIR = os.getenv("OUTPUT_DIR", "summaries")
    
    # Delay Settings (seconds)
    MIN_API_DELAY = float(os.getenv("MIN_API_DELAY", 0.5))
    MAX_API_DELAY = float(os.getenv("MAX_API_DELAY", 1.0))
    MIN_DOWNLOAD_DELAY = float(os.getenv("MIN_DOWNLOAD_DELAY", 1))
    MAX_DOWNLOAD_DELAY = float(os.getenv("MAX_DOWNLOAD_DELAY", 3))
    
    # Email Configuration
    EMAIL_ENABLED = os.getenv("EMAIL_ENABLED", "true").lower() == "true"
    EMAIL_DISPLAY_NAME = os.getenv("EMAIL_DISPLAY_NAME", "ArXiv论文助手")
    EMAIL_SENDER = os.getenv("EMAIL_SENDER")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
    EMAIL_RECEIVERS = [email.strip() for email in os.getenv("EMAIL_RECEIVERS", "").split(",") if email.strip()]
    SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.163.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", 465))

# Initialize clients
arxiv_client = arxiv.Client()
openai_client = openai.OpenAI(
    api_key=Config.API_KEY,
    base_url=Config.API_BASE
)

def get_output_filename(topic: str) -> str:
    """Generate output filename with date and topic"""
    now = datetime.now()
    safe_topic = "".join(c if c.isalnum() else "_" for c in topic)
    return os.path.join(Config.OUTPUT_DIR, f"arxiv_{safe_topic}_{now.strftime('%Y%m%d')}.txt")

def init_database():
    """Initialize SQLite database"""
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
    """Check if paper has been processed"""
    conn = sqlite3.connect(Config.DATABASE_FILE)
    c = conn.cursor()
    c.execute("SELECT 1 FROM processed_papers WHERE paper_id=?", (paper_id,))
    result = c.fetchone()
    conn.close()
    return result is not None

def mark_paper_as_processed(paper_id: str):
    """Mark paper as processed in database"""
    conn = sqlite3.connect(Config.DATABASE_FILE)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO processed_papers VALUES (?, ?)",
              (paper_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def search_arxiv_papers(topic: str) -> Iterator[arxiv.Result]:
    """Search for papers on arXiv"""
    search = arxiv.Search(
        query=topic,
        max_results=Config.MAX_PAPERS_PER_TOPIC,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending
    )
    return arxiv_client.results(search)

def download_pdf(paper: arxiv.Result) -> Optional[Tuple[str, str]]:
    """Download paper PDF and return (text content, file path)"""
    paper_id = paper.get_short_id()
    filename = f"{paper_id}.pdf"
    filepath = os.path.join(Config.PDF_DIR, filename)
    
    try:
        delay = random.uniform(Config.MIN_DOWNLOAD_DELAY, Config.MAX_DOWNLOAD_DELAY)
        print(f"Waiting {delay:.1f}s before downloading PDF...")
        time.sleep(delay)
        
        paper.download_pdf(filename=filepath)
        
        with open(filepath, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            text = "\n".join(page.extract_text() for page in reader.pages if page.extract_text())
        
        return text, filepath
    except Exception as e:
        print(f"Failed to download/process PDF: {str(e)}")
        return None

def get_summary_prompt(paper: arxiv.Result, paper_text: str) -> str:
    """Generate appropriate prompt based on configured language"""
    if Config.SUMMARY_LANGUAGE == "zh":
        return f"""请为以下学术论文生成详细的中文摘要，必须包含以下六个部分：

(1). 研究背景与动机
(2). 核心问题
(3). 方法与技术
(4). 关键结果
(5). 创新与贡献
(6). 意义与展望

论文信息:
标题: {paper.title}
作者: {', '.join(author.name for author in paper.authors)}
发表日期: {paper.published.date() if paper.published else '未知'}
链接: {paper.entry_id}

请基于以下论文内容生成摘要:
{paper_text[:12000]}..."""
    else:  # Default to English
        return f"""Please generate a detailed academic summary in English with the following six sections:

(1). Background and Motivation
(2). Core Problem
(3). Methodology
(4). Key Results
(5). Innovations and Contributions
(6). Implications and Future Work

Paper Info:
Title: {paper.title}
Authors: {', '.join(author.name for author in paper.authors)}
Date: {paper.published.date() if paper.published else 'Unknown'}
Link: {paper.entry_id}

Please generate the summary based on:
{paper_text[:12000]}..."""

def get_system_message() -> str:
    """Get system message based on configured language"""
    if Config.SUMMARY_LANGUAGE == "zh":
        return "你是一位资深学术研究员，需要用专业但易懂的中文总结论文核心内容。"
    else:
        return "You are a senior academic researcher who needs to summarize paper core content professionally but accessibly."

def generate_llm_summary(paper: arxiv.Result, paper_text: str) -> str:
    """Generate structured paper summary using LLM"""
    prompt = get_summary_prompt(paper, paper_text)
    system_message = get_system_message()
    
    try:
        delay = random.uniform(Config.MIN_API_DELAY, Config.MAX_API_DELAY)
        print(f"Waiting {delay:.1f}s before calling API for {Config.SUMMARY_LANGUAGE} summary...")
        time.sleep(delay)
        
        response = openai_client.chat.completions.create(
            model=Config.LLM_MODEL,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Failed to generate summary: {str(e)}")
        return f"Summary generation failed: {str(e)}"

def create_summary_file(topic: str, summaries: List[Dict]) -> str:
    """Create summary file and return file path"""
    output_file = get_output_filename(topic)
    with open(output_file, "w", encoding="utf-8") as f:
        # File header
        f.write("=" * 80 + "\n")
        f.write(f"ArXiv Paper Summary - {topic}\n")
        f.write(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 80 + "\n\n")
        
        # Paper details
        for i, summary in enumerate(summaries, 1):
            f.write(f"[Paper {i}]\n")
            f.write(f"Title: {summary['title']}\n")
            f.write(f"Link: {summary['url']}\n")
            f.write(f"Date: {summary['published']}\n")
            f.write(f"Authors: {summary['authors']}\n\n")
            
            f.write("=== Original Abstract ===\n")
            f.write(f"{summary['arxiv_summary']}\n\n")
            
            f.write(f"=== Generated Summary ({Config.SUMMARY_LANGUAGE.upper()}) ===\n")
            f.write(f"{summary['llm_summary']}\n")
            f.write("=" * 80 + "\n\n")
    
    return output_file

def send_summary_email(summaries: List[Dict], attachments: List[str]) -> bool:
    """Send summary email with all attachments in one message"""
    if not Config.EMAIL_ENABLED or not Config.EMAIL_RECEIVERS:
        print("Email disabled or no receivers configured")
        return False
    
    try:
        msg = MIMEMultipart()
        msg['From'] = formataddr((Config.EMAIL_DISPLAY_NAME, Config.EMAIL_SENDER))
        msg['To'] = ", ".join(Config.EMAIL_RECEIVERS)
        msg['Subject'] = f"ArXiv Paper Summary {datetime.now().strftime('%Y-%m-%d')}"
        
        # Email body content
        if Config.SUMMARY_LANGUAGE == "zh":
            email_content = f"ArXiv论文摘要 ({datetime.now().strftime('%Y-%m-%d')})\n\n"
            email_content += f"发现 {len(summaries)} 篇新论文\n\n"
        else:
            email_content = f"ArXiv Paper Summary ({datetime.now().strftime('%Y-%m-%d')})\n\n"
            email_content += f"Found {len(summaries)} new papers\n\n"
        
        for i, summary in enumerate(summaries, 1):
            email_content += f"{i}. {summary['title']}\n"
            email_content += f"Link: {summary['url']}\n"
            email_content += f"Summary ({Config.SUMMARY_LANGUAGE.upper()}):\n"
            email_content += f"{summary['llm_summary']}\n"
            email_content += "-" * 60 + "\n"
        
        msg.attach(MIMEText(email_content, 'plain', 'utf-8'))
        
        # Add all attachments
        for attachment in attachments:
            if os.path.exists(attachment):
                with open(attachment, "rb") as f:
                    part = MIMEApplication(f.read(), Name=os.path.basename(attachment))
                part['Content-Disposition'] = f'attachment; filename="{os.path.basename(attachment)}"'
                msg.attach(part)
        
        # Send with SSL
        with smtplib.SMTP_SSL(Config.SMTP_SERVER, Config.SMTP_PORT) as server:
            server.login(Config.EMAIL_SENDER, Config.EMAIL_PASSWORD)
            server.sendmail(Config.EMAIL_SENDER, Config.EMAIL_RECEIVERS, msg.as_string())
        
        print(f"Email sent successfully to {len(Config.EMAIL_RECEIVERS)} recipients")
        return True
    except smtplib.SMTPAuthenticationError:
        print("Authentication failed! Please check:")
        print("1. Using authorization code (not password)")
        print("2. SMTP service is enabled")
        print("3. Authorization code is valid")
    except Exception as e:
        print(f"Email sending failed: {str(e)}")
    return False

def process_topic(topic: str) -> Tuple[List[Dict], str]:
    """Process a single topic, return (summaries, output_file_path)"""
    print(f"\n{'=' * 40}")
    print(f"Processing topic: {topic}")
    
    papers = list(search_arxiv_papers(topic))
    new_papers = [p for p in papers if not is_paper_processed(p.get_short_id())]
    
    if not new_papers:
        print("No new papers found.")
        return [], ""
    
    print(f"\nFound {len(new_papers)} new papers, processing...")
    summaries = []
    
    for i, paper in enumerate(new_papers, 1):
        print(f"\n[Progress {i}/{len(new_papers)}] {paper.title}")
        
        try:
            result = download_pdf(paper)
            if not result:
                continue
                
            paper_text, pdf_path = result
            llm_summary = generate_llm_summary(paper, paper_text)
            
            summaries.append({
                "title": paper.title,
                "url": paper.entry_id,
                "published": str(paper.published.date()) if paper.published else "Unknown",
                "authors": ", ".join(author.name for author in paper.authors),
                "arxiv_summary": paper.summary,
                "llm_summary": llm_summary,
                "pdf_path": pdf_path
            })
            
            mark_paper_as_processed(paper.get_short_id())
            print("Paper processed successfully!")
        except Exception as e:
            print(f"Error processing paper: {str(e)}")
            continue
    
    # Save summary file
    if summaries:
        output_file = create_summary_file(topic, summaries)
        return summaries, output_file
    
    return [], ""

def main():
    """Main execution function"""
    print("Initializing database...")
    init_database()
    
    start_time = time.time()
    all_summaries = []
    all_attachments = []
    
    # Process all topics
    for topic in Config.SEARCH_TOPICS:
        topic_summaries, output_file = process_topic(topic)
        all_summaries.extend(topic_summaries)
        if output_file:
            all_attachments.append(output_file)
    
    # Send summary email (all attachments in one message)
    if all_summaries and all_attachments:
        send_summary_email(all_summaries, all_attachments)
    
    elapsed = time.time() - start_time
    print(f"\n{'=' * 40}")
    print(f"Completed all topics | Time: {elapsed:.1f}s")
    print(f"Total papers processed: {len(all_summaries)}")
    print(f"Summary files generated: {len(all_attachments)}")
    print(f"{'=' * 40}")

if __name__ == "__main__":
    main()