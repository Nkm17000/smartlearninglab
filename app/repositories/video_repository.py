from app.repositories.base import Repository
class VideoRepository(Repository):
    def __init__(self):
        super().__init__("videos")
