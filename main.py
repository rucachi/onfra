"""
ONFRA Camera Tracking System
메인 진입점
"""
import sys
import logging
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from ui.main_window import MainWindow


def setup_logging():
    """로깅 설정"""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    log_file = log_dir / "tracking_app.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("ONFRA Camera Tracking System 시작")
    logger.info("=" * 60)


def main():
    """메인 함수"""
    # 로깅 설정
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        # High DPI 스케일링 활성화 (Qt6에서는 기본 활성화이지만 명시적 설정)
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
        
        # Qt 애플리케이션 생성
        app = QApplication(sys.argv)
        app.setApplicationName("ONFRA Camera Tracking System")
        app.setOrganizationName("ONFRA")
        
        # 화면 정보 가져오기
        screen = app.primaryScreen()
        screen_geometry = screen.availableGeometry()
        screen_width = screen_geometry.width()
        screen_height = screen_geometry.height()
        
        logger.info(f"화면 크기: {screen_width}x{screen_height}")
        logger.info(f"DPI: {screen.logicalDotsPerInch()}")
        
        # 메인 윈도우 생성
        window = MainWindow()
        
        # 화면 크기에 따른 윈도우 크기 조정 (화면의 80% 사용)
        window_width = int(screen_width * 0.8)
        window_height = int(screen_height * 0.85)
        
        # 최소/최대 크기 제한
        window_width = max(1000, min(window_width, 1800))
        window_height = max(700, min(window_height, 1200))
        
        window.resize(window_width, window_height)
        
        # 화면 중앙에 위치
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        window.move(x, y)
        
        window.show()
        
        logger.info(f"메인 윈도우 표시 완료 ({window_width}x{window_height})")
        
        # 이벤트 루프 실행
        exit_code = app.exec()
        
        logger.info(f"애플리케이션 종료 (exit code: {exit_code})")
        return exit_code
        
    except Exception as e:
        logger.critical(f"치명적 오류 발생: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
