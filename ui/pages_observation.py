"""
관찰(Observation) 페이지
실시간 추적, 오버레이, 상태 표시
- 멀티 템플릿 추적 지원
"""
import logging
from typing import Optional, List
from datetime import datetime

import cv2
import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap, QFont, QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QGroupBox, QMessageBox, QFrame,
    QListWidget, QListWidgetItem, QAbstractItemView, QScrollArea
)

from vision.recipe import RecipeManager, Recipe
from vision.multi_tracker import MultiTrackerPipeline, TRACKING_COLORS
from vision.utils import cv2_to_qimage

logger = logging.getLogger(__name__)


class ObservationPage(QWidget):
    """관찰 페이지 - 멀티 템플릿 추적"""
    
    def __init__(self):
        super().__init__()
        
        self.recipe_manager = RecipeManager()
        self.multi_tracker: Optional[MultiTrackerPipeline] = None
        self.selected_recipes: List[str] = []
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
        left_panel.setFixedWidth(300)
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
        
        # 템플릿 선택 (체크박스 리스트)
        recipe_group = QGroupBox("📦 템플릿 선택 (복수 선택 가능)")
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
        
        # 체크박스 리스트
        self.recipe_list = QListWidget()
        self.recipe_list.setMinimumHeight(100)
        self.recipe_list.setMaximumHeight(160)
        self.recipe_list.setSpacing(2)  # 아이템 간 간격
        self.recipe_list.setStyleSheet("""
            QListWidget {
                border: 2px solid #dee2e6;
                border-radius: 8px;
                background-color: white;
                outline: none;
            }
            QListWidget::item {
                padding: 4px;
            }
            QListWidget::item:hover {
                background-color: #e3f2fd;
            }
            QListWidget::indicator {
                width: 14px;
                height: 14px;
            }
            QListWidget::indicator:unchecked {
                border: 2px solid #adb5bd;
                background-color: white;
            }
            QListWidget::indicator:checked {
                border: 2px solid #27ae60;
                background-color: #27ae60;
            }
        """)
        self._refresh_recipe_list()
        recipe_layout.addWidget(self.recipe_list)
        
        # 선택된 템플릿 표시
        self.selected_label = QLabel("선택됨: 0개")
        self.selected_label.setStyleSheet("color: #6c757d; font-size: 12px;")
        recipe_layout.addWidget(self.selected_label)
        
        # 버튼 행
        btn_row = QHBoxLayout()
        
        btn_select_all = QPushButton("모두 선택")
        btn_select_all.clicked.connect(self._select_all)
        btn_select_all.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #5a6268; }
            QPushButton:pressed { background-color: #495057; }
        """)
        btn_row.addWidget(btn_select_all)
        
        btn_clear = QPushButton("선택 해제")
        btn_clear.clicked.connect(self._clear_selection)
        btn_clear.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #5a6268; }
            QPushButton:pressed { background-color: #495057; }
        """)
        btn_row.addWidget(btn_clear)
        
        btn_refresh = QPushButton("🔄")
        btn_refresh.setFixedWidth(36)
        btn_refresh.clicked.connect(self._refresh_recipe_list)
        btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border-radius: 4px;
                font-size: 14px;
                padding: 6px;
            }
            QPushButton:hover { background-color: #2980b9; }
            QPushButton:pressed { background-color: #1f618d; }
        """)
        btn_row.addWidget(btn_refresh)
        
        recipe_layout.addLayout(btn_row)
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
            QPushButton:hover { background-color: #229954; }
            QPushButton:pressed { background-color: #1e8449; }
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
            QPushButton:hover { background-color: #d68910; }
            QPushButton:pressed { background-color: #b9770e; }
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
            QPushButton:hover { background-color: #8e44ad; }
            QPushButton:pressed { background-color: #7d3c98; }
        """)
        control_layout.addWidget(btn_snapshot)
        
        left_layout.addWidget(control_group)
        
        # 추적 상태 (멀티 템플릿)
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
        
        # 스크롤 가능한 상태 영역
        self.status_container = QVBoxLayout()
        self.status_labels = {}  # 템플릿별 상태 라벨
        
        self.status_placeholder = QLabel("추적 시작 시 상태가 표시됩니다")
        self.status_placeholder.setStyleSheet("color: #adb5bd; font-style: italic;")
        self.status_container.addWidget(self.status_placeholder)
        
        status_layout.addLayout(self.status_container)
        left_layout.addWidget(status_group)
        
        # 색상 범례
        legend_group = QGroupBox("🎨 색상 범례")
        legend_group.setStyleSheet("""
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
        legend_layout = QVBoxLayout(legend_group)
        
        self.legend_container = QVBoxLayout()
        self.legend_placeholder = QLabel("템플릿 선택 시 색상이 표시됩니다")
        self.legend_placeholder.setStyleSheet("color: #adb5bd; font-style: italic; font-size: 11px;")
        self.legend_container.addWidget(self.legend_placeholder)
        
        legend_layout.addLayout(self.legend_container)
        left_layout.addWidget(legend_group)
        
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
        self.preview_label.setText("☑ 템플릿을 체크하고\n▶ 추적 시작 버튼을 누르세요")
        right_layout.addWidget(self.preview_label, stretch=1)
        
        main_layout.addWidget(right_panel, stretch=1)
    
    def _refresh_recipe_list(self):
        """레시피 목록 새로고침"""
        # 기존 시그널 연결 해제
        try:
            self.recipe_list.itemChanged.disconnect()
        except:
            pass
        
        self.recipe_list.clear()
        recipes = self.recipe_manager.list_recipes()
        
        for i, name in enumerate(recipes):
            item = QListWidgetItem()
            
            # 색상 가져오기
            color = TRACKING_COLORS[i % len(TRACKING_COLORS)]
            color_hex = f"#{color[2]:02x}{color[1]:02x}{color[0]:02x}"  # BGR to RGB hex
            
            # 색상 블록과 이름 함께 표시 (이름은 항상 어두운 색)
            item.setText(f"[■] {name}")
            item.setData(Qt.UserRole, name)  # 실제 이름 저장
            item.setData(Qt.UserRole + 1, color_hex)  # 색상 저장
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            
            # 글씨는 항상 어두운 색으로 고정
            item.setForeground(QColor("#2c3e50"))
            
            self.recipe_list.addItem(item)
        
        self.recipe_list.itemChanged.connect(self._on_selection_changed)
        logger.info(f"레시피 목록: {len(recipes)}개")
    
    def _on_selection_changed(self):
        """선택 변경 시"""
        selected = self._get_selected_recipes()
        self.selected_label.setText(f"선택됨: {len(selected)}개")
        self._update_legend(selected)
    
    def _get_selected_recipes(self) -> List[str]:
        """선택된 레시피 목록"""
        selected = []
        for i in range(self.recipe_list.count()):
            item = self.recipe_list.item(i)
            if item.checkState() == Qt.Checked:
                name = item.data(Qt.UserRole)  # UserRole에서 실제 이름 가져오기
                if name:
                    selected.append(name)
        return selected
    
    def _select_all(self):
        """모두 선택"""
        for i in range(self.recipe_list.count()):
            item = self.recipe_list.item(i)
            item.setCheckState(Qt.Checked)
    
    def _clear_selection(self):
        """선택 해제"""
        for i in range(self.recipe_list.count()):
            item = self.recipe_list.item(i)
            item.setCheckState(Qt.Unchecked)
    
    def _update_legend(self, selected_names: List[str]):
        """색상 범례 업데이트"""
        # 기존 아이템 제거
        while self.legend_container.count():
            item = self.legend_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if not selected_names:
            placeholder = QLabel("템플릿 선택 시 색상이 표시됩니다")
            placeholder.setStyleSheet("color: #adb5bd; font-style: italic; font-size: 11px;")
            self.legend_container.addWidget(placeholder)
            return
        
        for i, name in enumerate(selected_names):
            color = TRACKING_COLORS[i % len(TRACKING_COLORS)]
            color_hex = f"#{color[2]:02x}{color[1]:02x}{color[0]:02x}"
            
            row = QHBoxLayout()
            
            color_box = QLabel("■")
            color_box.setStyleSheet(f"color: {color_hex}; font-size: 16px;")
            color_box.setFixedWidth(20)
            row.addWidget(color_box)
            
            name_label = QLabel(name)
            name_label.setStyleSheet("font-size: 11px; color: #495057;")
            row.addWidget(name_label)
            row.addStretch()
            
            container = QWidget()
            container.setLayout(row)
            self.legend_container.addWidget(container)
    
    def _toggle_tracking(self):
        """추적 시작/중지"""
        if not self.is_tracking:
            selected = self._get_selected_recipes()
            
            if not selected:
                QMessageBox.warning(self, "⚠ 템플릿 필요", 
                    "추적할 템플릿을 하나 이상 선택하세요.\n\n"
                    "☑ 체크박스를 클릭하여 선택하세요.")
                return
            
            self.selected_recipes = selected
            
            # 멀티 트래커 시작
            self.multi_tracker = MultiTrackerPipeline()
            self.multi_tracker.frame_processed.connect(self._on_frame_processed)
            self.multi_tracker.error_occurred.connect(self._on_error)
            
            self.multi_tracker.set_recipes(selected)
            self.multi_tracker.start()
            
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
                QPushButton:hover { background-color: #c0392b; }
                QPushButton:pressed { background-color: #a93226; }
            """)
            
            # 상태 라벨 초기화
            self._init_status_labels(selected)
            
            logger.info(f"멀티 추적 시작: {len(selected)}개 템플릿")
        else:
            self.cleanup()
    
    def _init_status_labels(self, names: List[str]):
        """상태 라벨 초기화"""
        # 기존 라벨 제거
        while self.status_container.count():
            item = self.status_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.status_labels.clear()
        
        for i, name in enumerate(names):
            color = TRACKING_COLORS[i % len(TRACKING_COLORS)]
            color_hex = f"#{color[2]:02x}{color[1]:02x}{color[0]:02x}"
            
            row = QHBoxLayout()
            
            color_box = QLabel("●")
            color_box.setStyleSheet(f"color: {color_hex}; font-size: 14px;")
            color_box.setFixedWidth(20)
            row.addWidget(color_box)
            
            name_label = QLabel(f"{name}:")
            name_label.setStyleSheet("font-size: 11px; font-weight: bold;")
            name_label.setFixedWidth(80)
            row.addWidget(name_label)
            
            status_label = QLabel("SEARCH")
            status_label.setStyleSheet("""
                background-color: #f39c12;
                color: white;
                padding: 2px 8px;
                border-radius: 4px;
                font-size: 10px;
                font-weight: bold;
            """)
            row.addWidget(status_label)
            row.addStretch()
            
            container = QWidget()
            container.setLayout(row)
            self.status_container.addWidget(container)
            
            self.status_labels[name] = status_label
    
    def _feed_frames(self):
        """프레임을 추적 파이프라인에 전달"""
        if self.multi_tracker is None:
            return
        
        main_window = self.window()
        if hasattr(main_window, 'camera_page'):
            camera_thread = main_window.camera_page.get_camera_thread()
            
            if camera_thread is not None:
                frame = camera_thread.get_frame(timeout=0.1)
                
                if frame is not None:
                    self.multi_tracker.put_frame(frame)
    
    def _on_frame_processed(self, frame: np.ndarray, results: list):
        """멀티 템플릿 프레임 처리 완료"""
        display_frame = frame.copy()
        
        for result in results:
            name = result.get("name", "")
            color = result.get("color", (0, 255, 0))
            bbox = result.get("bbox")
            corners = result.get("corners")
            state = result.get("state", "IDLE")
            score = result.get("score", 0.0)
            matches = result.get("matches", 0)
            
            # 상태 업데이트
            self._update_status_label(name, state)
            
            # 폴리곤 그리기
            if corners is not None and len(corners) == 4:
                pts = corners.reshape((-1, 1, 2))
                cv2.polylines(display_frame, [pts], True, color, 3)
                
                cx = int(np.mean(corners[:, 0]))
                cy = int(np.mean(corners[:, 1]))
                cv2.circle(display_frame, (cx, cy), 8, color, -1)
                cv2.circle(display_frame, (cx, cy), 12, color, 2)
            
            # 바운딩 박스 그리기
            if bbox is not None:
                x, y, w, h = bbox
                
                if corners is None:
                    cv2.rectangle(display_frame, (x, y), (x + w, y + h), color, 3)
                    cx, cy = x + w // 2, y + h // 2
                    cv2.circle(display_frame, (cx, cy), 8, color, -1)
                
                # 라벨
                label = f"{name} | {state}"
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 0.5
                thickness = 2
                
                (lw, lh), _ = cv2.getTextSize(label, font, font_scale, thickness)
                cv2.rectangle(display_frame, (x, y - lh - 10), (x + lw + 10, y), color, -1)
                cv2.putText(display_frame, label, (x + 5, y - 5), font, font_scale, (0, 0, 0), thickness)
                
                # 점수
                info = f"{score:.2f}"
                cv2.putText(display_frame, info, (x + 5, y + h + 15), font, 0.5, color, 1)
        
        # 프레임 좌상단에 요약 표시
        tracking_count = sum(1 for r in results if r.get("state") == "TRACK")
        status_text = f"Tracking: {tracking_count}/{len(results)}"
        cv2.putText(display_frame, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        cv2.putText(display_frame, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 1)
        
        qimage = cv2_to_qimage(display_frame)
        if qimage is not None:
            pixmap = QPixmap.fromImage(qimage)
            scaled_pixmap = pixmap.scaled(
                self.preview_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.preview_label.setPixmap(scaled_pixmap)
    
    def _update_status_label(self, name: str, state: str):
        """상태 라벨 업데이트"""
        if name not in self.status_labels:
            return
        
        label = self.status_labels[name]
        label.setText(state)
        
        color_map = {
            "IDLE": "#95a5a6",
            "SEARCH": "#f39c12",
            "TRACK": "#27ae60",
            "LOST": "#e74c3c",
            "REACQUIRE": "#f1c40f"
        }
        color = color_map.get(state, "#95a5a6")
        
        label.setStyleSheet(f"""
            background-color: {color};
            color: white;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 10px;
            font-weight: bold;
        """)
    
    def _on_error(self, error_msg: str):
        """에러 발생"""
        logger.error(f"추적 에러: {error_msg}")
        QMessageBox.warning(self, "⚠ 에러", f"추적 중 에러:\n{error_msg}")
    
    def _force_reacquire(self):
        """강제 재탐색"""
        if self.multi_tracker is not None and self.is_tracking:
            self.multi_tracker.force_reacquire()
            logger.info("전체 강제 재탐색")
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
        if self.multi_tracker is not None:
            self.preview_timer.stop()
            self.multi_tracker.stop()
            self.multi_tracker.join(timeout=2.0)
            self.multi_tracker = None
        
        self.is_tracking = False
        self.selected_recipes = []
        
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
            QPushButton:hover { background-color: #229954; }
            QPushButton:pressed { background-color: #1e8449; }
        """)
        
        # 상태 라벨 초기화
        while self.status_container.count():
            item = self.status_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        placeholder = QLabel("추적 시작 시 상태가 표시됩니다")
        placeholder.setStyleSheet("color: #adb5bd; font-style: italic;")
        self.status_container.addWidget(placeholder)
        self.status_labels.clear()
        
        self.preview_label.clear()
        self.preview_label.setText("☑ 템플릿을 체크하고\n▶ 추적 시작 버튼을 누르세요")
        
        logger.info("추적 중지")
