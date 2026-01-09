"""
메인 윈도우
좌측 네비게이션 + 페이지 스택 + 로고 표시
- 개선된 UI
"""
import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap, QFont
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QPushButton, QLabel, QStatusBar, QFrame
)

from assets import load_logo_pixmap, get_logo_error_message, LOGO_PATH

logger = logging.getLogger(__name__)


class NavButton(QPushButton):
    """네비게이션 버튼"""
    
    def __init__(self, icon: str, text: str, parent=None):
        super().__init__(f"{icon}  {text}", parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self._update_style(False)
    
    def _update_style(self, selected: bool):
        if selected:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #3498db;
                    color: white;
                    text-align: left;
                    padding: 16px 20px;
                    border: none;
                    border-left: 4px solid #2980b9;
                    font-size: 14px;
                    font-weight: bold;
                }
                QPushButton:pressed {
                    background-color: #1f618d;
                    padding-top: 18px;
                    padding-bottom: 14px;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #bdc3c7;
                    text-align: left;
                    padding: 16px 20px;
                    border: none;
                    border-left: 4px solid transparent;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: #34495e;
                    color: #ecf0f1;
                }
                QPushButton:pressed {
                    background-color: #2c3e50;
                    color: #ffffff;
                    padding-top: 18px;
                    padding-bottom: 14px;
                }
            """)
    
    def setSelected(self, selected: bool):
        self.setChecked(selected)
        self._update_style(selected)


class MainWindow(QMainWindow):
    """메인 윈도우"""
    
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("ONFRA Camera Tracking System")
        self.setMinimumSize(1000, 700)
        
        # 로고 로드
        self.logo_pixmap = load_logo_pixmap()
        self._setup_window_icon()
        
        # UI 구성
        self._setup_ui()
        
        # 상태바
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("""
            QStatusBar {
                background-color: #2c3e50;
                color: #ecf0f1;
                padding: 5px;
                font-size: 12px;
            }
        """)
        self.setStatusBar(self.status_bar)
        
        if self.logo_pixmap is None:
            self.status_bar.showMessage(f"⚠ {get_logo_error_message()}", 10000)
        else:
            self.status_bar.showMessage("✅ 준비 완료 - Camera Settings에서 카메라를 연결하세요", 5000)
    
    def _setup_window_icon(self):
        """윈도우 아이콘 설정"""
        try:
            if self.logo_pixmap is not None:
                icon = QIcon(self.logo_pixmap)
                self.setWindowIcon(icon)
                logger.info("윈도우 아이콘 설정 완료")
            else:
                icon = QIcon(LOGO_PATH)
                if not icon.isNull():
                    self.setWindowIcon(icon)
        except Exception as e:
            logger.warning(f"윈도우 아이콘 설정 실패: {e}")
    
    def _setup_ui(self):
        """UI 구성"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 좌측 사이드바
        sidebar = self._create_sidebar()
        main_layout.addWidget(sidebar)
        
        # 우측 페이지 스택
        self.page_stack = QStackedWidget()
        self.page_stack.setStyleSheet("background-color: #ecf0f1;")
        main_layout.addWidget(self.page_stack, stretch=1)
        
        # 페이지 추가
        from ui.pages_camera import CameraSettingsPage
        from ui.pages_training import TrainingPage
        from ui.pages_observation import ObservationPage
        
        self.camera_page = CameraSettingsPage()
        self.training_page = TrainingPage()
        self.observation_page = ObservationPage()
        
        self.page_stack.addWidget(self.camera_page)
        self.page_stack.addWidget(self.training_page)
        self.page_stack.addWidget(self.observation_page)
        
        # 초기 페이지
        self._navigate_to(0)
    
    def _create_sidebar(self) -> QWidget:
        """좌측 사이드바 생성"""
        sidebar = QFrame()
        sidebar.setFrameShape(QFrame.StyledPanel)
        sidebar.setFixedWidth(260)
        sidebar.setStyleSheet("""
            QFrame {
                background-color: #2c3e50;
            }
        """)
        
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 로고 영역
        logo_widget = self._create_logo_widget()
        layout.addWidget(logo_widget)
        
        # 구분선
        separator = QFrame()
        separator.setFixedHeight(2)
        separator.setStyleSheet("background-color: #34495e;")
        layout.addWidget(separator)
        
        # 메뉴 제목
        menu_title = QLabel("  메뉴")
        menu_title.setStyleSheet("""
            color: #7f8c8d;
            font-size: 11px;
            font-weight: bold;
            padding: 15px 20px 5px 20px;
            text-transform: uppercase;
            letter-spacing: 1px;
        """)
        layout.addWidget(menu_title)
        
        # 네비게이션 버튼
        self.btn_camera = NavButton("📷", "Camera Settings")
        self.btn_camera.clicked.connect(lambda: self._navigate_to(0))
        layout.addWidget(self.btn_camera)
        
        self.btn_training = NavButton("🎯", "Training")
        self.btn_training.clicked.connect(lambda: self._navigate_to(1))
        layout.addWidget(self.btn_training)
        
        self.btn_observation = NavButton("👁", "Observation")
        self.btn_observation.clicked.connect(lambda: self._navigate_to(2))
        layout.addWidget(self.btn_observation)
        
        self.nav_buttons = [self.btn_camera, self.btn_training, self.btn_observation]
        
        # 여백
        layout.addStretch()
        
        # 사용 안내
        help_frame = QFrame()
        help_frame.setStyleSheet("""
            QFrame {
                background-color: #34495e;
                border-radius: 8px;
                margin: 15px;
            }
        """)
        help_layout = QVBoxLayout(help_frame)
        help_layout.setContentsMargins(15, 15, 15, 15)
        
        help_title = QLabel("💡 사용 순서")
        help_title.setStyleSheet("color: #ecf0f1; font-weight: bold; font-size: 12px;")
        help_layout.addWidget(help_title)
        
        help_text = QLabel(
            "1️⃣ Camera Settings\n"
            "     카메라 연결\n\n"
            "2️⃣ Training\n"
            "     템플릿 학습\n\n"
            "3️⃣ Observation\n"
            "     실시간 추적"
        )
        help_text.setStyleSheet("color: #bdc3c7; font-size: 10px; line-height: 1.4;")
        help_text.setWordWrap(True)
        help_layout.addWidget(help_text)
        
        layout.addWidget(help_frame)
        
        # 하단 정보
        info_label = QLabel("ONFRA Tracking System\nVersion 1.0")
        info_label.setAlignment(Qt.AlignCenter)
        info_label.setStyleSheet("color: #7f8c8d; font-size: 10px; padding: 15px;")
        layout.addWidget(info_label)
        
        return sidebar
    
    def _create_logo_widget(self) -> QWidget:
        """로고 위젯 생성"""
        widget = QWidget()
        widget.setFixedHeight(140)
        widget.setStyleSheet("background-color: #1a252f;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignCenter)
        
        if self.logo_pixmap is not None:
            # 로고 이미지 표시
            scaled_pixmap = self.logo_pixmap.scaled(
                220, 100,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            logo_label.setPixmap(scaled_pixmap)
        else:
            # 텍스트 플레이스홀더
            logo_label.setText("ONFRA")
            logo_label.setStyleSheet("""
                font-size: 36px;
                font-weight: bold;
                color: #3498db;
                background-color: #2c3e50;
                border-radius: 10px;
                padding: 20px;
            """)
        
        layout.addWidget(logo_label)
        
        return widget
    
    def _navigate_to(self, index: int):
        """페이지 이동"""
        self.page_stack.setCurrentIndex(index)
        
        # 버튼 상태 업데이트
        for i, btn in enumerate(self.nav_buttons):
            btn.setSelected(i == index)
        
        # 상태바 메시지 (상태바가 있을 때만)
        pages = ["Camera Settings", "Training", "Observation"]
        if hasattr(self, 'status_bar') and self.status_bar is not None:
            self.status_bar.showMessage(f"📍 {pages[index]}", 2000)
    
    def show_status_message(self, message: str, timeout: int = 3000):
        """상태바에 메시지 표시"""
        self.status_bar.showMessage(message, timeout)
    
    def closeEvent(self, event):
        """윈도우 닫기 이벤트"""
        logger.info("애플리케이션 종료")
        
        if hasattr(self.camera_page, 'cleanup'):
            self.camera_page.cleanup()
        
        if hasattr(self.observation_page, 'cleanup'):
            self.observation_page.cleanup()
        
        event.accept()
