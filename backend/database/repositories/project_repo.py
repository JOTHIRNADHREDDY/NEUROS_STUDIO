from sqlalchemy.orm import Session
from ..models.models import ProjectModel

class ProjectRepository:
    def __init__(self, db: Session):
        self.db = db
        
    def create_project(self, name: str, path: str, board: str = None) -> ProjectModel:
        db_project = ProjectModel(name=name, path=path, board=board)
        self.db.add(db_project)
        self.db.commit()
        self.db.refresh(db_project)
        return db_project
        
    def get_project_by_path(self, path: str) -> ProjectModel:
        return self.db.query(ProjectModel).filter(ProjectModel.path == path).first()
        
    def list_projects(self):
        return self.db.query(ProjectModel).all()
