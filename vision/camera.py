"""
카메라 캡처 스레드
별도 스레드에서 프레임을 읽어 큐에 전달
"""
import logging
import time
from queue import Queue, Full
from threading import Thread, Event
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class CameraThread(Thread):
    """
    카메라 프레임 캡처 전용 스레드
    프레임을 읽어서 큐에 넣고, 큐가 꽉 차면 오래된 프레임을 버립니다.
    """
    
    def __init__(self, camera_index: int = 0, queue_size: int = 2):
        """
        Args:
            camera_index: 카메라 인덱스 (0, 1, 2, ...)
            queue_size: 프레임 큐 크기 (작을수록 지연 감소)
        """
        super().__init__(daemon=True)
        self.camera_index = camera_index
        self.queue_size = queue_size
        
        self.frame_queue: Queue = Queue(maxsize=queue_size)
        self.stop_event = Event()
        
        self.cap: Optional[cv2.VideoCapture] = None
        self.is_opened = False
        
        # 카메라 설정
        self.width: Optional[int] = None
        self.height: Optional[int] = None
        self.fps: Optional[int] = None
        self.exposure: Optional[float] = None
        self.gain: Optional[float] = None
        
    def open_camera(self) -> bool:
        """
        카메라를 엽니다.
        
        Returns:
            bool: 성공 여부
        """
        try:
            self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
            
            if not self.cap.isOpened():
                logger.error(f"카메라 {self.camera_index} 열기 실패")
                return False
            
            self.is_opened = True
            logger.info(f"카메라 {self.camera_index} 열기 성공")
            
            # 기본 설정 읽기
            self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.fps = int(self.cap.get(cv2.CAP_PROP_FPS))
            
            return True
            
        except Exception as e:
            logger.error(f"카메라 열기 중 예외: {e}")
            return False
    
    def close_camera(self):
        """카메라를 닫습니다."""
        if self.cap is not None:
            self.cap.release()
            self.is_opened = False
            logger.info(f"카메라 {self.camera_index} 닫기")
    
    def set_resolution(self, width: int, height: int) -> bool:
        """
        해상도를 설정합니다.
        
        Args:
            width: 너비
            height: 높이
            
        Returns:
            bool: 성공 여부
        """
        if not self.is_opened:
            return False
        
        try:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            
            # 실제 설정된 값 확인
            actual_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            self.width = actual_w
            self.height = actual_h
            
            logger.info(f"해상도 설정: {actual_w}x{actual_h}")
            return True
            
        except Exception as e:
            logger.error(f"해상도 설정 실패: {e}")
            return False
    
    def set_fps(self, fps: int) -> bool:
        """FPS를 설정합니다."""
        if not self.is_opened:
            return False
        
        try:
            self.cap.set(cv2.CAP_PROP_FPS, fps)
            actual_fps = int(self.cap.get(cv2.CAP_PROP_FPS))
            self.fps = actual_fps
            logger.info(f"FPS 설정: {actual_fps}")
            return True
        except Exception as e:
            logger.error(f"FPS 설정 실패: {e}")
            return False
    
    def set_exposure(self, exposure: float) -> bool:
        """노출을 설정합니다."""
        if not self.is_opened:
            return False
        
        try:
            self.cap.set(cv2.CAP_PROP_EXPOSURE, exposure)
            self.exposure = exposure
            logger.info(f"노출 설정: {exposure}")
            return True
        except Exception as e:
            logger.warning(f"노출 설정 실패 (미지원 가능): {e}")
            return False
    
    def set_gain(self, gain: float) -> bool:
        """게인을 설정합니다."""
        if not self.is_opened:
            return False
        
        try:
            self.cap.set(cv2.CAP_PROP_GAIN, gain)
            self.gain = gain
            logger.info(f"게인 설정: {gain}")
            return True
        except Exception as e:
            logger.warning(f"게인 설정 실패 (미지원 가능): {e}")
            return False
    
    def set_auto_exposure(self, auto: bool) -> bool:
        """자동 노출을 설정합니다."""
        if not self.is_opened:
            return False
        
        try:
            value = 0.25 if auto else 0.75  # DirectShow 기준
            self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, value)
            logger.info(f"자동 노출: {auto}")
            return True
        except Exception as e:
            logger.warning(f"자동 노출 설정 실패: {e}")
            return False
    
    def get_frame(self, timeout: float = 0.5) -> Optional[np.ndarray]:
        """
        큐에서 프레임을 가져옵니다.
        
        Args:
            timeout: 대기 시간 (초)
            
        Returns:
            np.ndarray: 프레임, 없으면 None
        """
        try:
            frame = self.frame_queue.get(timeout=timeout)
            return frame
        except:
            return None
    
    def run(self):
        """스레드 메인 루프"""
        logger.info(f"카메라 스레드 시작 (index={self.camera_index})")
        
        while not self.stop_event.is_set():
            if not self.is_opened:
                time.sleep(0.1)
                continue
            
            ret, frame = self.cap.read()
            
            if not ret or frame is None:
                logger.warning("프레임 읽기 실패")
                time.sleep(0.01)
                continue
            
            # 큐에 프레임 추가 (꽉 차면 오래된 프레임 제거)
            try:
                self.frame_queue.put(frame, block=False)
            except Full:
                # 오래된 프레임 제거 후 새 프레임 추가
                try:
                    self.frame_queue.get_nowait()
                    self.frame_queue.put(frame, block=False)
                except:
                    pass
        
        self.close_camera()
        logger.info("카메라 스레드 종료")
    
    def stop(self):
        """스레드를 중지합니다."""
        self.stop_event.set()
