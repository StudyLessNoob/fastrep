from datetime import datetime, timedelta
from typing import List
from collections import defaultdict
import subprocess
import tempfile
import os
import logging
import time
from .models import LogEntry

logger = logging.getLogger(__name__)

class ReportGenerator:
    """Generate formatted reports from log entries."""
    
    @staticmethod
    def get_date_range(mode: str) -> tuple:
        """Get start and end dates based on report mode."""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        if mode == 'weekly':
            start_date = today - timedelta(days=6)
            end_date = today
        elif mode == 'biweekly':
            start_date = today - timedelta(days=13)
            end_date = today
        elif mode == 'monthly':
            start_date = today - timedelta(days=30)
            end_date = today
        else:
            raise ValueError(f"Unknown report mode: {mode}")
        
        return start_date, end_date
    
    @staticmethod
    def group_by_project(logs: List[LogEntry]) -> dict:
        """Group logs by project."""
        grouped = defaultdict(list)
        for log in logs:
            grouped[log.project].append(log)
        
        # Sort each project's logs by date (descending)
        for project in grouped:
            grouped[project].sort(key=lambda x: x.date, reverse=True)
        
        return dict(grouped)
    
    @staticmethod
    def summarize_project_logs(project: str, logs: List[LogEntry], verbosity: int = 0, summary_points: str = "3-5", timeout: int = 120) -> List[str]:
        """Summarize logs using cline CLI."""
        # Create a temporary file in .fastrep/temp to avoid permission issues
        temp_dir = os.path.join(os.path.expanduser("~"), ".fastrep", "temp")
        os.makedirs(temp_dir, exist_ok=True)
        output_file = os.path.join(temp_dir, f"summary_{project.replace(' ', '_')}_{int(time.time())}.txt")
            
        logs_text = "\n".join([f"- {log.date.strftime('%Y-%m-%d')}: {log.description}" for log in logs])
        
        prompt = (
            f"Summarize the following work logs for project '{project}' into {summary_points} concise bullet points. "
            f"Focus on key achievements and tasks. "
            f"Each bullet point MUST include the relevant date or date range (e.g., '11/15 - Implemented X' or '11/15-11/17 - Fixed Y'). "
            f"Ensure the text is grammatically correct and professional. "
            f"Write ONLY the bullet points to the file '{output_file}'. "
            f"Do not include any other text or conversation.\n\n"
            f"Logs:\n{logs_text}"
        )
        
        logger.info(f"Summarizing project: {project} (Points: {summary_points}, Timeout: {timeout}s)")
        logger.debug(f"Prompt:\n{prompt}")
        
        try:
            # Call cline CLI
            # Use stdin=subprocess.DEVNULL to prevent hanging on interactive prompts
            result = subprocess.run(['cline', prompt, '--yolo', '--mode', 'act'], 
                         check=True, 
                         capture_output=True,
                         text=True,
                         stdin=subprocess.DEVNULL,
                         timeout=timeout)
            
            logger.debug(f"CLI Output:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}")
            
            # Read result
            with open(output_file, 'r') as f:
                summary = f.read().strip()
                
            if summary:
                logger.info(f"Summary obtained ({len(summary)} chars)")
                logger.debug(f"Summary Content:\n{summary}")
                return summary.split('\n')
            else:
                logger.warning("Summary file was empty")
                    
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout summarizing logs for {project} ({timeout}s)")
        except Exception as e:
            logger.error(f"Error summarizing logs for {project}: {e}", exc_info=True)
            
        finally:
            if os.path.exists(output_file):
                os.remove(output_file)
                
        # Fallback if summarization fails: Return up to 10 recent logs
        logger.info(f"Falling back to recent logs (max 10) for {project}")
        
        recent_logs = logs[:10]
        formatted_logs = [f"{log.date.strftime('%m/%d')} - {log.description}" for log in recent_logs]
        
        if len(logs) > 10:
            formatted_logs.append(f"... and {len(logs) - 10} more entries.")
            
        return formatted_logs

    @staticmethod
    def generate_summaries(logs: List[LogEntry], mode: str, summarize: bool, verbosity: int = 0, summary_points: str = "3-5", timeout: int = 120) -> dict:
        """Generate AI summaries for projects if needed."""
        if not summarize or mode != 'monthly':
            return {}
            
        grouped = ReportGenerator.group_by_project(logs)
        summaries = {}
        
        # Process sequentially to avoid Rate Limits (429)
        for project, project_logs in grouped.items():
            if len(project_logs) > 5:
                logger.info(f"Processing summary for: {project}")
                try:
                    result = ReportGenerator.summarize_project_logs(
                        project, project_logs, verbosity, summary_points, timeout
                    )
                    summaries[project] = result
                    # Small delay to be nice to the API
                    time.sleep(2)
                except Exception as e:
                    logger.error(f"Failed to summarize {project}: {e}")
                    
        return summaries

    @staticmethod
    def improve_report_text(report_text: str, verbosity: int = 0) -> str:
        """Improve the grammar and tone of the full report text."""
        # Create a temporary file for output
        temp_dir = os.path.join(os.path.expanduser("~"), ".fastrep", "temp")
        os.makedirs(temp_dir, exist_ok=True)
        output_file = os.path.join(temp_dir, f"improved_report_{int(time.time())}.txt")
            
        prompt = (
            f"Review and improve the following work report. "
            f"Ensure correct grammar, professional tone, and consistency. "
            f"Do NOT remove any information, dates, or projects. "
            f"Write the improved report to the file '{output_file}'. "
            f"Do not include any other text or conversation.\n\n"
            f"Report:\n{report_text}"
        )
        
        logger.info("Improving full report text")
        logger.debug(f"Improvement Prompt:\n{prompt}")
        
        try:
            result = subprocess.run(['cline', prompt, '--yolo', '--mode', 'act'], 
                         check=True, 
                         capture_output=True,
                         text=True,
                         stdin=subprocess.DEVNULL,
                         timeout=120)
            
            logger.debug(f"CLI Output:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}")
            
            with open(output_file, 'r') as f:
                improved_text = f.read().strip()
                
            if improved_text:
                logger.info("Report improved successfully")
                return improved_text
                
        except Exception as e:
            logger.error(f"Error improving report: {e}", exc_info=True)
                
        finally:
            if os.path.exists(output_file):
                os.remove(output_file)
                
        return report_text

    @staticmethod
    def format_report(logs: List[LogEntry], mode: str = None, summaries: dict = None, verbosity: int = 0) -> str:
        """Format logs into a readable report."""
        if not logs:
            return "No logs found for this period."
        
        grouped = ReportGenerator.group_by_project(logs)
        summaries = summaries or {}
        
        report_lines = []
        
        if mode:
            start_date, end_date = ReportGenerator.get_date_range(mode)
            report_lines.append(f"Report Period: {start_date.strftime('%m/%d')} - {end_date.strftime('%m/%d')}")
            report_lines.append("=" * 60)
            report_lines.append("")
        
        for project in sorted(grouped.keys()):
            report_lines.append(f"Project: {project}")
            report_lines.append("-" * 60)
            
            project_logs = grouped[project]
            
            if project in summaries:
                report_lines.append("(AI Summary)")
                for line in summaries[project]:
                    report_lines.append(f"  {line}")
            else:
                # If summarized but no summary (fallback) or normal
                # Check if we should fallback (e.g. > 5 logs but no summary)
                # But generate_summaries handles the decision. 
                # If key missing, print normally or fallback.
                # If user wanted summary but failed, generate_summaries returns empty for that project?
                # Let's assume if >10 logs and no summary, fallback logic applies here too?
                # No, let's keep it simple: if in summaries dict, use it. Else raw.
                # If generate_summaries failed, it didn't add to dict.
                # We should probably implement the fallback here: if > 5 logs and mode==monthly and no summary, slice.
                # But `summaries` is the source of truth for "AI content".
                # I'll stick to raw logs if no summary.
                # Wait, user wanted fallback to 10 logs if AI fails.
                # I'll just show all logs or slice to 10 if it looks like it was supposed to be summarized?
                # Actually, `format_report` doesn't know if it *failed*.
                # Let's just show logs.
                
                # Wait, if I want consistent behavior with previous step:
                # I should probably slice if > 10 logs regardless?
                # No, user only said fallback if AI times out.
                
                for log in project_logs:
                    date_str = log.date.strftime('%m/%d')
                    report_lines.append(f"  * {date_str} - {log.description}")
            
            report_lines.append("")
        
        final_text = "\n".join(report_lines)
        
        if summaries:
            return ReportGenerator.improve_report_text(final_text, verbosity)
            
        return final_text
    
    @staticmethod
    def format_report_html(logs: List[LogEntry], mode: str = None, summaries: dict = None) -> str:
        """Format logs into HTML report."""
        if not logs:
            return "<p>No logs found for this period.</p>"
        
        grouped = ReportGenerator.group_by_project(logs)
        summaries = summaries or {}
        
        html_parts = []
        
        if mode:
            start_date, end_date = ReportGenerator.get_date_range(mode)
            html_parts.append(f"<p><strong>Report Period:</strong> {start_date.strftime('%m/%d')} - {end_date.strftime('%m/%d')}</p>")
        
        for project in sorted(grouped.keys()):
            html_parts.append(f"<h4>{project}</h4>")
            
            project_logs = grouped[project]
            
            if project in summaries:
                html_parts.append("<p><em>(AI Summary)</em></p>")
                html_parts.append("<ul>")
                for line in summaries[project]:
                    line = line.lstrip('-*• ')
                    html_parts.append(f"<li>{line}</li>")
                html_parts.append("</ul>")
            else:
                html_parts.append("<ul>")
                for log in project_logs:
                    date_str = log.date.strftime('%m/%d')
                    html_parts.append(f"<li><strong>{date_str}</strong> - {log.description}</li>")
                html_parts.append("</ul>")
        
        return "".join(html_parts)
