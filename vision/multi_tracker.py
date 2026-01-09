"""
멀티 템플릿 추적 파이프라인
여러 템플릿을 동시에 추적하는 기능
"""
import logging
from queue import Queue, Empty
from threading import Thread, Event
from typing import Optional, Dict, List

import cv2
import numpy as np
from PySide6.QtCore import QObject, Signal

from .recipe import Recipe, RecipeManager
from .tracker_pipeline import TrackerPipeline, TrackingState

logger = logging.getLogger(__name__)


# 추적 색상 팔레트 (BGR)
TRACKING_COLORS = [
    (0, 255, 0),      # 초록
    (255, 0, 0),      # 파랑
    (0, 0, 255),      # 빨강
    (255, 255, 0),    # 청록
    (255, 0, 255),    # 자홍
    (0, 165, 255),    # 주황
    (128, 0, 128),    # 보라
    (0, 255, 255),    # 노랑
    (255, 128, 0),    # 하늘색
    (128, 255, 0),    # 연두
]


class SingleTracker:
    """단일 템플릿 추적기 (스레드 없이)"""
    
    def __init__(self, recipe: Recipe, color: tuple):
        self.recipe = recipe
        self.color = color
        self.state = TrackingState.SEARCH
        
        # ORB 특징점
        self.orb = cv2.ORB_create(nfeatures=2000, scaleFactor=1.2, nlevels=8)
        self.bf_matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
        
        # 템플릿 정보
        self.template_keypoints = None
        self.template_descriptors = None
        self.template_size = (0, 0)
        
        # 추적 결과
        self.current_bbox = None
        self.current_corners = None
        self.tracking_score = 0.0
        
        # 실패 카운터
        self.fail_count = 0
        self.max_fail_count = 5
        
        # 이전 bbox
        self.prev_bbox = None
        
        # 템플릿 특징점 추출
        self._setup_template()
    
    def _setup_template(self):
        """템플릿 특징점 설정"""
        if self.recipe.template_img is not None:
            gray = cv2.cvtColor(self.recipe.template_img, cv2.COLOR_BGR2GRAY) if len(self.recipe.template_img.shape) == 3 else self.recipe.template_img
            self.template_keypoints, self.template_descriptors = self.orb.detectAndCompute(gray, None)
            self.template_size = (self.recipe.template_img.shape[1], self.recipe.template_img.shape[0])
        else:
            self.template_descriptors = self.recipe.descriptors
            if self.recipe.roi:
                self.template_size = (self.recipe.roi[2], self.recipe.roi[3])
    
    def process_frame(self, frame: np.ndarray) -> dict:
        """프레임 처리"""
        result = {
            "name": self.recipe.name,
            "color": self.color,
            "state": self.state.value,
            "bbox": None,
            "corners": None,
            "score": 0.0,
            "matches": 0
        }
        
        if self.template_descriptors is None:
            return result
        
        match_result = self._match_orb_with_homography(frame)
        
        if match_result is not None:
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
        else:
            self.fail_count += 1
            
            if self.current_bbox is not None and self.fail_count < self.max_fail_count:
                result["bbox"] = self.current_bbox
                result["corners"] = self.current_corners
                result["score"] = 0.3
            else:
                if self.fail_count >= self.max_fail_count:
                    self.state = TrackingState.LOST
                    self.current_bbox = None
                    self.prev_bbox = None
        
        result["state"] = self.state.value
        return result
    
    def _match_orb_with_homography(self, frame: np.ndarray) -> Optional[dict]:
        """ORB 매칭 + 호모그래피"""
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            keypoints, descriptors = self.orb.detectAndCompute(gray, None)
            
            if descriptors is None or len(keypoints) < 10:
                return None
            
            matches = self.bf_matcher.knnMatch(self.template_descriptors, descriptors, k=2)
            
            good_matches = []
            for match_pair in matches:
                if len(match_pair) == 2:
                    m, n = match_pair
                    if m.distance < 0.7 * n.distance:
                        good_matches.append(m)
            
            if len(good_matches) < 8:
                return None
            
            if self.template_keypoints is not None:
                src_pts = np.float32([self.template_keypoints[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
            else:
                return None
            
            dst_pts = np.float32([keypoints[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)
            
            H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
            
            if H is None:
                return None
            
            inliers = mask.ravel().sum() if mask is not None else 0
            
            if inliers < 6:
                return None
            
            h, w = self.template_size[1], self.template_size[0]
            corners = np.float32([[0, 0], [w, 0], [w, h], [0, h]]).reshape(-1, 1, 2)
            transformed_corners = cv2.perspectiveTransform(corners, H)
            
            x, y, bw, bh = cv2.boundingRect(transformed_corners.astype(np.int32))
            
            if bw < 20 or bh < 20 or bw > frame.shape[1] * 0.9 or bh > frame.shape[0] * 0.9:
                return None
            
            if x < -50 or y < -50 or x + bw > frame.shape[1] + 50 or y + bh > frame.shape[0] + 50:
                return None
            
            score = min(1.0, inliers / 20.0)
            
            return {
                'bbox': (max(0, x), max(0, y), bw, bh),
                'corners': transformed_corners.reshape(-1, 2).astype(np.int32),
                'score': score,
                'matches': len(good_matches),
                'inliers': inliers
            }
            
        except Exception as e:
            logger.error(f"ORB 매칭 중 예외 ({self.recipe.name}): {e}")
            return None
    
    def _smooth_bbox(self, new_bbox: tuple) -> tuple:
        """bbox 스무딩"""
        if self.prev_bbox is None:
            self.prev_bbox = new_bbox
            return new_bbox
        
        alpha = 0.6
        
        x = int(alpha * new_bbox[0] + (1 - alpha) * self.prev_bbox[0])
        y = int(alpha * new_bbox[1] + (1 - alpha) * self.prev_bbox[1])
        w = int(alpha * new_bbox[2] + (1 - alpha) * self.prev_bbox[2])
        h = int(alpha * new_bbox[3] + (1 - alpha) * self.prev_bbox[3])
        
        smoothed = (x, y, w, h)
        self.prev_bbox = smoothed
        
        return smoothed
    
    def reset(self):
        """추적 상태 초기화"""
        self.state = TrackingState.SEARCH
        self.current_bbox = None
        self.current_corners = None
        self.prev_bbox = None
        self.fail_count = 0


class MultiTrackerPipeline(QObject, Thread):
    """
    멀티 템플릿 추적 파이프라인
    여러 템플릿을 동시에 추적
    """
    
    # Qt 시그널
    frame_processed = Signal(np.ndarray, list)  # (프레임, 추적 결과 리스트)
    state_changed = Signal(str, str)  # (템플릿 이름, 상태)
    error_occurred = Signal(str)
    
    def __init__(self):
        QObject.__init__(self)
        Thread.__init__(self, daemon=True)
        
        self.frame_queue: Queue = Queue(maxsize=2)
        self.stop_event = Event()
        
        self.trackers: List[SingleTracker] = []
        self.recipe_manager = RecipeManager()
    
    def set_recipes(self, recipe_names: List[str]):
        """추적할 레시피들을 설정"""
        self.trackers.clear()
        
        for i, name in enumerate(recipe_names):
            recipe = self.recipe_manager.load_recipe(name)
            if recipe is not None:
                color = TRACKING_COLORS[i % len(TRACKING_COLORS)]
                tracker = SingleTracker(recipe, color)
                self.trackers.append(tracker)
                logger.info(f"트래커 추가: {name} (색상: {color})")
        
        logger.info(f"총 {len(self.trackers)}개 트래커 설정 완료")
    
    def get_tracker_count(self) -> int:
        """트래커 개수 반환"""
        return len(self.trackers)
    
    def put_frame(self, frame: np.ndarray):
        """프레임 큐에 추가"""
        try:
            if self.frame_queue.full():
                try:
                    self.frame_queue.get_nowait()
                except Empty:
                    pass
            
            self.frame_queue.put(frame, block=False)
        except Exception as e:
            logger.warning(f"프레임 큐 추가 실패: {e}")
    
    def force_reacquire(self):
        """모든 트래커 재탐색"""
        for tracker in self.trackers:
            tracker.reset()
        logger.info("모든 트래커 재탐색")
    
    def _process_frame(self, frame: np.ndarray):
        """프레임 처리"""
        results = []
        
        for tracker in self.trackers:
            result = tracker.process_frame(frame)
            results.append(result)
        
        self.frame_processed.emit(frame, results)
    
    def run(self):
        """스레드 메인 루프"""
        logger.info(f"멀티 추적 파이프라인 시작 ({len(self.trackers)}개 트래커)")
        
        while not self.stop_event.is_set():
            try:
                frame = self.frame_queue.get(timeout=0.1)
                self._process_frame(frame)
            except Empty:
                continue
            except Exception as e:
                logger.error(f"파이프라인 루프 예외: {e}")
        
        logger.info("멀티 추적 파이프라인 종료")
    
    def stop(self):
        """스레드 중지"""
        self.stop_event.set()
