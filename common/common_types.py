from enum import StrEnum
from typing import Literal

ImageType = Literal["fullsize", "preview"]
ImagePhase = Literal["initial", "update"]

class UserRole(StrEnum):
    user = "user"
    admin = "admin"
    
class TaskType(StrEnum):
    AddItem = "AddItem"
    CloseItem = "CloseItem"
    RelistItem = "RelistItem"
    UpdateItem = "UpdateItem"
    RelistAllItems = "RelistAllItems"
    AddImage = "AddImage"
    DeleteImage = "DeleteImage"

class TaskStatus(StrEnum):
    ongoing = "ongoing"
    success = "success"
    fail = "fail"