"""
비전 처리 유틸리티 함수
OpenCV 이미지를 Qt 이미지로 변환 등
"""
import logging
from typing import Optional

import cv2
import numpy as np
from PySide6.QtGui import QImage

logger = logging.getLogger(__name__)


def cv2_to_qimage(cv_img: np.ndarray) -> Optional[QImage]:
    """
    OpenCV 이미지(BGR)를 QImage(RGB)로 변환합니다.
    
    Args:
        cv_img: OpenCV 이미지 (numpy array)
        
    Returns:
        QImage: 변환된 Qt 이미지, 실패 시 None
    """
    try:
        if cv_img is None or cv_img.size == 0:
            return None
        
        # BGR to RGB
        rgb_img = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_img.shape
        bytes_per_line = ch * w
        
        qimage = QImage(rgb_img.data, w, h, bytes_per_line, QImage.Format_RGB888)
        
        # 데이터 복사 (원본 numpy 배열이 삭제되어도 안전)
        return qimage.copy()
        
    except Exception as e:
        logger.error(f"cv2_to_qimage 변환 실패: {e}")
        return None


def draw_bbox(
    img: np.ndarray,
    bbox: tuple[int, int, int, int],
    label: str = "",
    color: tuple[int, int, int] = (0, 255, 0),
    thickness: int = 2
) -> np.ndarray:
    """
    이미지에 바운딩 박스를 그립니다.
    
    Args:
        img: 입력 이미지
        bbox: (x, y, w, h) 형식의 바운딩 박스
        label: 표시할 레이블
        color: BGR 색상
        thickness: 선 두께
        
    Returns:
        np.ndarray: 박스가 그려진 이미지
    """
    x, y, w, h = bbox
    img_copy = img.copy()
    
    # 바운딩 박스
    cv2.rectangle(img_copy, (x, y), (x + w, y + h), color, thickness)
    
    # 중심점
    cx, cy = x + w // 2, y + h // 2
    cv2.circle(img_copy, (cx, cy), 5, color, -1)
    
    # 레이블
    if label:
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.6
        font_thickness = 2
        
        # 텍스트 배경
        (text_w, text_h), _ = cv2.getTextSize(label, font, font_scale, font_thickness)
        cv2.rectangle(img_copy, (x, y - text_h - 10), (x + text_w, y), color, -1)
        
        # 텍스트
        cv2.putText(img_copy, label, (x, y - 5), font, font_scale, (0, 0, 0), font_thickness)
    
    return img_copy


def calculate_iou(bbox1: tuple[int, int, int, int], bbox2: tuple[int, int, int, int]) -> float:
    """
    두 바운딩 박스의 IoU(Intersection over Union)를 계산합니다.
    
    Args:
        bbox1: (x, y, w, h)
        bbox2: (x, y, w, h)
        
    Returns:
        float: IoU 값 (0.0 ~ 1.0)
    """
    x1, y1, w1, h1 = bbox1
    x2, y2, w2, h2 = bbox2
    
    # 교집합 영역
    xi1 = max(x1, x2)
    yi1 = max(y1, y2)
    xi2 = min(x1 + w1, x2 + w2)
    yi2 = min(y1 + h1, y2 + h2)
    
    inter_area = max(0, xi2 - xi1) * max(0, yi2 - yi1)
    
    # 합집합 영역
    box1_area = w1 * h1
    box2_area = w2 * h2
    union_area = box1_area + box2_area - inter_area
    
    if union_area == 0:
        return 0.0
    
    return inter_area / union_area


# 상수
MIN_MATCH_COUNT = 10  # ORB 매칭 최소 개수
MATCH_RATIO_THRESHOLD = 0.75  # Lowe's ratio test 임계값
TRACKER_CONFIDENCE_THRESHOLD = 0.3  # 트래커 신뢰도 임계값
