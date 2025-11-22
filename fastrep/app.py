from flask import Flask, render_template, request, jsonify, redirect, url_for
from datetime import datetime
import os
import webbrowser
import click
from threading import Timer
from .database import Database
from .models import LogEntry
from .report_generator import ReportGenerator


def create_app():
    """Create and configure Flask application."""
    app = Flask(__name__,
                template_folder=os.path.join(os.path.dirname(__file__), 'ui', 'templates'),
                static_folder=os.path.join(os.path.dirname(__file__), 'ui', 'static'))
    app.config['SECRET_KEY'] = os.urandom(24)
    
    db = Database()
    
    @app.route('/')
    def index():
        """Main page with log entry form and recent logs."""
        logs = db.get_logs()
        projects = db.get_all_projects()
        today = datetime.now().strftime('%Y-%m-%d')
        return render_template('index.html', logs=logs, projects=projects, today=today)
    
    @app.route('/add_log', methods=['POST'])
    def add_log():
        """Add a new log entry."""
        project = request.form.get('project')
        description = request.form.get('description')
        date_str = request.form.get('date')
        
        if not description:
            return jsonify({'success': False, 'error': 'Description is required'}), 400
            
        if not project:
            project = "Misc"
        
        try:
            log_date = datetime.strptime(date_str, '%Y-%m-%d') if date_str else datetime.now()
        except ValueError:
            return jsonify({'success': False, 'error': 'Invalid date format'}), 400
        
        entry = LogEntry(
            id=None,
            project=project,
            description=description,
            date=log_date
        )
        
        log_id = db.add_log(entry)
        return jsonify({'success': True, 'id': log_id, 'message': 'Log entry added successfully'})
    
    @app.route('/update_log/<int:log_id>', methods=['POST'])
    def update_log(log_id):
        """Update a log entry."""
        project = request.form.get('project')
        description = request.form.get('description')
        date_str = request.form.get('date')
        
        if not description:
            return jsonify({'success': False, 'error': 'Description is required'}), 400
            
        if not project:
            project = "Misc"
            
        try:
            log_date = datetime.strptime(date_str, '%Y-%m-%d') if date_str else datetime.now()
        except ValueError:
            return jsonify({'success': False, 'error': 'Invalid date format'}), 400
            
        if db.update_log(log_id, project, description, log_date):
            return jsonify({'success': True, 'message': 'Log entry updated'})
        else:
            return jsonify({'success': False, 'error': 'Log entry not found'}), 404

    @app.route('/delete_log/<int:log_id>', methods=['POST'])
    def delete_log(log_id):
        """Delete a log entry."""
        if db.delete_log(log_id):
            return jsonify({'success': True, 'message': 'Log entry deleted'})
        else:
            return jsonify({'success': False, 'error': 'Log entry not found'}), 404
    
    @app.route('/report/<mode>')
    def report(mode):
        """Generate and display a report."""
        if mode not in ['weekly', 'biweekly', 'monthly']:
            return "Invalid report mode", 400
        
        start_date, end_date = ReportGenerator.get_date_range(mode)
        logs = db.get_logs(start_date, end_date)
        report_html = ReportGenerator.format_report_html(logs, mode)
        report_text = ReportGenerator.format_report(logs, mode)
        
        return render_template('index.html', 
                             logs=db.get_logs(), 
                             projects=db.get_all_projects(),
                             report=report_html,
                             report_text=report_text,
                             report_mode=mode)
    
    @app.route('/settings')
    def settings():
        """Settings page."""
        return render_template('settings.html')
    
    @app.route('/clear_all', methods=['POST'])
    def clear_all():
        """Clear all log entries."""
        db.clear_all()
        return jsonify({'success': True, 'message': 'All log entries cleared'})
    
    @app.route('/api/logs')
    def get_logs_api():
        """API endpoint to get logs as JSON."""
        logs = db.get_logs()
        return jsonify([log.to_dict() for log in logs])
    
    return app


def open_browser(port=5000):
    """Open browser after a short delay."""
    url = f'http://127.0.0.1:{port}'
    
    # Try to open in app mode if possible (Chrome/Chromium)
    try:
        # Common browser commands with app mode argument
        browser_commands = [
            ['google-chrome', '--app=' + url],
            ['chromium-browser', '--app=' + url],
            ['chromium', '--app=' + url],
            ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '--app=' + url]
        ]
        
        import subprocess
        for cmd in browser_commands:
            try:
                # Check if executable exists (except for mac app path)
                if cmd[0].startswith('/') and os.path.exists(cmd[0]):
                    subprocess.Popen(cmd)
                    return
                
                # For commands in path, this check is harder without 'which', 
                # so we just try to execute and catch exception
                if not cmd[0].startswith('/'):
                    subprocess.Popen(cmd)
                    return
            except FileNotFoundError:
                continue
            except Exception:
                continue
                
    except Exception:
        pass
        
    # Fallback to default browser
    webbrowser.open(url)


@click.command()
@click.option('--port', '-p', default=5000, help='Port to run the server on')
def main(port):
    """Main entry point for fastrep-ui command."""
    app = create_app()
    
    print("=" * 60)
    print("FastRep Web UI Starting...")
    print("=" * 60)
    print(f"\n🚀 Access the web interface at: http://127.0.0.1:{port}")
    print("\n📝 Features:")
    print("  • Add and manage work logs")
    print("  • Generate weekly, bi-weekly, and monthly reports")
    print("  • View and delete entries")
    print("\n⌨️  Press CTRL+C to stop the server\n")
    print("=" * 60)
    
    # Open browser after 1.5 seconds
    Timer(1.5, open_browser, args=[port]).start()
    
    app.run(debug=False, port=port, host='127.0.0.1')


if __name__ == '__main__':
    main()
