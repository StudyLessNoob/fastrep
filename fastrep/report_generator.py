from datetime import datetime, timedelta
from typing import List
from collections import defaultdict
import subprocess
import tempfile
import os
import logging
import time
from .models import LogEntry
from .llm import get_llm_client

logger = logging.getLogger(__name__)

class ReportGenerator:
    """Generate formatted reports from log entries."""

    TEMPLATES = {
        'classic': {
            'name': 'Classic',
            'description': 'Standard format with date range header.',
            'date_format': '%m/%d',
            'show_header': True,
            'html_item': '<li><strong>{date}</strong> - {description}</li>',
            'text_item': '  * {date} - {description}'
        },
        'classic_clean': {
            'name': 'Classic (No Header)',
            'description': 'Standard format without date range header.',
            'date_format': '%m/%d',
            'show_header': False,
            'html_item': '<li><strong>{date}</strong> - {description}</li>',
            'text_item': '  * {date} - {description}'
        },
        'bold': {
            'name': 'Bold Dates',
            'description': 'Dates bolded at start.',
            'date_format': '%Y-%m-%d',
            'show_header': True,
            'html_item': '<li><b style="color:var(--primary-color)">{date}</b>: {description}</li>',
            'text_item': '  * **{date}**: {description}'
        },
        'modern': {
            'name': 'Modern',
            'description': 'Description first, italic date at end.',
            'date_format': '%b %d',
            'show_header': True,
            'html_item': '<li>{description} <em style="color:var(--text-secondary)">({date})</em></li>',
            'text_item': '  * {description} ({date})'
        },
        'professional': {
            'name': 'Professional',
            'description': 'Detailed date badges.',
            'date_format': '%A, %B %d',
            'show_header': True,
            'html_item': '<li><span class="badge" style="background:#64748b">{date}</span> {description}</li>',
            'text_item': '  * [{date}] {description}'
        },
        'professional_clean': {
            'name': 'Professional (No Header)',
            'description': 'Detailed badges without range header.',
            'date_format': '%A, %B %d',
            'show_header': False,
            'html_item': '<li><span class="badge" style="background:#64748b">{date}</span> {description}</li>',
            'text_item': '  * [{date}] {description}'
        },
        'compact': {
            'name': 'Compact',
            'description': 'Minimalist layout.',
            'date_format': '%m/%d',
            'show_header': False,
            'html_item': '<li><small style="color:var(--text-secondary)">{date}</small> {description}</li>',
            'text_item': '  - {date} {description}'
        }
    }
    
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
    def summarize_project_logs(project: str, logs: List[LogEntry], verbosity: int = 0, summary_points: str = "3-5", timeout: int = 120, provider_config: dict = None) -> List[str]:
        """Summarize logs using configured AI provider or cline CLI fallback."""
        logs_text = "\n".join([f"- {log.date.strftime('%Y-%m-%d')}: {log.description}" for log in logs])
        
        system_prompt = "You are a professional project manager assisting with work log summarization."
        prompt_content = (
            f"Summarize the following work logs for project '{project}' into {summary_points} concise bullet points. "
            f"Focus on key achievements and tasks. "
            f"Each bullet point MUST include the relevant date or date range (e.g., '11/15 - Implemented X' or '11/15-11/17 - Fixed Y'). "
            f"Ensure the text is grammatically correct and professional. "
            f"Return ONLY the bullet points, one per line."
        )
        full_prompt = f"{prompt_content}\n\nLogs:\n{logs_text}"
        
        logger.info(f"Summarizing project: {project} (Points: {summary_points}, Timeout: {timeout}s)")
        
        # Try Direct Provider First
        if provider_config and provider_config.get('api_key'):
            try:
                client = get_llm_client(
                    provider_config['provider'], 
                    provider_config['api_key'], 
                    provider_config['model'], 
                    provider_config['base_url']
                )
                if client:
                    summary = client.generate(full_prompt, system_prompt)
                    if summary:
                        logger.info(f"Summary obtained via {provider_config['provider']} ({len(summary)} chars)")
                        return summary.strip().split('\n')
            except Exception as e:
                logger.error(f"Provider {provider_config['provider']} failed: {e}")
                # Fallthrough to CLI fallback

        # Fallback to Cline CLI
        # Create a temporary file in .fastrep/temp to avoid permission issues
        temp_dir = os.path.join(os.path.expanduser("~"), ".fastrep", "temp")
        os.makedirs(temp_dir, exist_ok=True)
        output_file = os.path.join(temp_dir, f"summary_{project.replace(' ', '_')}_{int(time.time())}.txt")
            
        cli_prompt = (
            f"{prompt_content} "
            f"Write ONLY the bullet points to the file '{output_file}'. "
            f"Do not include any other text or conversation.\n\n"
            f"Logs:\n{logs_text}"
        )
        
        try:
            # Call cline CLI
            # Use stdin=subprocess.DEVNULL to prevent hanging on interactive prompts
            result = subprocess.run(['cline', cli_prompt, '--yolo', '--mode', 'act'], 
                         check=True, 
                         capture_output=True,
                         text=True,
                         stdin=subprocess.DEVNULL,
                         timeout=timeout)
            
            logger.debug(f"CLI Output:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}")
            
            # Read result
            if os.path.exists(output_file):
                with open(output_file, 'r') as f:
                    summary = f.read().strip()
                
                if summary:
                    logger.info(f"Summary obtained via CLI ({len(summary)} chars)")
                    return summary.split('\n')
            
            logger.warning("Summary file was empty or not created")
                    
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
    def generate_summaries(logs: List[LogEntry], mode: str, summarize: bool, verbosity: int = 0, summary_points: str = "3-5", timeout: int = 120, provider_config: dict = None, threshold: int = 5) -> dict:
        """Generate AI summaries for projects if needed."""
        if not summarize:
            return {}
            
        grouped = ReportGenerator.group_by_project(logs)
        projects_to_summarize = {p: l for p, l in grouped.items() if len(l) > threshold}
        
        if not projects_to_summarize:
            return {}

        # Construct a single prompt for all projects
        prompt_intro = (
            f"Summarize the work logs for the following {len(projects_to_summarize)} projects. "
            f"For EACH project, provide {summary_points} concise bullet points focusing on key achievements. "
            f"Each bullet point MUST include a specific date or date range. "
            f"Ensure professional tone and grammar. "
            f"IMPORTANT: Return the output as a valid JSON object where keys are Project names and values are LISTS OF OBJECTS. "
            f"Each object must have two keys: 'date' (string, e.g. '11/15' or '10/01-10/05') and 'description' (string). "
            f"Do not include markdown formatting like ```json."
        )
        
        prompt_logs = ""
        for project, p_logs in projects_to_summarize.items():
            prompt_logs += f"\nProject: {project}\n"
            prompt_logs += "\n".join([f"- {log.date.strftime('%Y-%m-%d')}: {log.description}" for log in p_logs])
            prompt_logs += "\n"
            
        full_prompt = f"{prompt_intro}\n\nData:\n{prompt_logs}"
        
        logger.info(f"Generating summaries for {len(projects_to_summarize)} projects in a single call")
        
        response_text = ""
        
        # Try Direct Provider
        if provider_config and provider_config.get('api_key'):
            try:
                client = get_llm_client(
                    provider_config['provider'], 
                    provider_config['api_key'], 
                    provider_config['model'], 
                    provider_config['base_url']
                )
                if client:
                    response_text = client.generate(full_prompt, "You are a precise JSON generator.")
            except Exception as e:
                logger.error(f"Provider summarization failed: {e}")

        # Fallback to Cline CLI
        if not response_text:
            temp_dir = os.path.join(os.path.expanduser("~"), ".fastrep", "temp")
            os.makedirs(temp_dir, exist_ok=True)
            output_file = os.path.join(temp_dir, f"summary_all_{int(time.time())}.json")
            
            cli_prompt = f"{full_prompt}\n\nWrite the JSON to '{output_file}'. No other text."
            
            try:
                subprocess.run(['cline', cli_prompt, '--yolo', '--mode', 'act'], 
                            check=True, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=timeout*2) # More time for big batch
                
                if os.path.exists(output_file):
                    with open(output_file, 'r') as f:
                        response_text = f.read().strip()
                    os.remove(output_file)
            except Exception as e:
                logger.error(f"CLI summarization failed: {e}")

        # Parse JSON
        try:
            if response_text:
                # Clean potential markdown
                response_text = response_text.replace("```json", "").replace("```", "").strip()
                import json
                return json.loads(response_text)
        except Exception as e:
            logger.error(f"Failed to parse summary JSON: {e}\nResponse: {response_text}")
            
        return {}

    @staticmethod
    def improve_report_text(report_text: str, verbosity: int = 0, custom_instructions: str = "", provider_config: dict = None, timeout: int = 120) -> str:
        """Improve the grammar and tone of the full report text."""
        instruction = (
            "Review and improve the following work report. "
            "Ensure correct grammar, professional tone, and consistency. "
            "Do NOT remove any information, dates, or projects. "
        )
        
        if custom_instructions:
            instruction += f"\n\nAdditional Custom Instructions: {custom_instructions}"
            
        prompt_content = f"{instruction}\n\nReport:\n{report_text}"
        
        logger.info("Improving full report text")
        
        # Try Direct Provider First
        if provider_config and provider_config.get('api_key'):
            try:
                client = get_llm_client(
                    provider_config['provider'], 
                    provider_config['api_key'], 
                    provider_config['model'], 
                    provider_config['base_url']
                )
                if client:
                    improved = client.generate(prompt_content, "You are a helpful editor.")
                    if improved:
                        logger.info("Report improved successfully via Provider")
                        return improved.strip()
            except Exception as e:
                logger.error(f"Provider improvement failed: {e}")

        # Fallback to Cline CLI
        temp_dir = os.path.join(os.path.expanduser("~"), ".fastrep", "temp")
        os.makedirs(temp_dir, exist_ok=True)
        output_file = os.path.join(temp_dir, f"improved_report_{int(time.time())}.txt")
        
        cli_prompt = (
            f"{instruction}\n"
            f"Write the improved report to the file '{output_file}'. "
            f"Do not include any other text or conversation.\n\n"
            f"Report:\n{report_text}"
        )
        
        try:
            result = subprocess.run(['cline', cli_prompt, '--yolo', '--mode', 'act'], 
                         check=True, 
                         capture_output=True,
                         text=True,
                         stdin=subprocess.DEVNULL,
                         timeout=timeout)
            
            logger.debug(f"CLI Output:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}")
            
            if os.path.exists(output_file):
                with open(output_file, 'r') as f:
                    improved_text = f.read().strip()
                
                if improved_text:
                    logger.info("Report improved successfully via CLI")
                    return improved_text
                
        except Exception as e:
            logger.error(f"Error improving report via CLI: {e}", exc_info=True)
                
        finally:
            if os.path.exists(output_file):
                os.remove(output_file)
                
        return report_text

    @staticmethod
    def format_report(logs: List[LogEntry], mode: str = None, summaries: dict = None, verbosity: int = 0, custom_instructions: str = "", template_name: str = 'classic', provider_config: dict = None, timeout: int = 120) -> str:
        """Format logs into a readable report."""
        if not logs:
            return "No logs found for this period."
        
        grouped = ReportGenerator.group_by_project(logs)
        summaries = summaries or {}
        template = ReportGenerator.TEMPLATES.get(template_name, ReportGenerator.TEMPLATES['classic'])
        
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
                for item in summaries[project]:
                    if isinstance(item, dict) and 'date' in item and 'description' in item:
                        formatted_line = template['text_item'].format(date=item['date'], description=item['description'])
                        report_lines.append(formatted_line)
                    else:
                        report_lines.append(f"  * {str(item)}")
            else:
                for log in project_logs:
                    date_str = log.date.strftime(template['date_format'])
                    # report_lines.append(f"  * {date_str} - {log.description}")
                    # Use template format
                    formatted_line = template['text_item'].format(date=date_str, description=log.description)
                    report_lines.append(formatted_line)
            
            report_lines.append("")
        
        final_text = "\n".join(report_lines)
        
        if summaries:
            return ReportGenerator.improve_report_text(final_text, verbosity, custom_instructions, provider_config, timeout)
            
        return final_text
    
    @staticmethod
    def format_report_html(logs: List[LogEntry], mode: str = None, summaries: dict = None, template_name: str = 'classic') -> str:
        """Format logs into HTML report."""
        if not logs:
            return "<p>No logs found for this period.</p>"
        
        grouped = ReportGenerator.group_by_project(logs)
        summaries = summaries or {}
        template = ReportGenerator.TEMPLATES.get(template_name, ReportGenerator.TEMPLATES['classic'])
        
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
                for item in summaries[project]:
                    if isinstance(item, dict) and 'date' in item and 'description' in item:
                        formatted_line = template['html_item'].format(date=item['date'], description=item['description'])
                        html_parts.append(formatted_line)
                    else:
                        line = str(item).lstrip('-*• ')
                        html_parts.append(f"<li>{line}</li>")
                html_parts.append("</ul>")
            else:
                html_parts.append("<ul>")
                for log in project_logs:
                    date_str = log.date.strftime(template['date_format'])
                    # html_parts.append(f"<li><strong>{date_str}</strong> - {log.description}</li>")
                    # Use template format
                    formatted_line = template['html_item'].format(date=date_str, description=log.description)
                    html_parts.append(formatted_line)
                html_parts.append("</ul>")
        
        return "".join(html_parts)
