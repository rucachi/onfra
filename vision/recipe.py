"""
템플릿(레시피) 관리
ORB 특징점 추출 및 저장/로드
"""
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Recipe:
    """
    템플릿 레시피
    학습된 객체의 정보를 담고 있습니다.
    """
    name: str
    roi: tuple[int, int, int, int]  # (x, y, w, h)
    created_at: str
    notes: str = ""
    keypoint_count: int = 0
    
    # 런타임 데이터 (저장 안 됨)
    template_img: Optional[np.ndarray] = None
    keypoints: Optional[list] = None
    descriptors: Optional[np.ndarray] = None


class RecipeManager:
    """레시피 저장/로드 관리자"""
    
    def __init__(self, recipes_dir: str = "data/recipes"):
        """
        Args:
            recipes_dir: 레시피 저장 디렉토리
        """
        self.recipes_dir = Path(recipes_dir)
        self.recipes_dir.mkdir(parents=True, exist_ok=True)
        
        # ORB 특징점 추출기
        self.orb = cv2.ORB_create(nfeatures=1000)
        
        logger.info(f"레시피 디렉토리: {self.recipes_dir.absolute()}")
    
    def create_recipe(
        self,
        name: str,
        roi_img: np.ndarray,
        roi: tuple[int, int, int, int],
        notes: str = ""
    ) -> Optional[Recipe]:
        """
        새 레시피를 생성합니다.
        
        Args:
            name: 레시피 이름
            roi_img: ROI 이미지
            roi: ROI 좌표 (x, y, w, h)
            notes: 메모
            
        Returns:
            Recipe: 생성된 레시피, 실패 시 None
        """
        try:
            # ORB 특징점 추출
            gray = cv2.cvtColor(roi_img, cv2.COLOR_BGR2GRAY) if len(roi_img.shape) == 3 else roi_img
            keypoints, descriptors = self.orb.detectAndCompute(gray, None)
            
            if descriptors is None or len(keypoints) < 10:
                logger.error(f"특징점이 부족합니다 (최소 10개 필요, 현재 {len(keypoints) if keypoints else 0}개)")
                return None
            
            recipe = Recipe(
                name=name,
                roi=roi,
                created_at=datetime.now().isoformat(),
                notes=notes,
                keypoint_count=len(keypoints),
                template_img=roi_img.copy(),
                keypoints=keypoints,
                descriptors=descriptors
            )
            
            logger.info(f"레시피 생성: {name} (키포인트: {len(keypoints)}개)")
            return recipe
            
        except Exception as e:
            logger.error(f"레시피 생성 실패: {e}")
            return None
    
    def save_recipe(self, recipe: Recipe) -> bool:
        """
        레시피를 파일로 저장합니다.
        
        Args:
            recipe: 저장할 레시피
            
        Returns:
            bool: 성공 여부
        """
        try:
            recipe_dir = self.recipes_dir / recipe.name
            recipe_dir.mkdir(parents=True, exist_ok=True)
            
            # 메타데이터 저장 (JSON)
            meta_path = recipe_dir / "metadata.json"
            meta_data = {
                "name": recipe.name,
                "roi": recipe.roi,
                "created_at": recipe.created_at,
                "notes": recipe.notes,
                "keypoint_count": recipe.keypoint_count
            }
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta_data, f, indent=2, ensure_ascii=False)
            
            # 템플릿 이미지 저장 (PNG)
            img_path = recipe_dir / "template.png"
            cv2.imwrite(str(img_path), recipe.template_img)
            
            # 디스크립터 저장 (NPY)
            desc_path = recipe_dir / "descriptors.npy"
            np.save(str(desc_path), recipe.descriptors)
            
            logger.info(f"레시피 저장 완료: {recipe.name}")
            return True
            
        except Exception as e:
            logger.error(f"레시피 저장 실패: {e}")
            return False
    
    def load_recipe(self, name: str) -> Optional[Recipe]:
        """
        레시피를 파일에서 로드합니다.
        
        Args:
            name: 레시피 이름
            
        Returns:
            Recipe: 로드된 레시피, 실패 시 None
        """
        try:
            recipe_dir = self.recipes_dir / name
            
            if not recipe_dir.exists():
                logger.error(f"레시피 디렉토리가 없습니다: {name}")
                return None
            
            # 메타데이터 로드
            meta_path = recipe_dir / "metadata.json"
            with open(meta_path, "r", encoding="utf-8") as f:
                meta_data = json.load(f)
            
            # 템플릿 이미지 로드
            img_path = recipe_dir / "template.png"
            template_img = cv2.imread(str(img_path))
            
            # 디스크립터 로드
            desc_path = recipe_dir / "descriptors.npy"
            descriptors = np.load(str(desc_path))
            
            # 키포인트 재생성 (좌표 정보는 없지만 디스크립터는 있음)
            # 실제 매칭에는 디스크립터만 필요
            recipe = Recipe(
                name=meta_data["name"],
                roi=tuple(meta_data["roi"]),
                created_at=meta_data["created_at"],
                notes=meta_data.get("notes", ""),
                keypoint_count=meta_data["keypoint_count"],
                template_img=template_img,
                keypoints=None,  # 디스크립터만으로 매칭 가능
                descriptors=descriptors
            )
            
            logger.info(f"레시피 로드 완료: {name} (키포인트: {recipe.keypoint_count}개)")
            return recipe
            
        except Exception as e:
            logger.error(f"레시피 로드 실패: {e}")
            return None
    
    def list_recipes(self) -> list[str]:
        """
        저장된 레시피 목록을 반환합니다.
        
        Returns:
            list[str]: 레시피 이름 목록
        """
        try:
            recipes = []
            for item in self.recipes_dir.iterdir():
                if item.is_dir() and (item / "metadata.json").exists():
                    recipes.append(item.name)
            return sorted(recipes)
        except Exception as e:
            logger.error(f"레시피 목록 조회 실패: {e}")
            return []
    
    def delete_recipe(self, name: str) -> bool:
        """
        레시피를 삭제합니다.
        
        Args:
            name: 레시피 이름
            
        Returns:
            bool: 성공 여부
        """
        try:
            recipe_dir = self.recipes_dir / name
            
            if not recipe_dir.exists():
                logger.warning(f"삭제할 레시피가 없습니다: {name}")
                return False
            
            # 디렉토리 내 파일 삭제
            for file in recipe_dir.iterdir():
                file.unlink()
            
            # 디렉토리 삭제
            recipe_dir.rmdir()
            
            logger.info(f"레시피 삭제 완료: {name}")
            return True
            
        except Exception as e:
            logger.error(f"레시피 삭제 실패: {e}")
            return False
