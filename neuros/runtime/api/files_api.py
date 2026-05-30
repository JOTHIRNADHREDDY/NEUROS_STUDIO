import logging
import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, status

logger = logging.getLogger("neuros.api.files")
router = APIRouter()
folders_router = APIRouter()

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
PROTECTED_PATHS = {
    Path("package.json"),
    Path("next.config.ts"),
    Path("tsconfig.json"),
    Path("app/layout.tsx"),
    Path("app/page.tsx"),
    Path("app/globals.css"),
}


def _resolve_target(path_value: str) -> Path:
    if not path_value or path_value in {"/", "."}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Workspace root cannot be deleted.")

    normalized = Path(path_value.strip().replace("\\", "/"))
    if normalized.is_absolute():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Absolute paths are not allowed.")

    target = (WORKSPACE_ROOT / normalized).resolve()
    if target == WORKSPACE_ROOT or WORKSPACE_ROOT not in target.parents:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Path is outside the workspace.")

    relative = target.relative_to(WORKSPACE_ROOT)
    if relative in PROTECTED_PATHS or any(parent in PROTECTED_PATHS for parent in relative.parents):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Path is protected and cannot be deleted.")

    return target


async def _delete_path(path: str, expected_kind: str | None = None):
    target = _resolve_target(path)

    if not target.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File or folder not found.")

    is_directory = target.is_dir()
    if expected_kind == "file" and is_directory:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Use /api/folders to delete folders.")
    if expected_kind == "folder" and not is_directory:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Use /api/files to delete files.")

    try:
        if is_directory:
            shutil.rmtree(target)
        else:
            target.unlink()
    except OSError as error:
        logger.exception("Failed to delete workspace path %s", target)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(error)) from error

    return {
        "status": "deleted",
        "path": str(target.relative_to(WORKSPACE_ROOT)).replace("\\", "/"),
        "kind": "directory" if is_directory else "file",
    }


@router.delete("/{path:path}")
async def delete_file(path: str, request: Request):
    del request
    return await _delete_path(path, "file")


@folders_router.delete("/{path:path}")
async def delete_folder(path: str, request: Request):
    del request
    return await _delete_path(path, "folder")
