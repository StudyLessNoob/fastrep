from datetime import datetime
from typing import Optional


class LogEntry:
    """Represents a work log entry."""
    
    def __init__(self, id: Optional[int], project: str, description: str, 
                 date: datetime, created_at: Optional[datetime] = None):
        self.id = id
        self.project = project
        self.description = description
        self.date = date
        self.created_at = created_at or datetime.now()
    
    def to_dict(self):
        return {
            'id': self.id,
            'project': self.project,
            'description': self.description,
            'date': self.date.strftime('%Y-%m-%d'),
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }
    
    @classmethod
    def from_dict(cls, data):
        return cls(
            id=data.get('id'),
            project=data['project'],
            description=data['description'],
            date=datetime.strptime(data['date'], '%Y-%m-%d'),
            created_at=datetime.strptime(data['created_at'], '%Y-%m-%d %H:%M:%S') 
                if 'created_at' in data else None
        )
    
    def __repr__(self):
        return f"LogEntry(project='{self.project}', date='{self.date.strftime('%Y-%m-%d')}', description='{self.description[:30]}...')"