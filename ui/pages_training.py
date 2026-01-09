"""
학습(Training) 페이지
ROI 선택, 템플릿 등록, 레시피 관리
- 단계별 가이드로 사용자 친화적 UI
"""
import logging
from typing import Optional

import cv2
import numpy as np
from PySide6.QtCore import Qt, QTimer, QRect, QPoint
from PySide6.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit, QListWidget,
    QGroupBox, QMessageBox, QFrame, QSplitter
)

from vision.recipe import RecipeManager, Recipe
from vision.utils import cv2_to_qimage

logger = logging.getLogger(__name__)


class ROISelector(QLabel):
    """ROI 선택 위젯 (마우스 드래그)"""
    
    def __init__(self):
        super().__init__()
        
        self.start_point: Optional[QPoint] = None
        self.end_point: Optional[QPoint] = None
        self.is_selecting = False
        
        self.current_pixmap: Optional[QPixmap] = None
        self.image_offset = QPoint(0, 0)
        self.scale_factor = 1.0
        
        self.setMouseTracking(True)
        self.setMinimumSize(640, 480)
        self.setStyleSheet("""
            QLabel {
                background-color: #1a1a2e;
                border: 3px solid #16213e;
                border-radius: 12px;
            }
        """)
    
    def set_image(self, pixmap: QPixmap):
        """이미지 설정"""
        self.current_pixmap = pixmap
        self._calculate_scale()
        self.update()
    
    def _calculate_scale(self):
        """스케일 계산"""
        if self.current_pixmap is None:
            return
        
        # 이미지를 위젯 크기에 맞게 스케일
        img_w, img_h = self.current_pixmap.width(), self.current_pixmap.height()
        widget_w, widget_h = self.width() - 20, self.height() - 20  # 여백
        
        scale_w = widget_w / img_w
        scale_h = widget_h / img_h
        self.scale_factor = min(scale_w, scale_h)
        
        scaled_w = int(img_w * self.scale_factor)
        scaled_h = int(img_h * self.scale_factor)
        
        self.image_offset = QPoint(
            (self.width() - scaled_w) // 2,
            (self.height() - scaled_h) // 2
        )
    
    def get_roi(self) -> Optional[tuple[int, int, int, int]]:
        """선택된 ROI 반환 (원본 이미지 좌표)"""
        if self.start_point is None or self.end_point is None:
            return None
        
        # 화면 좌표를 원본 이미지 좌표로 변환
        x1 = int((min(self.start_point.x(), self.end_point.x()) - self.image_offset.x()) / self.scale_factor)
        y1 = int((min(self.start_point.y(), self.end_point.y()) - self.image_offset.y()) / self.scale_factor)
        x2 = int((max(self.start_point.x(), self.end_point.x()) - self.image_offset.x()) / self.scale_factor)
        y2 = int((max(self.start_point.y(), self.end_point.y()) - self.image_offset.y()) / self.scale_factor)
        
        w = x2 - x1
        h = y2 - y1
        
        if w < 20 or h < 20:
            return None
        
        return (max(0, x1), max(0, y1), w, h)
    
    def clear_roi(self):
        """ROI 초기화"""
        self.start_point = None
        self.end_point = None
        self.is_selecting = False
        self.update()
    
    def mousePressEvent(self, event):
        """마우스 누름"""
        if event.button() == Qt.LeftButton:
            self.start_point = event.pos()
            self.end_point = event.pos()
            self.is_selecting = True
    
    def mouseMoveEvent(self, event):
        """마우스 이동"""
        if self.is_selecting:
            self.end_point = event.pos()
            self.update()
    
    def mouseReleaseEvent(self, event):
        """마우스 뗌"""
        if event.button() == Qt.LeftButton:
            self.is_selecting = False
            self.update()
    
    def paintEvent(self, event):
        """그리기"""
        super().paintEvent(event)
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 이미지 그리기
        if self.current_pixmap is not None:
            self._calculate_scale()
            scaled_pixmap = self.current_pixmap.scaled(
                int(self.current_pixmap.width() * self.scale_factor),
                int(self.current_pixmap.height() * self.scale_factor),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            painter.drawPixmap(self.image_offset, scaled_pixmap)
        else:
            # 카메라 연결 안내
            painter.setPen(QPen(QColor("#7f8c8d"), 2))
            font = QFont("Arial", 14)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignCenter, "📷 먼저 Camera Settings에서\n카메라를 연결하세요")
        
        # ROI 박스 그리기
        if self.start_point is not None and self.end_point is not None:
            # 반투명 오버레이
            overlay_color = QColor(46, 204, 113, 80)
            painter.fillRect(QRect(self.start_point, self.end_point), overlay_color)
            
            # 테두리
            pen = QPen(QColor("#2ecc71"), 3, Qt.SolidLine)
            painter.setPen(pen)
            rect = QRect(self.start_point, self.end_point)
            painter.drawRect(rect)
            
            # 크기 표시
            roi = self.get_roi()
            if roi:
                x, y, w, h = roi
                size_text = f"{w} x {h}"
                painter.setPen(QPen(QColor("#ffffff")))
                font = QFont("Arial", 10, QFont.Bold)
                painter.setFont(font)
                painter.drawText(rect.bottomRight() + QPoint(-60, 20), size_text)
        
        painter.end()
    
    def resizeEvent(self, event):
        """크기 변경 시"""
        super().resizeEvent(event)
        self._calculate_scale()


