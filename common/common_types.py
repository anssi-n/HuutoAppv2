from enum import StrEnum

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