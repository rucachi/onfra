"""
추적 파이프라인
ORB 매칭 기반 추적 (CSRT 트래커 optional)
- 호모그래피 기반 정확한 bbox 추정
- 트래커 없이도 작동
"""
import logging
from enum import Enum
from queue import Queue, Empty
from threading import Thread, Event
from typing import Optional

import cv2
import numpy as np
from PySide6.QtCore import QObject, Signal

from .recipe import Recipe
from .utils import MIN_MATCH_COUNT, MATCH_RATIO_THRESHOLD

logger = logging.getLogger(__name__)


class TrackingState(Enum):
    """추적 상태"""
    IDLE = "IDLE"
    SEARCH = "SEARCH"
    TRACK = "TRACK"
    LOST = "LOST"
    REACQUIRE = "REACQUIRE"


class TrackerPipeline(QObject, Thread):
    """
    추적 파이프라인 스레드
    ORB 매칭 기반 추적 (호모그래피 사용)
    """
    
    # Qt 시그널
    frame_processed = Signal(np.ndarray, object)  # (프레임, 추적 결과)
    state_changed = Signal(str)  # 상태 변경
    error_occurred = Signal(str)  # 에러 발생
    
    def __init__(self):
        QObject.__init__(self)
        Thread.__init__(self, daemon=True)
        
        self.frame_queue: Queue = Queue(maxsize=2)
        self.stop_event = Event()
        
        self.recipe: Optional[Recipe] = None
        self.state = TrackingState.IDLE
        
        # ORB 특징점 (더 많은 특징점 추출)
        self.orb = cv2.ORB_create(nfeatures=2000, scaleFactor=1.2, nlevels=8)
        self.bf_matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
        
        # 템플릿 정보
        self.template_keypoints = None
        self.template_descriptors = None
        self.template_size = (0, 0)
        
        # 추적 결과
        self.current_bbox: Optional[tuple[int, int, int, int]] = None
        self.current_corners = None  # 변환된 4개 모서리
        self.tracking_score = 0.0
        
        # 실패 카운터
        self.fail_count = 0
        self.max_fail_count = 5
        
        # 이전 bbox (스무딩용)
        self.prev_bbox = None
        
    def set_recipe(self, recipe: Recipe):
        """추적할 레시피를 설정합니다."""
        self.recipe = recipe
        self.state = TrackingState.SEARCH
        self.current_bbox = None
        self.prev_bbox = None
        self.fail_count = 0
        
        # 템플릿 특징점 추출
        if recipe.template_img is not None:
            gray = cv2.cvtColor(recipe.template_img, cv2.COLOR_BGR2GRAY) if len(recipe.template_img.shape) == 3 else recipe.template_img
            self.template_keypoints, self.template_descriptors = self.orb.detectAndCompute(gray, None)
            self.template_size = (recipe.template_img.shape[1], recipe.template_img.shape[0])
            logger.info(f"템플릿 특징점: {len(self.template_keypoints) if self.template_keypoints else 0}개")
        else:
            self.template_descriptors = recipe.descriptors
            if recipe.roi:
                self.template_size = (recipe.roi[2], recipe.roi[3])
        
        self.state_changed.emit(self.state.value)
        logger.info(f"레시피 설정: {recipe.name}")
    
    def force_reacquire(self):
        """강제로 재탐색 모드로 전환합니다."""
        self.state = TrackingState.REACQUIRE
        self.current_bbox = None
        self.prev_bbox = None
        self.fail_count = 0
        self.state_changed.emit(self.state.value)
        logger.info("강제 재탐색")
    
    def put_frame(self, frame: np.ndarray):
        """처리할 프레임을 큐에 넣습니다."""
        try:
            if self.frame_queue.full():
                try:
                    self.frame_queue.get_nowait()
                except Empty:
                    pass
            
            self.frame_queue.put(frame, block=False)
        except Exception as e:
            logger.warning(f"프레임 큐 추가 실패: {e}")
    
    def _match_orb_with_homography(self, frame: np.ndarray) -> Optional[dict]:
        """
        ORB 특징점 매칭 + 호모그래피로 정확한 위치 추정
        
        Returns:
            dict: {'bbox': (x,y,w,h), 'corners': 4개 모서리, 'score': 매칭 점수}
        """
        if self.template_descriptors is None:
            return None
        
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            keypoints, descriptors = self.orb.detectAndCompute(gray, None)
            
            if descriptors is None or len(keypoints) < 10:
                return None
            
            # BFMatcher로 매칭 (knnMatch)
            matches = self.bf_matcher.knnMatch(self.template_descriptors, descriptors, k=2)
            
            # Lowe's ratio test
            good_matches = []
            for match_pair in matches:
                if len(match_pair) == 2:
                    m, n = match_pair
                    if m.distance < 0.7 * n.distance:  # 더 엄격한 threshold
                        good_matches.append(m)
            
            match_count = len(good_matches)
            
            if match_count < 8:  # 호모그래피에 최소 4점 필요
                return None
            
            # 매칭된 점들 추출
            if self.template_keypoints is not None:
                src_pts = np.float32([self.template_keypoints[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
            else:
                # 템플릿 키포인트가 없으면 균등 분포 가정
                return self._match_orb_simple(frame, keypoints, good_matches)
            
            dst_pts = np.float32([keypoints[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)
            
            # 호모그래피 계산
            H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
            
            if H is None:
                return self._match_orb_simple(frame, keypoints, good_matches)
            
            # 인라이어 개수
            inliers = mask.ravel().sum() if mask is not None else 0
            
            if inliers < 6:
                return self._match_orb_simple(frame, keypoints, good_matches)
            
            # 템플릿 모서리를 현재 프레임으로 변환
            h, w = self.template_size[1], self.template_size[0]
            corners = np.float32([[0, 0], [w, 0], [w, h], [0, h]]).reshape(-1, 1, 2)
            transformed_corners = cv2.perspectiveTransform(corners, H)
            
            # 바운딩 박스 계산
            x, y, bw, bh = cv2.boundingRect(transformed_corners.astype(np.int32))
            
            # 유효성 검사
            if bw < 20 or bh < 20 or bw > frame.shape[1] * 0.9 or bh > frame.shape[0] * 0.9:
                return None
            
            if x < -50 or y < -50 or x + bw > frame.shape[1] + 50 or y + bh > frame.shape[0] + 50:
                return None
            
            # 스코어 계산
            score = min(1.0, inliers / 20.0)
            
            return {
                'bbox': (max(0, x), max(0, y), bw, bh),
                'corners': transformed_corners.reshape(-1, 2).astype(np.int32),
                'score': score,
                'matches': match_count,
                'inliers': inliers
            }
            
        except Exception as e:
            logger.error(f"ORB 매칭 중 예외: {e}")
            return None
    
    def _match_orb_simple(self, frame: np.ndarray, keypoints, good_matches) -> Optional[dict]:
        """간단한 bbox 추정 (호모그래피 실패 시 fallback)"""
        try:
            matched_pts = np.float32([keypoints[m.trainIdx].pt for m in good_matches])
            
            if len(matched_pts) < 4:
                return None
            
            x, y, w, h = cv2.boundingRect(matched_pts.astype(np.int32))
            
            # 템플릿 크기를 참고하여 bbox 보정
            if self.template_size[0] > 0 and self.template_size[1] > 0:
                # 매칭된 점들의 중심
                cx = x + w // 2
                cy = y + h // 2
                
                # 템플릿 비율 유지
                scale = max(w / self.template_size[0], h / self.template_size[1])
                new_w = int(self.template_size[0] * scale * 1.2)  # 약간 여유
                new_h = int(self.template_size[1] * scale * 1.2)
                
                x = max(0, cx - new_w // 2)
                y = max(0, cy - new_h // 2)
                w, h = new_w, new_h
            
            # 유효성 검사
            if w < 20 or h < 20 or w > frame.shape[1] or h > frame.shape[0]:
                return None
            
            score = min(1.0, len(good_matches) / 30.0)
            
            return {
                'bbox': (x, y, w, h),
                'corners': None,
                'score': score,
                'matches': len(good_matches),
                'inliers': 0
            }
            
        except Exception as e:
            logger.error(f"간단 매칭 중 예외: {e}")
            return None
    
    def _smooth_bbox(self, new_bbox: tuple) -> tuple:
        """bbox 스무딩 (떨림 감소)"""
        if self.prev_bbox is None:
            self.prev_bbox = new_bbox
            return new_bbox
        
        alpha = 0.6  # 새 값의 가중치
        
        x = int(alpha * new_bbox[0] + (1 - alpha) * self.prev_bbox[0])
        y = int(alpha * new_bbox[1] + (1 - alpha) * self.prev_bbox[1])
        w = int(alpha * new_bbox[2] + (1 - alpha) * self.prev_bbox[2])
        h = int(alpha * new_bbox[3] + (1 - alpha) * self.prev_bbox[3])
        
        smoothed = (x, y, w, h)
        self.prev_bbox = smoothed
        
        return smoothed
    
    def _process_frame(self, frame: np.ndarray):
        """프레임을 처리합니다 (상태 머신)."""
        result = {
            "state": self.state.value,
            "bbox": None,
            "corners": None,
            "score": 0.0,
            "matches": 0
        }
        
        try:
            if self.state == TrackingState.IDLE:
                pass
            
            elif self.state in (TrackingState.SEARCH, TrackingState.REACQUIRE, TrackingState.TRACK):
                # ORB 매칭으로 위치 찾기
                match_result = self._match_orb_with_homography(frame)
                
                if match_result is not None:
                    # 스무딩 적용
                    smoothed_bbox = self._smooth_bbox(match_result['bbox'])
                    
                    result["bbox"] = smoothed_bbox
                    result["corners"] = match_result.get('corners')
                    result["score"] = match_result['score']
                    result["matches"] = match_result.get('matches', 0)
                    
                    self.current_bbox = smoothed_bbox
                    self.current_corners = match_result.get('corners')
                    self.fail_count = 0
                    
                    if self.state != TrackingState.TRACK:
                        self.state = TrackingState.TRACK
                        self.state_changed.emit(self.state.value)
                else:
                    self.fail_count += 1
                    
                    # 이전 bbox 사용 (일시적 실패)
                    if self.current_bbox is not None and self.fail_count < self.max_fail_count:
                        result["bbox"] = self.current_bbox
                        result["corners"] = self.current_corners
                        result["score"] = 0.3
                    else:
                        if self.fail_count >= self.max_fail_count:
                            self.state = TrackingState.LOST
                            self.state_changed.emit(self.state.value)
                            self.current_bbox = None
                            self.prev_bbox = None
            
            elif self.state == TrackingState.LOST:
                # 자동으로 재탐색
                self.state = TrackingState.REACQUIRE
                self.state_changed.emit(self.state.value)
            
            result["state"] = self.state.value
            self.frame_processed.emit(frame, result)
            
        except Exception as e:
            logger.error(f"프레임 처리 중 예외: {e}")
            self.error_occurred.emit(str(e))
    
    def run(self):
        """스레드 메인 루프"""
        logger.info("추적 파이프라인 시작")
        
        while not self.stop_event.is_set():
            try:
                frame = self.frame_queue.get(timeout=0.1)
                self._process_frame(frame)
            except Empty:
                continue
            except Exception as e:
                logger.error(f"파이프라인 루프 예외: {e}")
        
        logger.info("추적 파이프라인 종료")
    
    def stop(self):
        """스레드를 중지합니다."""
        self.stop_event.set()