class StepIndicator(QWidget):
    """단계 표시기"""
    
    def __init__(self, step_number: int, title: str, description: str):
        super().__init__()
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        
        # 단계 번호
        self.number_label = QLabel(str(step_number))
        self.number_label.setFixedSize(36, 36)
        self.number_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.number_label)
        
        # 텍스트
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #2c3e50;")
        text_layout.addWidget(self.title_label)
        
        self.desc_label = QLabel(description)
        self.desc_label.setStyleSheet("font-size: 11px; color: #7f8c8d;")
        self.desc_label.setWordWrap(True)
        text_layout.addWidget(self.desc_label)
        
        layout.addLayout(text_layout, stretch=1)
        
        # 라벨 생성 후 스타일 설정
        self.set_inactive()
    
    def set_active(self):
        """활성 상태"""
        self.number_label.setStyleSheet("""
            QLabel {
                background-color: #3498db;
                color: white;
                border-radius: 18px;
                font-weight: bold;
                font-size: 16px;
            }
        """)
        self.title_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #3498db;")
    
    def set_complete(self):
        """완료 상태"""
        self.number_label.setText("✓")
        self.number_label.setStyleSheet("""
            QLabel {
                background-color: #27ae60;
                color: white;
                border-radius: 18px;
                font-weight: bold;
                font-size: 16px;
            }
        """)
        self.title_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #27ae60;")
    
    def set_inactive(self):
        """비활성 상태"""
        self.number_label.setStyleSheet("""
            QLabel {
                background-color: #bdc3c7;
                color: white;
                border-radius: 18px;
                font-weight: bold;
                font-size: 16px;
            }
        """)
        self.title_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #95a5a6;")


