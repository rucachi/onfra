"""
카메라 설정 페이지
카메라 선택, 파라미터 조정, 프리뷰
- 개선된 UI
"""
import json
import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap, QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QComboBox, QSpinBox, QSlider,
    QGroupBox, QMessageBox, QFrame
)

from vision.camera import CameraThread
from vision.utils import cv2_to_qimage

logger = logging.getLogger(__name__)


class CameraSettingsPage(QWidget):
    """카메라 설정 페이지"""
    
    def __init__(self):
        super().__init__()
        
        self.camera_thread: Optional[CameraThread] = None
        self.is_connected = False
        
        self._setup_ui()
        
        # 프리뷰 타이머
        self.preview_timer = QTimer()
        self.preview_timer.timeout.connect(self._update_preview)
        
    def _setup_ui(self):
        """UI 구성"""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        # ===== 좌측: 설정 패널 =====
        left_panel = QFrame()
        left_panel.setFixedWidth(350)
        left_panel.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border-radius: 12px;
            }
        """)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(20, 20, 20, 20)
        left_layout.setSpacing(15)
        
        # 제목
        title = QLabel("📷 카메라 설정")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #2c3e50;")
        left_layout.addWidget(title)
        
        # 카메라 선택
        camera_group = self._create_camera_group()
        left_layout.addWidget(camera_group)
        
        # 파라미터
        param_group = self._create_parameter_group()
        left_layout.addWidget(param_group)
        
        # 설정 저장/불러오기
        config_group = self._create_config_group()
        left_layout.addWidget(config_group)
        
        left_layout.addStretch()
        
        main_layout.addWidget(left_panel)
        
        # ===== 우측: 프리뷰 =====
        right_panel = QFrame()
        right_panel.setStyleSheet("""
            QFrame {
                background-color: #1a1a2e;
                border-radius: 12px;
            }
        """)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(15, 15, 15, 15)
        
        preview_title = QLabel("👁 실시간 프리뷰")
        preview_title.setStyleSheet("color: #ecf0f1; font-weight: bold; font-size: 14px;")
        preview_title.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(preview_title)
        
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumSize(640, 480)
        self.preview_label.setStyleSheet("""
            QLabel {
                background-color: #16213e;
                color: #7f8c8d;
                font-size: 14px;
                border: 2px solid #1a1a2e;
                border-radius: 10px;
            }
        """)
        self.preview_label.setText("📷 카메라를 연결하세요")
        right_layout.addWidget(self.preview_label, stretch=1)
        
        # 상태 표시
        self.status_label = QLabel("⚪ 연결 안 됨")
        self.status_label.setStyleSheet("color: #95a5a6; font-size: 12px;")
        self.status_label.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(self.status_label)
        
        main_layout.addWidget(right_panel, stretch=1)
    
    def _create_camera_group(self) -> QGroupBox:
        """카메라 선택 그룹"""
        group = QGroupBox("🎥 카메라 연결")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #2c3e50;
                border: 2px solid #e9ecef;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        layout = QVBoxLayout(group)
        layout.setSpacing(10)
        
        # 카메라 선택
        camera_row = QHBoxLayout()
        camera_row.addWidget(QLabel("카메라:"))
        
        self.camera_combo = QComboBox()
        self.camera_combo.addItems([f"Camera {i}" for i in range(5)])
        self.camera_combo.setStyleSheet("""
            QComboBox {
                padding: 8px;
                border: 2px solid #e9ecef;
                border-radius: 6px;
                min-width: 120px;
            }
        """)
        camera_row.addWidget(self.camera_combo, stretch=1)
        
        layout.addLayout(camera_row)
        
        # 연결 버튼
        self.btn_connect = QPushButton("🔌 연결하기")
        self.btn_connect.clicked.connect(self._toggle_connection)
        self.btn_connect.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                padding: 12px;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #229954;
            }
            QPushButton:pressed {
                background-color: #1e8449;
                padding-top: 14px;
                padding-bottom: 10px;
            }
        """)
        layout.addWidget(self.btn_connect)
        
        return group
    
    def _create_parameter_group(self) -> QGroupBox:
        """파라미터 조정 그룹"""
        group = QGroupBox("⚙ 카메라 파라미터")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #2c3e50;
                border: 2px solid #e9ecef;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        layout = QVBoxLayout(group)
        layout.setSpacing(12)
        
        # 해상도 프리셋 정의
        self.resolution_presets = [
            ("320 x 240 (QVGA)", 320, 240),
            ("640 x 480 (VGA)", 640, 480),
            ("800 x 600 (SVGA)", 800, 600),
            ("1280 x 720 (HD)", 1280, 720),
            ("1920 x 1080 (FHD)", 1920, 1080),
            ("2560 x 1440 (QHD)", 2560, 1440),
            ("3840 x 2160 (4K)", 3840, 2160),
        ]
        
        # 해상도 선택
        res_row = QHBoxLayout()
        res_row.setSpacing(10)
        res_label = QLabel("해상도:")
        res_label.setFixedWidth(45)
        res_label.setStyleSheet("font-size: 13px; color: #2c3e50;")
        res_row.addWidget(res_label)
        
        self.resolution_combo = QComboBox()
        for name, w, h in self.resolution_presets:
            self.resolution_combo.addItem(name)
        self.resolution_combo.setCurrentIndex(1)  # 640x480 기본값
        self.resolution_combo.setFixedHeight(36)
        self.resolution_combo.setStyleSheet("""
            QComboBox {
                padding: 8px 12px;
                border: 2px solid #dee2e6;
                border-radius: 6px;
                background-color: white;
                font-size: 12px;
            }
            QComboBox:hover {
                border-color: #3498db;
            }
            QComboBox:focus {
                border-color: #3498db;
            }
            QComboBox::drop-down {
                border: none;
                width: 25px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #3498db;
                margin-right: 8px;
            }
            QComboBox QAbstractItemView {
                background-color: white;
                border: 2px solid #dee2e6;
                selection-background-color: #3498db;
                selection-color: white;
                padding: 4px;
            }
        """)
        res_row.addWidget(self.resolution_combo, stretch=1)
        
        btn_apply_res = QPushButton("✓ 적용")
        btn_apply_res.clicked.connect(self._apply_resolution)
        btn_apply_res.setFixedHeight(36)
        btn_apply_res.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                padding: 0 16px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #229954;
            }
            QPushButton:pressed {
                background-color: #1e8449;
            }
        """)
        res_row.addWidget(btn_apply_res)
        
        layout.addLayout(res_row)
        
        # FPS 프리셋 정의
        self.fps_presets = [10, 15, 20, 24, 25, 30, 50, 60]
        
        # FPS 선택
        fps_row = QHBoxLayout()
        fps_row.setSpacing(10)
        fps_label = QLabel("FPS:")
        fps_label.setFixedWidth(45)
        fps_label.setStyleSheet("font-size: 13px; color: #2c3e50;")
        fps_row.addWidget(fps_label)
        
        self.fps_combo = QComboBox()
        for fps in self.fps_presets:
            self.fps_combo.addItem(f"{fps} fps")
        self.fps_combo.setCurrentIndex(5)  # 30fps 기본값
        self.fps_combo.setFixedHeight(36)
        self.fps_combo.setStyleSheet("""
            QComboBox {
                padding: 8px 12px;
                border: 2px solid #dee2e6;
                border-radius: 6px;
                background-color: white;
                font-size: 12px;
            }
            QComboBox:hover {
                border-color: #3498db;
            }
            QComboBox:focus {
                border-color: #3498db;
            }
            QComboBox::drop-down {
                border: none;
                width: 25px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #3498db;
                margin-right: 8px;
            }
            QComboBox QAbstractItemView {
                background-color: white;
                border: 2px solid #dee2e6;
                selection-background-color: #3498db;
                selection-color: white;
                padding: 4px;
            }
        """)
        fps_row.addWidget(self.fps_combo, stretch=1)
        
        btn_apply_fps = QPushButton("✓ 적용")
        btn_apply_fps.clicked.connect(self._apply_fps)
        btn_apply_fps.setFixedHeight(36)
        btn_apply_fps.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                padding: 0 16px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #229954;
            }
            QPushButton:pressed {
                background-color: #1e8449;
            }
        """)
        fps_row.addWidget(btn_apply_fps)
        
        layout.addLayout(fps_row)
        
        # 노출
        exposure_row = QHBoxLayout()
        exposure_row.addWidget(QLabel("노출:"))
        
        self.exposure_slider = QSlider(Qt.Horizontal)
        self.exposure_slider.setRange(-13, -1)
        self.exposure_slider.setValue(-6)
        self.exposure_slider.valueChanged.connect(self._apply_exposure)
        exposure_row.addWidget(self.exposure_slider, stretch=1)
        
        self.exposure_label = QLabel("-6")
        self.exposure_label.setFixedWidth(30)
        exposure_row.addWidget(self.exposure_label)
        
        layout.addLayout(exposure_row)
        
        # 게인
        gain_row = QHBoxLayout()
        gain_row.addWidget(QLabel("게인:"))
        
        self.gain_slider = QSlider(Qt.Horizontal)
        self.gain_slider.setRange(0, 100)
        self.gain_slider.setValue(0)
        self.gain_slider.valueChanged.connect(self._apply_gain)
        gain_row.addWidget(self.gain_slider, stretch=1)
        
        self.gain_label = QLabel("0")
        self.gain_label.setFixedWidth(30)
        gain_row.addWidget(self.gain_label)
        
        layout.addLayout(gain_row)
        
        return group
    
    def _create_config_group(self) -> QGroupBox:
        """설정 저장/불러오기 그룹"""
        group = QGroupBox("💾 설정 관리")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #2c3e50;
                border: 2px solid #e9ecef;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        layout = QHBoxLayout(group)
        
        btn_save = QPushButton("💾 저장")
        btn_save.clicked.connect(self._save_config)
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                padding: 10px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #229954;
            }
            QPushButton:pressed {
                background-color: #1e8449;
                padding-top: 12px;
                padding-bottom: 8px;
            }
        """)
        layout.addWidget(btn_save)
        
        btn_load = QPushButton("📂 불러오기")
        btn_load.clicked.connect(self._load_config)
        btn_load.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                padding: 10px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #1f618d;
                padding-top: 12px;
                padding-bottom: 8px;
            }
        """)
        layout.addWidget(btn_load)
        
        return group
    
    def _toggle_connection(self):
        """카메라 연결/해제"""
        if not self.is_connected:
            camera_index = self.camera_combo.currentIndex()
            self.camera_thread = CameraThread(camera_index=camera_index)
            
            if self.camera_thread.open_camera():
                self.camera_thread.start()
                self.preview_timer.start(33)
                self.is_connected = True
                
                self.btn_connect.setText("🔌 연결 해제")
                self.btn_connect.setStyleSheet("""
                    QPushButton {
                        background-color: #e74c3c;
                        color: white;
                        padding: 12px;
                        border-radius: 8px;
                        font-weight: bold;
                        font-size: 14px;
                    }
                    QPushButton:hover {
                        background-color: #c0392b;
                    }
                    QPushButton:pressed {
                        background-color: #a93226;
                        padding-top: 14px;
                        padding-bottom: 10px;
                    }
                """)
                
                self.status_label.setText("🟢 연결됨")
                self.status_label.setStyleSheet("color: #27ae60; font-size: 12px;")
                
                logger.info(f"카메라 {camera_index} 연결 성공")
            else:
                QMessageBox.warning(self, "⚠ 연결 실패", 
                    f"카메라 {camera_index}를 열 수 없습니다.\n\n" +
                    "확인 사항:\n" +
                    "• 카메라가 연결되어 있는지\n" +
                    "• 다른 프로그램에서 사용 중인지\n" +
                    "• 다른 카메라 인덱스 시도")
        else:
            self.cleanup()
    
    def _update_preview(self):
        """프리뷰 업데이트"""
        if self.camera_thread is None or not self.is_connected:
            return
        
        frame = self.camera_thread.get_frame(timeout=0.1)
        
        if frame is not None:
            qimage = cv2_to_qimage(frame)
            if qimage is not None:
                pixmap = QPixmap.fromImage(qimage)
                scaled_pixmap = pixmap.scaled(
                    self.preview_label.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.preview_label.setPixmap(scaled_pixmap)
    
    def _apply_resolution(self):
        """해상도 적용"""
        if not self.is_connected:
            QMessageBox.warning(self, "⚠ 경고", "먼저 카메라를 연결하세요.")
            return
        
        idx = self.resolution_combo.currentIndex()
        _, width, height = self.resolution_presets[idx]
        
        if self.camera_thread.set_resolution(width, height):
            QMessageBox.information(self, "✅ 성공", f"해상도: {width}x{height}")
        else:
            QMessageBox.warning(self, "⚠ 실패", "해상도 설정 실패 (미지원)")
    
    def _apply_fps(self):
        """FPS 적용"""
        if not self.is_connected:
            QMessageBox.warning(self, "⚠ 경고", "먼저 카메라를 연결하세요.")
            return
        
        idx = self.fps_combo.currentIndex()
        fps = self.fps_presets[idx]
        
        if self.camera_thread.set_fps(fps):
            QMessageBox.information(self, "✅ 성공", f"FPS: {fps}")
        else:
            QMessageBox.warning(self, "⚠ 실패", "FPS 설정 실패 (미지원)")
    
    def _apply_exposure(self, value: int):
        """노출 적용"""
        self.exposure_label.setText(str(value))
        
        if self.camera_thread is not None and self.is_connected:
            self.camera_thread.set_exposure(value)
    
    def _apply_gain(self, value: int):
        """게인 적용"""
        self.gain_label.setText(str(value))
        
        if self.camera_thread is not None and self.is_connected:
            self.camera_thread.set_gain(value)
    
    def _save_config(self):
        """설정 저장"""
        res_idx = self.resolution_combo.currentIndex()
        _, width, height = self.resolution_presets[res_idx]
        fps_idx = self.fps_combo.currentIndex()
        fps = self.fps_presets[fps_idx]
        
        config = {
            "camera_index": self.camera_combo.currentIndex(),
            "resolution_index": res_idx,
            "width": width,
            "height": height,
            "fps_index": fps_idx,
            "fps": fps,
            "exposure": self.exposure_slider.value(),
            "gain": self.gain_slider.value()
        }
        
        try:
            config_path = Path("camera_config.json")
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
            
            QMessageBox.information(self, "✅ 저장 완료", f"설정이 저장되었습니다.")
            logger.info(f"카메라 설정 저장: {config_path}")
        except Exception as e:
            QMessageBox.critical(self, "❌ 오류", f"설정 저장 실패: {e}")
    
    def _load_config(self):
        """설정 불러오기"""
        try:
            config_path = Path("camera_config.json")
            
            if not config_path.exists():
                QMessageBox.warning(self, "⚠ 경고", "저장된 설정이 없습니다.")
                return
            
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            
            self.camera_combo.setCurrentIndex(config.get("camera_index", 0))
            self.resolution_combo.setCurrentIndex(config.get("resolution_index", 1))
            self.fps_combo.setCurrentIndex(config.get("fps_index", 5))
            self.exposure_slider.setValue(config.get("exposure", -6))
            self.gain_slider.setValue(config.get("gain", 0))
            
            QMessageBox.information(self, "✅ 불러오기 완료", "설정을 불러왔습니다.")
        except Exception as e:
            QMessageBox.critical(self, "❌ 오류", f"설정 불러오기 실패: {e}")
    
    def get_camera_thread(self) -> Optional[CameraThread]:
        """카메라 스레드 반환"""
        return self.camera_thread if self.is_connected else None
    
    def cleanup(self):
        """정리"""
        if self.camera_thread is not None:
            self.preview_timer.stop()
            self.camera_thread.stop()
            self.camera_thread.join(timeout=2.0)
            self.camera_thread = None
            self.is_connected = False
            
            self.btn_connect.setText("🔌 연결하기")
            self.btn_connect.setStyleSheet("""
                QPushButton {
                    background-color: #27ae60;
                    color: white;
                    padding: 12px;
                    border-radius: 8px;
                    font-weight: bold;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: #229954;
                }
                QPushButton:pressed {
                    background-color: #1e8449;
                    padding-top: 14px;
                    padding-bottom: 10px;
                }
            """)
            
            self.preview_label.clear()
            self.preview_label.setText("📷 카메라를 연결하세요")
            self.status_label.setText("⚪ 연결 안 됨")
            self.status_label.setStyleSheet("color: #95a5a6; font-size: 12px;")
            
            logger.info("카메라 연결 해제")
