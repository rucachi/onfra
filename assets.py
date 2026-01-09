"""
로고 및 자산 관리 모듈
회사 로고 로딩 및 에러 처리
"""
import logging
from pathlib import Path
from typing import Optional

from PySide6.QtGui import QPixmap

# 로고 파일 경로 (고정)
LOGO_PATH = r"C:\onfra\onfra_logo.png"

logger = logging.getLogger(__name__)


def load_logo_pixmap() -> Optional[QPixmap]:
    """
    회사 로고를 QPixmap으로 로드합니다.
    
    Returns:
        QPixmap: 로고가 성공적으로 로드된 경우
        None: 로드 실패 시 (파일 없음, 권한 문제 등)
    """
    logo_path = Path(LOGO_PATH)
    
    try:
        if not logo_path.exists():
            logger.warning(f"로고 파일이 존재하지 않습니다: {LOGO_PATH}")
            return None
        
        if not logo_path.is_file():
            logger.warning(f"로고 경로가 파일이 아닙니다: {LOGO_PATH}")
            return None
        
        pixmap = QPixmap(LOGO_PATH)
        
        if pixmap.isNull():
            logger.error(f"로고 이미지 로드 실패 (손상된 파일일 수 있음): {LOGO_PATH}")
            return None
        
        logger.info(f"로고 로드 성공: {LOGO_PATH} ({pixmap.width()}x{pixmap.height()})")
        return pixmap
        
    except PermissionError:
        logger.error(f"로고 파일 접근 권한 없음: {LOGO_PATH}")
        return None
    except Exception as e:
        logger.error(f"로고 로드 중 예외 발생: {e}")
        return None


def get_logo_error_message() -> str:
    """
    로고 로드 실패 시 표시할 에러 메시지를 반환합니다.
    
    Returns:
        str: 에러 메시지
    """
    return f"로고 로드 실패: {LOGO_PATH}"