class TrainingPage(QWidget):
    """학습 페이지 - 단계별 가이드"""
    
    def __init__(self):
        super().__init__()
        
        self.recipe_manager = RecipeManager()
        self.current_frame: Optional[np.ndarray] = None
        self.current_recipe: Optional[Recipe] = None
        self.current_step = 1
        
        self._setup_ui()
        
        # 프리뷰 타이머
        self.preview_timer = QTimer()
        self.preview_timer.timeout.connect(self._update_preview)
        self.preview_timer.start(33)
    
    def _setup_ui(self):
        """UI 구성"""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        # ===== 좌측: 단계 가이드 + 입력 =====
        left_panel = QFrame()
        left_panel.setFixedWidth(320)
        left_panel.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border-radius: 12px;
            }
        """)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(15, 15, 15, 15)
        left_layout.setSpacing(12)
        
        # 제목
        title = QLabel("🎯 템플릿 학습")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #2c3e50;")
        left_layout.addWidget(title)
        
        # 단계 표시기
        steps_frame = QFrame()
        steps_frame.setStyleSheet("background-color: white; border-radius: 8px;")
        steps_layout = QVBoxLayout(steps_frame)
        steps_layout.setSpacing(0)
        
        self.step1 = StepIndicator(1, "영역 선택", "추적할 물체를 드래그하세요")
        self.step2 = StepIndicator(2, "이름 입력", "템플릿 이름을 입력하세요")
        self.step3 = StepIndicator(3, "학습 완료", "저장 버튼을 눌러 저장하세요")
        
        steps_layout.addWidget(self.step1)
        steps_layout.addWidget(self.step2)
        steps_layout.addWidget(self.step3)
        
        left_layout.addWidget(steps_frame)
        
        # 구분선
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet("background-color: #dee2e6;")
        separator.setFixedHeight(1)
        left_layout.addWidget(separator)
        
        # 입력 영역
        input_frame = QFrame()
        input_frame.setStyleSheet("background-color: white; border-radius: 8px; padding: 10px;")
        input_layout = QVBoxLayout(input_frame)
        
        # 템플릿 이름
        name_label = QLabel("📝 템플릿 이름")
        name_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        input_layout.addWidget(name_label)
        
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("예: product_box, target_01")
        self.name_edit.setStyleSheet("""
            QLineEdit {
                padding: 12px;
                border: 2px solid #e9ecef;
                border-radius: 8px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #3498db;
            }
        """)
        self.name_edit.textChanged.connect(self._on_name_changed)
        input_layout.addWidget(self.name_edit)
        
        # 메모 (선택)
        notes_label = QLabel("💬 메모 (선택)")
        notes_label.setStyleSheet("font-weight: bold; color: #2c3e50; margin-top: 10px;")
        input_layout.addWidget(notes_label)
        
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("추가 설명...")
        self.notes_edit.setMaximumHeight(60)
        self.notes_edit.setStyleSheet("""
            QTextEdit {
                padding: 8px;
                border: 2px solid #e9ecef;
                border-radius: 8px;
                font-size: 12px;
            }
        """)
        input_layout.addWidget(self.notes_edit)
        
        left_layout.addWidget(input_frame)
        
        # 버튼 영역
        btn_frame = QFrame()
        btn_layout = QVBoxLayout(btn_frame)
        btn_layout.setSpacing(10)
        
        self.btn_train = QPushButton("🎯 학습하기")
        self.btn_train.clicked.connect(self._train_template)
        self.btn_train.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                padding: 14px;
                border-radius: 8px;
                font-weight: bold;
                font-size: 15px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #1f618d;
                padding-top: 16px;
                padding-bottom: 12px;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """)
        btn_layout.addWidget(self.btn_train)
        
        self.btn_save = QPushButton("💾 저장하기")
        self.btn_save.clicked.connect(self._save_recipe)
        self.btn_save.setEnabled(False)
        self.btn_save.setStyleSheet("""
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
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """)
        btn_layout.addWidget(self.btn_save)
        
        btn_clear = QPushButton("🔄 초기화")
        btn_clear.clicked.connect(self._clear_all)
        btn_clear.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                padding: 10px;
                border-radius: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:pressed {
                background-color: #a93226;
                padding-top: 12px;
                padding-bottom: 8px;
            }
        """)
        btn_layout.addWidget(btn_clear)
        
        left_layout.addWidget(btn_frame)
        
        # 품질 표시
        self.quality_frame = QFrame()
        self.quality_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        self.quality_frame.hide()
        quality_layout = QVBoxLayout(self.quality_frame)
        
        quality_title = QLabel("📊 품질 정보")
        quality_title.setStyleSheet("font-weight: bold; color: #2c3e50;")
        quality_layout.addWidget(quality_title)
        
        self.quality_label = QLabel("")
        self.quality_label.setWordWrap(True)
        self.quality_label.setStyleSheet("color: #34495e; font-size: 12px;")
        quality_layout.addWidget(self.quality_label)
        
        left_layout.addWidget(self.quality_frame)
        
        left_layout.addStretch()
        
        main_layout.addWidget(left_panel)
        
        # ===== 중앙: 프리뷰 =====
        center_panel = QFrame()
        center_panel.setStyleSheet("""
            QFrame {
                background-color: #1a1a2e;
                border-radius: 12px;
            }
        """)
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(10, 10, 10, 10)
        
        preview_title = QLabel("👁 실시간 프리뷰 - 마우스로 드래그하여 영역 선택")
        preview_title.setStyleSheet("color: #ecf0f1; font-weight: bold; font-size: 13px;")
        preview_title.setAlignment(Qt.AlignCenter)
        center_layout.addWidget(preview_title)
        
        self.roi_selector = ROISelector()
        center_layout.addWidget(self.roi_selector, stretch=1)
        
        main_layout.addWidget(center_panel, stretch=2)
        
        # ===== 우측: 저장된 레시피 =====
        right_panel = QFrame()
        right_panel.setFixedWidth(220)
        right_panel.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border-radius: 12px;
            }
        """)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(15, 15, 15, 15)
        
        recipe_title = QLabel("📁 저장된 템플릿")
        recipe_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50;")
        right_layout.addWidget(recipe_title)
        
        self.recipe_list = QListWidget()
        self.recipe_list.setStyleSheet("""
            QListWidget {
                background-color: white;
                border: 2px solid #e9ecef;
                border-radius: 8px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 10px;
                border-radius: 5px;
            }
            QListWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
            QListWidget::item:hover {
                background-color: #ecf0f1;
            }
        """)
        self.recipe_list.itemClicked.connect(self._on_recipe_selected)
        right_layout.addWidget(self.recipe_list, stretch=1)
        
        btn_refresh = QPushButton("🔄 새로고침")
        btn_refresh.clicked.connect(self._refresh_recipe_list)
        btn_refresh.setStyleSheet("""
            QPushButton {
                padding: 8px;
                border-radius: 6px;
                background-color: #3498db;
                color: white;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #1f618d;
                padding-top: 10px;
                padding-bottom: 6px;
            }
        """)
        right_layout.addWidget(btn_refresh)
        
        btn_delete = QPushButton("🗑 삭제")
        btn_delete.clicked.connect(self._delete_recipe)
        btn_delete.setStyleSheet("""
            QPushButton {
                padding: 8px;
                border-radius: 6px;
                background-color: #e74c3c;
                color: white;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:pressed {
                background-color: #a93226;
                padding-top: 10px;
                padding-bottom: 6px;
            }
        """)
        right_layout.addWidget(btn_delete)
        
        main_layout.addWidget(right_panel)
        
        # 초기 상태 설정
        self._update_step(1)
        self._refresh_recipe_list()
    
    def _update_step(self, step: int):
        """단계 업데이트"""
        self.current_step = step
        
        # 모든 단계 비활성화
        self.step1.set_inactive()
        self.step2.set_inactive()
        self.step3.set_inactive()
        
        # 현재까지의 단계 표시
        if step >= 1:
            self.step1.set_active()
        if step >= 2:
            self.step1.set_complete()
            self.step2.set_active()
        if step >= 3:
            self.step2.set_complete()
            self.step3.set_active()
    
    def _on_name_changed(self, text: str):
        """이름 입력 시"""
        if text.strip() and self.roi_selector.get_roi():
            self._update_step(2)
    
    def _update_preview(self):
        """프리뷰 업데이트"""
        main_window = self.window()
        if hasattr(main_window, 'camera_page'):
            camera_thread = main_window.camera_page.get_camera_thread()
            
            if camera_thread is not None:
                frame = camera_thread.get_frame(timeout=0.1)
                
                if frame is not None:
                    self.current_frame = frame.copy()
                    qimage = cv2_to_qimage(frame)
                    
                    if qimage is not None:
                        pixmap = QPixmap.fromImage(qimage)
                        self.roi_selector.set_image(pixmap)
    
    def _train_template(self):
        """템플릿 학습"""
        if self.current_frame is None:
            QMessageBox.warning(self, "⚠ 카메라 필요", 
                "먼저 Camera Settings 페이지에서\n카메라를 연결해주세요.")
            return
        
        roi = self.roi_selector.get_roi()
        if roi is None:
            QMessageBox.warning(self, "⚠ 영역 선택 필요", 
                "프리뷰 화면에서 마우스를 드래그하여\n추적할 물체의 영역을 선택해주세요.")
            return
        
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "⚠ 이름 필요", 
                "템플릿 이름을 입력해주세요.\n예: product_box, target_01")
            self.name_edit.setFocus()
            return
        
        # ROI 이미지 추출
        x, y, w, h = roi
        
        # 범위 검사
        frame_h, frame_w = self.current_frame.shape[:2]
        x = max(0, min(x, frame_w - 1))
        y = max(0, min(y, frame_h - 1))
        w = min(w, frame_w - x)
        h = min(h, frame_h - y)
        
        if w < 20 or h < 20:
            QMessageBox.warning(self, "⚠ 영역이 너무 작음", 
                "선택한 영역이 너무 작습니다.\n더 큰 영역을 선택해주세요.")
            return
        
        roi_img = self.current_frame[y:y+h, x:x+w]
        
        # 레시피 생성
        notes = self.notes_edit.toPlainText()
        recipe = self.recipe_manager.create_recipe(name, roi_img, (x, y, w, h), notes)
        
        if recipe is None:
            QMessageBox.critical(self, "❌ 학습 실패", 
                "특징점을 충분히 찾을 수 없습니다.\n\n" +
                "해결 방법:\n" +
                "• 텍스처가 풍부한 영역 선택\n" +
                "• 조명 조건 개선\n" +
                "• 더 큰 영역 선택")
            return
        
        # 품질 표시
        quality_icon = "✅" if recipe.keypoint_count >= 30 else "⚠"
        quality_text = f"""
{quality_icon} 키포인트: {recipe.keypoint_count}개
📐 크기: {w} x {h} 픽셀
🕐 생성: {recipe.created_at[:19]}
        """
        
        if recipe.keypoint_count < 30:
            quality_text += "\n⚠ 키포인트가 적습니다 (30개 이상 권장)"
        
        self.quality_label.setText(quality_text.strip())
        self.quality_frame.show()
        
        # 상태 업데이트
        self.current_recipe = recipe
        self.btn_save.setEnabled(True)
        self._update_step(3)
        
        QMessageBox.information(self, "✅ 학습 완료!", 
            f"템플릿 '{name}' 학습 완료!\n\n" +
            f"키포인트: {recipe.keypoint_count}개\n\n" +
            "저장 버튼을 눌러 저장하세요.")
        
        logger.info(f"템플릿 학습 완료: {name} (키포인트: {recipe.keypoint_count})")
    
    def _save_recipe(self):
        """레시피 저장"""
        if self.current_recipe is None:
            return
        
        if self.recipe_manager.save_recipe(self.current_recipe):
            QMessageBox.information(self, "✅ 저장 완료", 
                f"템플릿 '{self.current_recipe.name}'이(가) 저장되었습니다!\n\n" +
                "이제 Observation 페이지에서 사용할 수 있습니다.")
            self._refresh_recipe_list()
            self._clear_all()
        else:
            QMessageBox.critical(self, "❌ 저장 실패", "레시피 저장에 실패했습니다.")
    
    def _clear_all(self):
        """모든 입력 초기화"""
        self.name_edit.clear()
        self.notes_edit.clear()
        self.roi_selector.clear_roi()
        self.current_recipe = None
        self.btn_save.setEnabled(False)
        self.quality_frame.hide()
        self._update_step(1)
    
    def _refresh_recipe_list(self):
        """레시피 목록 새로고침"""
        self.recipe_list.clear()
        recipes = self.recipe_manager.list_recipes()
        for name in recipes:
            self.recipe_list.addItem(f"📦 {name}")
        logger.info(f"레시피 목록: {len(recipes)}개")
    
    def _on_recipe_selected(self, item):
        """레시피 선택"""
        recipe_name = item.text().replace("📦 ", "")
        recipe = self.recipe_manager.load_recipe(recipe_name)
        
        if recipe is not None:
            self.quality_label.setText(
                f"📦 {recipe.name}\n"
                f"🔑 키포인트: {recipe.keypoint_count}개\n"
                f"📐 ROI: {recipe.roi}\n"
                f"🕐 생성: {recipe.created_at[:19]}\n"
                f"💬 {recipe.notes or '(메모 없음)'}"
            )
            self.quality_frame.show()
    
    def _delete_recipe(self):
        """레시피 삭제"""
        current_item = self.recipe_list.currentItem()
        
        if current_item is None:
            QMessageBox.warning(self, "⚠ 선택 필요", "삭제할 레시피를 선택하세요.")
            return
        
        recipe_name = current_item.text().replace("📦 ", "")
        
        reply = QMessageBox.question(
            self, "🗑 삭제 확인",
            f"템플릿 '{recipe_name}'을(를) 삭제하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if self.recipe_manager.delete_recipe(recipe_name):
                QMessageBox.information(self, "✅ 삭제 완료", "템플릿이 삭제되었습니다.")
                self._refresh_recipe_list()
                self.quality_frame.hide()
            else:
                QMessageBox.critical(self, "❌ 삭제 실패", "템플릿 삭제에 실패했습니다.")
