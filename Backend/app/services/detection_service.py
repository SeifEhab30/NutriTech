from ultralytics import YOLO
import cv2
import numpy as np
import base64
import os
from sqlalchemy.orm import Session
from app.models.food import FoodItem

class DetectionService:
    def __init__(self, model_path: str):
        self.model = YOLO(model_path)
    
    def detect_food(self, db: Session, image_bytes: bytes, user_weights: dict = None, conf_threshold: float = 0.25):
        # Convert bytes to numpy array for OpenCV
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Invalid image format")
        # Run YOLO inference
        results = self.model.predict(source=img, conf=conf_threshold, verbose=False)
        result = results[0]
        
        boxes = result.boxes
        
        # Group detections by class name
        grouped_counts = {}
        for box in boxes:
            class_id = int(box.cls[0])
            class_name = self.model.names[class_id].lower().strip()
            grouped_counts[class_name] = grouped_counts.get(class_name, 0) + 1

        detections = []
        total_macros = {
            "calories": {"min": 0.0, "max": 0.0},
            "protein": {"min": 0.0, "max": 0.0},
            "carbs": {"min": 0.0, "max": 0.0},
            "fat": {"min": 0.0, "max": 0.0},
            "fiber": {"min": 0.0, "max": 0.0}
        }

        for class_name, count in grouped_counts.items():
            # Query database for nutritional info
            food_info = db.query(FoodItem).filter(FoodItem.name == class_name).first()
            if not food_info:
                food_info = db.query(FoodItem).filter(FoodItem.name.contains(class_name.replace('_', ' '))).first()

            if food_info:
                # Handle potentially missing or zero serving size to avoid division by zero
                serving_size = food_info.serving_size_g if (food_info.serving_size_g and food_info.serving_size_g > 0) else 100.0

                # Calculate weight: user-provided total weight OR (count * default_serving).
                # The frontend keys overrides by the food name it was shown (food_info.name);
                # fall back to the raw class name for safety.
                if user_weights and food_info.name in user_weights:
                    actual_weight = float(user_weights[food_info.name])
                elif user_weights and class_name in user_weights:
                    actual_weight = float(user_weights[class_name])
                else:
                    actual_weight = serving_size * count
                
                scale = actual_weight / serving_size
                
                def safe_val(val):
                    return (val if val is not None else 0.0) * scale

                scaled_nutrition = {
                    "food_name": food_info.name,
                    "serving_size_g": serving_size,
                    "count": count,
                    "total_weight_g": actual_weight,
                    "calories": {"min": safe_val(food_info.calories_min), "max": safe_val(food_info.calories_max)},
                    "protein": {"min": safe_val(food_info.protein_min), "max": safe_val(food_info.protein_max)},
                    "carbs": {"min": safe_val(food_info.carbs_min), "max": safe_val(food_info.carbs_max)},
                    "fat": {"min": safe_val(food_info.fat_min), "max": safe_val(food_info.fat_max)},
                    "fiber": {"min": safe_val(food_info.fiber_min), "max": safe_val(food_info.fiber_max)}
                }

                # Add to totals
                for nut in ["calories", "protein", "carbs", "fat", "fiber"]:
                    total_macros[nut]["min"] += scaled_nutrition[nut]["min"]
                    total_macros[nut]["max"] += scaled_nutrition[nut]["max"]

                detections.append(scaled_nutrition)
            else:
                # If no nutrition data, still report the count
                detections.append({
                    "food_name": class_name,
                    "serving_size_g": 0,
                    "count": count,
                    "total_weight_g": 0,
                    "calories": {"min": 0, "max": 0},
                    "protein": {"min": 0, "max": 0},
                    "carbs": {"min": 0, "max": 0},
                    "fat": {"min": 0, "max": 0},
                    "fiber": {"min": 0, "max": 0}
                })

        # Create annotated image
        annotated_img = result.plot(labels=True, conf=False)
        _, buffer = cv2.imencode('.jpg', annotated_img)
        img_base64 = base64.b64encode(buffer).decode('utf-8')

        return {
            "detections": detections,
            "total_macros": total_macros,
            "annotated_image": img_base64
        }

# Global instance
MODEL_PATH = os.path.join("app", "AI_Models", "best.pt")
detection_service = DetectionService(MODEL_PATH)
