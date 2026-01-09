"""
관찰(Observation) 페이지
실시간 추적, 오버레이, 상태 표시
- 개선된 UI
"""
import logging
from typing import Optional
from datetime import datetime

import cv2
import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap, QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QGroupBox, QMessageBox, QFrame
)

from vision.recipe import RecipeManager, Recipe
from vision.tracker_pipeline import TrackerPipeline, TrackingState
from vision.utils import cv2_to_qimage, draw_bbox

logger = logging.getLogger(__name__)


class ObservationPage(QWidget):
    """관찰 페이지"""
    
    def __init__(self):
        super().__init__()
        
        self.recipe_manager = RecipeManager()
        self.tracker_pipeline: Optional[TrackerPipeline] = None
        self.current_recipe: Optional[Recipe] = None
        self.is_tracking = False
        
        self._setup_ui()
        
        # 프리뷰 타이머
        self.preview_timer = QTimer()
        self.preview_timer.timeout.connect(self._feed_frames)
    
    def _setup_ui(self):
        """UI 구성"""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        # ===== 좌측: 컨트롤 패널 =====
        left_panel = QFrame()
        left_panel.setFixedWidth(280)
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
        title = QLabel("👁 실시간 추적")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #2c3e50;")
        left_layout.addWidget(title)
        
        # 레시피 선택
        recipe_group = QGroupBox("📦 템플릿 선택")
        recipe_group.setStyleSheet("""
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
        recipe_layout = QVBoxLayout(recipe_group)
        
        recipe_row = QHBoxLayout()
        self.recipe_combo = QComboBox()
        self.recipe_combo.setStyleSheet("""
            QComboBox {
                padding: 10px;
                border: 2px solid #e9ecef;
                border-radius: 6px;
                font-size: 13px;
            }
        """)
        self._refresh_recipe_list()
        recipe_row.addWidget(self.recipe_combo, stretch=1)
        
        btn_refresh = QPushButton("🔄")
        btn_refresh.setFixedWidth(40)
        btn_refresh.clicked.connect(self._refresh_recipe_list)
        btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border-radius: 6px;
                font-size: 16px;
                padding: 6px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #1f618d;
                padding-top: 8px;
                padding-bottom: 4px;
            }
        """)
        recipe_row.addWidget(btn_refresh)
        
        recipe_layout.addLayout(recipe_row)
        left_layout.addWidget(recipe_group)
        
        # 컨트롤 버튼
        control_group = QGroupBox("🎮 제어")
        control_group.setStyleSheet("""
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
        control_layout = QVBoxLayout(control_group)
        control_layout.setSpacing(10)
        
        self.btn_start = QPushButton("▶ 추적 시작")
        self.btn_start.clicked.connect(self._toggle_tracking)
        self.btn_start.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                padding: 14px;
                border-radius: 8px;
                font-weight: bold;
                font-size: 15px;
            }
            QPushButton:hover {
                background-color: #229954;
            }
            QPushButton:pressed {
                background-color: #1e8449;
                padding-top: 16px;
                padding-bottom: 12px;
            }
        """)
        control_layout.addWidget(self.btn_start)
        
        btn_reacquire = QPushButton("🔍 재탐색")
        btn_reacquire.clicked.connect(self._force_reacquire)
        btn_reacquire.setStyleSheet("""
            QPushButton {
                background-color: #f39c12;
                color: white;
                padding: 12px;
                border-radius: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #d68910;
            }
            QPushButton:pressed {
                background-color: #b9770e;
                padding-top: 14px;
                padding-bottom: 10px;
            }
        """)
        control_layout.addWidget(btn_reacquire)
        
        btn_snapshot = QPushButton("📸 스냅샷 저장")
        btn_snapshot.clicked.connect(self._take_snapshot)
        btn_snapshot.setStyleSheet("""
            QPushButton {
                background-color: #9b59b6;
                color: white;
                padding: 12px;
                border-radius: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #8e44ad;
            }
            QPushButton:pressed {
                background-color: #7d3c98;
                padding-top: 14px;
                padding-bottom: 10px;
            }
        """)
        control_layout.addWidget(btn_snapshot)
        
        left_layout.addWidget(control_group)
        
        # 상태 표시
        status_group = QGroupBox("📊 추적 상태")
        status_group.setStyleSheet("""
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
        status_layout = QVBoxLayout(status_group)
        
        # 상태
        state_row = QHBoxLayout()
        state_row.addWidget(QLabel("상태:"))
        self.state_label = QLabel("IDLE")
        self.state_label.setStyleSheet("""
            QLabel {
                background-color: #95a5a6;
                color: white;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
            }
        """)
        state_row.addWidget(self.state_label)
        state_row.addStretch()
        status_layout.addLayout(state_row)
        
        # 점수
        score_row = QHBoxLayout()
        score_row.addWidget(QLabel("신뢰도:"))
        self.score_label = QLabel("0.00")
        self.score_label.setStyleSheet("""
            QLabel {
                background-color: #34495e;
                color: white;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
            }
        """)
        score_row.addWidget(self.score_label)
        score_row.addStretch()
        status_layout.addLayout(score_row)
        
        left_layout.addWidget(status_group)
        
        # 상태 설명
        legend_frame = QFrame()
        legend_frame.setStyleSheet("background-color: white; border-radius: 8px; padding: 10px;")
        legend_layout = QVBoxLayout(legend_frame)
        legend_layout.setSpacing(5)
        
        legend_title = QLabel("📖 상태 설명")
        legend_title.setStyleSheet("font-weight: bold; color: #2c3e50;")
        legend_layout.addWidget(legend_title)
        
        legends = [
            ("🟠 SEARCH", "객체 탐색 중"),
            ("🟢 TRACK", "추적 성공"),
            ("🔴 LOST", "추적 실패"),
            ("🟡 REACQUIRE", "재탐색 중"),
        ]
        
        for color, desc in legends:
            row = QHBoxLayout()
            lbl = QLabel(f"{color}: {desc}")
            lbl.setStyleSheet("color: #7f8c8d; font-size: 11px;")
            row.addWidget(lbl)
            legend_layout.addLayout(row)
        
        left_layout.addWidget(legend_frame)
        
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
        
        preview_title = QLabel("🎯 실시간 추적 화면")
        preview_title.setStyleSheet("color: #ecf0f1; font-weight: bold; font-size: 14px;")
        preview_title.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(preview_title)
        
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumSize(800, 600)
        self.preview_label.setStyleSheet("""
            QLabel {
                background-color: #16213e;
                color: #7f8c8d;
                font-size: 14px;
                border: 2px solid #1a1a2e;
                border-radius: 10px;
            }
        """)
        self.preview_label.setText("📦 템플릿을 선택하고\n▶ 추적 시작 버튼을 누르세요")
        right_layout.addWidget(self.preview_label, stretch=1)
        
        main_layout.addWidget(right_panel, stretch=1)
    
    def _refresh_recipe_list(self):
        """레시피 목록 새로고침"""
        self.recipe_combo.clear()
        recipes = self.recipe_manager.list_recipes()
        for name in recipes:
            self.recipe_combo.addItem(f"📦 {name}")
        logger.info(f"레시피 목록: {len(recipes)}개")
    
    def _toggle_tracking(self):
        """추적 시작/중지"""
        if not self.is_tracking:
            recipe_text = self.recipe_combo.currentText()
            
            if not recipe_text:
                QMessageBox.warning(self, "⚠ 템플릿 필요", 
                    "먼저 Training 페이지에서\n템플릿을 학습하고 저장하세요.")
                return
            
            recipe_name = recipe_text.replace("📦 ", "")
            recipe = self.recipe_manager.load_recipe(recipe_name)
            
            if recipe is None:
                QMessageBox.critical(self, "❌ 로드 실패", "템플릿 로드에 실패했습니다.")
                return
            
            self.current_recipe = recipe
            
            # 추적 파이프라인 시작
            self.tracker_pipeline = TrackerPipeline()
            self.tracker_pipeline.frame_processed.connect(self._on_frame_processed)
            self.tracker_pipeline.state_changed.connect(self._on_state_changed)
            self.tracker_pipeline.error_occurred.connect(self._on_error)
            
            self.tracker_pipeline.set_recipe(recipe)
            self.tracker_pipeline.start()
            
            self.preview_timer.start(33)
            self.is_tracking = True
            
            self.btn_start.setText("⏹ 추적 중지")
            self.btn_start.setStyleSheet("""
                QPushButton {
                    background-color: #e74c3c;
                    color: white;
                    padding: 14px;
                    border-radius: 8px;
                    font-weight: bold;
                    font-size: 15px;
                }
                QPushButton:hover {
                    background-color: #c0392b;
                }
                QPushButton:pressed {
                    background-color: #a93226;
                    padding-top: 16px;
                    padding-bottom: 12px;
                }
            """)
            
            logger.info(f"추적 시작: {recipe_name}")
        else:
            self.cleanup()
    
    def _feed_frames(self):
        """프레임을 추적 파이프라인에 전달"""
        if self.tracker_pipeline is None:
            return
        
        main_window = self.window()
        if hasattr(main_window, 'camera_page'):
            camera_thread = main_window.camera_page.get_camera_thread()
            
            if camera_thread is not None:
                frame = camera_thread.get_frame(timeout=0.1)
                
                if frame is not None:
                    self.tracker_pipeline.put_frame(frame)
    
    def _on_frame_processed(self, frame: np.ndarray, result: dict):
        """프레임 처리 완료"""
        display_frame = frame.copy()
        
        bbox = result.get("bbox")
        corners = result.get("corners")
        state = result.get("state", "IDLE")
        score = result.get("score", 0.0)
        matches = result.get("matches", 0)
        
        # 상태에 따른 색상
        color_map = {
            "SEARCH": (0, 165, 255),    # 주황 (BGR)
            "TRACK": (0, 255, 0),       # 초록
            "LOST": (0, 0, 255),        # 빨강
            "REACQUIRE": (0, 255, 255)  # 노랑
        }
        color = color_map.get(state, (128, 128, 128))
        
        # 폴리곤 그리기 (호모그래피 결과)
        if corners is not None and len(corners) == 4:
            pts = corners.reshape((-1, 1, 2))
            cv2.polylines(display_frame, [pts], True, color, 3)
            
            # 중심점
            cx = int(np.mean(corners[:, 0]))
            cy = int(np.mean(corners[:, 1]))
            cv2.circle(display_frame, (cx, cy), 8, color, -1)
            cv2.circle(display_frame, (cx, cy), 12, color, 2)
        
        # 바운딩 박스 그리기
        if bbox is not None:
            x, y, w, h = bbox
            
            # 폴리곤이 없으면 사각형 그리기
            if corners is None:
                cv2.rectangle(display_frame, (x, y), (x + w, y + h), color, 3)
                
                # 중심점
                cx, cy = x + w // 2, y + h // 2
                cv2.circle(display_frame, (cx, cy), 8, color, -1)
            
            # 라벨 배경
            label = f"{state} | {self.current_recipe.name if self.current_recipe else ''}"
            info = f"Score: {score:.2f} | Matches: {matches}"
            
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.6
            thickness = 2
            
            # 상단 라벨
            (lw, lh), _ = cv2.getTextSize(label, font, font_scale, thickness)
            cv2.rectangle(display_frame, (x, y - lh - 10), (x + lw + 10, y), color, -1)
            cv2.putText(display_frame, label, (x + 5, y - 5), font, font_scale, (0, 0, 0), thickness)
            
            # 하단 정보
            (iw, ih), _ = cv2.getTextSize(info, font, 0.5, 1)
            cv2.rectangle(display_frame, (x, y + h), (x + iw + 10, y + h + ih + 10), (0, 0, 0), -1)
            cv2.putText(display_frame, info, (x + 5, y + h + ih + 5), font, 0.5, (255, 255, 255), 1)
        
        # 프레임 좌상단에 상태 표시
        status_text = f"[{state}] Score: {score:.2f}"
        cv2.putText(display_frame, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        cv2.putText(display_frame, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 1)
        
        qimage = cv2_to_qimage(display_frame)
        if qimage is not None:
            pixmap = QPixmap.fromImage(qimage)
            scaled_pixmap = pixmap.scaled(
                self.preview_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.preview_label.setPixmap(scaled_pixmap)
        
        self.score_label.setText(f"{score:.2f}")
    
    def _on_state_changed(self, state: str):
        """상태 변경"""
        self.state_label.setText(state)
        
        color_map = {
            "IDLE": "#95a5a6",
            "SEARCH": "#f39c12",
            "TRACK": "#27ae60",
            "LOST": "#e74c3c",
            "REACQUIRE": "#f1c40f"
        }
        color = color_map.get(state, "#95a5a6")
        
        self.state_label.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                color: white;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
            }}
        """)
        
        logger.info(f"상태 변경: {state}")
    
    def _on_error(self, error_msg: str):
        """에러 발생"""
        logger.error(f"추적 에러: {error_msg}")
        QMessageBox.warning(self, "⚠ 에러", f"추적 중 에러:\n{error_msg}")
    
    def _force_reacquire(self):
        """강제 재탐색"""
        if self.tracker_pipeline is not None and self.is_tracking:
            self.tracker_pipeline.force_reacquire()
            logger.info("강제 재탐색")
        else:
            QMessageBox.warning(self, "⚠ 경고", "먼저 추적을 시작하세요.")
    
    def _take_snapshot(self):
        """스냅샷 저장"""
        if not self.is_tracking:
            QMessageBox.warning(self, "⚠ 경고", "먼저 추적을 시작하세요.")
            return
        
        pixmap = self.preview_label.pixmap()
        
        if pixmap is not None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"snapshot_{timestamp}.png"
            
            if pixmap.save(filename):
                QMessageBox.information(self, "✅ 저장 완료", f"스냅샷: {filename}")
                logger.info(f"스냅샷 저장: {filename}")
            else:
                QMessageBox.critical(self, "❌ 실패", "스냅샷 저장 실패")
    
    def cleanup(self):
        """정리"""
        if self.tracker_pipeline is not None:
            self.preview_timer.stop()
            self.tracker_pipeline.stop()
            self.tracker_pipeline.join(timeout=2.0)  # Thread.join() 사용
            self.tracker_pipeline = None
        
        self.is_tracking = False
        self.current_recipe = None
        
        self.btn_start.setText("▶ 추적 시작")
        self.btn_start.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                padding: 14px;
                border-radius: 8px;
                font-weight: bold;
                font-size: 15px;
            }
            QPushButton:hover {
                background-color: #229954;
            }
            QPushButton:pressed {
                background-color: #1e8449;
                padding-top: 16px;
                padding-bottom: 12px;
            }
        """)
        
        self.state_label.setText("IDLE")
        self.state_label.setStyleSheet("""
            QLabel {
                background-color: #95a5a6;
                color: white;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
            }
        """)
        self.score_label.setText("0.00")
        self.preview_label.clear()
        self.preview_label.setText("📦 템플릿을 선택하고\n▶ 추적 시작 버튼을 누르세요")
        
        logger.info("추적 중지")
