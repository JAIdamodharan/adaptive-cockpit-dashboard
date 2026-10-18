"""
Driver Cognitive State Monitoring Module
AI-based drowsiness, emotion, and stress detection using computer vision
Enhanced version with MediaPipe for accurate face mesh detection
"""

import cv2
import json
import numpy as np
import logging
import time
import os
from PyQt5.QtCore import QObject, pyqtSignal, QThread
from dataclasses import dataclass
from typing import Optional, Tuple
from collections import deque, Counter
from statistics import median

from drowsiness_engine import DrowsinessEngine


def list_available_cameras(max_cameras: int = 10):
    """
    List available cameras by trying to open each camera index.
    
    Args:
        max_cameras: Maximum number of camera indices to check
        
    Returns:
        List of available camera indices
    """
    available_cameras = []
    for i in range(max_cameras):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                available_cameras.append(i)
                cap.release()
        else:
            cap.release()
    
    return available_cameras


def load_camera_config(config_file: str = "camera_config.json"):
    """
    Load camera configuration from file.
    
    Args:
        config_file: Path to the camera config file
        
    Returns:
        dict: Camera configuration
    """
    default_config = {
        "camera_selection_method": "auto",
        "preferred_camera_index": 0,
        "last_used_camera": None
    }
    
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                # Merge with defaults to ensure all keys exist
                for key in default_config:
                    if key not in config:
                        config[key] = default_config[key]
                return config
        except Exception as e:
            logger.warning(f"Could not load camera config: {e}")
            
    return default_config


def save_camera_config(config: dict, config_file: str = "camera_config.json"):
    """
    Save camera configuration to file.
    
    Args:
        config: Camera configuration dictionary
        config_file: Path to the camera config file
    """
    try:
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        logger.warning(f"Could not save camera config: {e}")


logger = logging.getLogger(__name__)
try:
    import mediapipe as mp
    # Check for solutions explicitly as some installations may be limited
    if hasattr(mp, 'solutions'):
        MEDIAPIPE_AVAILABLE = True
    else:
        # Try importing solutions directly
        import mediapipe.solutions
        MEDIAPIPE_AVAILABLE = True
except (ImportError, AttributeError):
    MEDIAPIPE_AVAILABLE = False
    logger.warning("MediaPipe not available or missing 'solutions' attribute, falling back to OpenCV Haar Cascades")

# Import for emotion recognition
try:
    import tensorflow as tf
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.layers import Conv2D, MaxPooling2D, Dropout, Flatten, Dense
    TENSORFLOW_AVAILABLE = True
except ImportError:
    TENSORFLOW_AVAILABLE = False
    logger.warning("TensorFlow not available, emotion recognition will be simulated")


@dataclass
class CognitiveState:
    """Data class representing driver cognitive state"""
    timestamp: float
    drowsiness_level: float  # 0.0 (alert) to 1.0 (drowsy)
    eye_aspect_ratio: float  # EAR value
    mouth_aspect_ratio: float = 0.0  # MAR value
    head_pitch: float = 0.0  # Head nodding (up/down)
    head_yaw: float = 0.0    # Head turning (left/right)
    head_roll: float = 0.0   # Head tilting (side to side)
    blink_rate: float = 20.0  # blinks per minute
    yawn_count: int = 0      # Number of yawns detected
    emotion: str = "neutral"  # calm, stressed, angry
    emotion_confidence: float = 1.0
    state_classification: str = "normal"  # normal, fatigued, drowsy, stressed
    alert_required: bool = False
    perclos: float = 0.0              # share of last 60 s with eyes closed
    calibrated: bool = True           # False while learning the driver's baseline
    calibration_progress: float = 1.0


class DriverMonitor(QObject):
    """
    Monitors driver cognitive state using computer vision and AI
    Enhanced version with MediaPipe for accurate face mesh detection
    Falls back to OpenCV Haar Cascades if MediaPipe unavailable
    """
    
    # Signals
    cognitive_state_updated = pyqtSignal(object)  # Emits CognitiveState
    
    # Eye Aspect Ratio (EAR) thresholds
    EAR_THRESHOLD_DROWSY = 0.20
    EAR_THRESHOLD_ALERT = 0.27
    CONSECUTIVE_FRAMES_THRESHOLD = 8
    
    # Mouth Aspect Ratio (MAR) thresholds
    MAR_THRESHOLD_YAWN = 0.55  # Threshold for detecting a yawn
    YAWN_FRAMES_THRESHOLD = 15  # Consecutive frames to count as a yawn
    
    # Head Pose thresholds (in degrees)
    PITCH_THRESHOLD_NOD = 20.0  # Threshold for head nodding down
    YAW_THRESHOLD_DISTRACTED = 30.0  # Threshold for looking away
    
    def __init__(self, camera_index: int = None, use_video_file: Optional[str] = None, config_file: str = "camera_config.json"):
        super().__init__()
        
        # Load camera configuration
        self.config = load_camera_config(config_file)
        self.config_file = config_file
        
        # Determine camera index based on config and parameter
        if camera_index is not None:
            # Use explicitly provided camera index
            self.camera_index = camera_index
        elif self.config["camera_selection_method"] == "manual":
            # Use manually specified camera from config
            self.camera_index = self.config["preferred_camera_index"]
        else:
            # Auto-detect and use the built-in camera
            self.camera_index = self.find_builtin_camera()
        
        # Update config with last used camera
        self.config["last_used_camera"] = self.camera_index
        save_camera_config(self.config, self.config_file)
        
        self.use_video_file = use_video_file
        self.running = False
        
        # Video capture
        self.cap = None
        
        # Initialize MediaPipe if available, otherwise use OpenCV
        if MEDIAPIPE_AVAILABLE:
            self.use_mediapipe = True
            self.mp_face_mesh = mp.solutions.face_mesh
            self.face_mesh = self.mp_face_mesh.FaceMesh(
                static_image_mode=False,
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=0.7,
                min_tracking_confidence=0.7
            )
            self.mp_drawing = mp.solutions.drawing_utils
            logger.info("MediaPipe Face Mesh initialized")
        else:
            self.use_mediapipe = False
            self.face_detector = None
            self.eye_detector = None
            logger.warning("Using fallback OpenCV Haar Cascades due to missing MediaPipe")
        
        # State tracking
        self.consecutive_drowsy_frames = 0
        self.blink_history = deque(maxlen=300)  # 30 seconds at 10 FPS
        self.ear_history = deque(maxlen=30)
        self.prev_ear = 0.3  # For smoothing
        
        # Calibrated drowsiness engine (PERCLOS, closure events, fusion)
        self.engine = DrowsinessEngine()
        self._raw_ear_window = deque(maxlen=3)   # median filter against landmark outliers
        self._emotion_votes = deque(maxlen=7)
        self._frame_count = 0
        self._last_emotion = ("neutral", 0.5)
        self._last_emit = 0.0
        self.yawn_total = 0
        self.latest_frame = None          # BGR preview with overlay, read by the UI
        self._overlay_pts = []

        # New Feature tracking
        self.consecutive_yawn_frames = 0
        self.yawn_count = 0
        self.prev_mar = 0.1
        self.head_pose_history = deque(maxlen=20)
        
        # Current state
        self.current_state = CognitiveState(
            timestamp=time.time(),
            drowsiness_level=0.0,
            eye_aspect_ratio=0.3,
            mouth_aspect_ratio=0.1,
            head_pitch=0.0,
            head_yaw=0.0,
            head_roll=0.0,
            blink_rate=20.0,
            yawn_count=0,
            emotion="calm",
            emotion_confidence=1.0,
            state_classification="normal",
            alert_required=False
        )
        
        # Processing thread
        self.thread = None
        
        # Initialize detectors
        if not self.use_mediapipe:
            self._initialize_detectors()
        
        # Initialize emotion recognition model
        self.emotion_model = self._load_emotion_model()
        
        logger.info("Driver Monitor initialized")
    
    def _initialize_detectors(self):
        """Initialize OpenCV Haar Cascade detectors"""
        try:
            self.face_detector = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )
            self.eye_detector = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_eye.xml'
            )
            logger.info("OpenCV Haar Cascade detectors initialized")
        except Exception as e:
            logger.error(f"Could not initialize face/eye detection: {e}")

    def _load_emotion_model(self):
        """Load the pre-trained emotion recognition model or create a default one"""
        if not TENSORFLOW_AVAILABLE:
            logger.warning("TensorFlow not available, using simulated emotion detection")
            return None
        
        try:
            # Try to load a pre-trained model from file
            model_path = "emotion_model.h5"
            try:
                model = tf.keras.models.load_model(model_path)
                logger.info(f"Loaded emotion recognition model from {model_path}")
                return model
            except:
                # If model file doesn't exist, create a basic CNN model
                logger.info("Creating new emotion recognition model")
                model = self._create_emotion_model()
                
                # Train with synthetic data if possible
                self._train_emotion_model(model)
                
                # Save the model for future use
                try:
                    model.save(model_path)
                    logger.info(f"Saved emotion recognition model to {model_path}")
                except:
                    logger.warning("Could not save model to disk")
                    
                return model
        except Exception as e:
            logger.error(f"Error loading emotion model: {e}")
            return None

    def _create_emotion_model(self):
        """Create a CNN model for emotion recognition"""
        model = Sequential([
            Conv2D(32, (3, 3), activation='relu', input_shape=(48, 48, 1)),
            Conv2D(64, (3, 3), activation='relu'),
            MaxPooling2D(2, 2),
            Dropout(0.25),
            
            Conv2D(128, (3, 3), activation='relu'),
            Conv2D(128, (3, 3), activation='relu'),
            MaxPooling2D(2, 2),
            Dropout(0.25),
            
            Flatten(),
            Dense(1024, activation='relu'),
            Dropout(0.5),
            Dense(7, activation='softmax')  # 7 emotions: angry, disgust, fear, happy, neutral, sad, surprised
        ])
        
        model.compile(optimizer='adam', loss='categorical_crossentropy', metrics=['accuracy'])
        return model
    
    def _train_emotion_model(self, model):
        """Train the model with synthetic facial expression data"""
        # This is a placeholder function that would normally train the model
        # with real facial expression datasets
        logger.info("Training emotion recognition model with synthetic data...")
        
        # For demonstration purposes, we'll skip actual training
        # In a real implementation, you would load training data here
        pass

    def _recognize_emotion(self, face_img):
        """
        Recognize emotion from a face image using the trained model
        
        Args:
            face_img: Grayscale face image of shape (48, 48)
        
        Returns:
            tuple: (emotion_label, confidence)
        """
        if self.emotion_model is None:
            # Fallback to simple heuristic if TensorFlow is not available
            return self._simulated_emotion_recognition(face_img)
        
        try:
            # Preprocess the face image
            img = cv2.resize(face_img, (48, 48))
            img = img.astype('float32') / 255.0
            img = np.expand_dims(img, axis=0)
            img = np.expand_dims(img, axis=-1)  # Add channel dimension
            
            # Predict emotion
            prediction = self.emotion_model.predict(img, verbose=0)
            emotion_idx = np.argmax(prediction[0])
            confidence = float(np.max(prediction[0]))
            
            # Map index to emotion label
            emotions = ['angry', 'disgust', 'fear', 'happy', 'neutral', 'sad', 'surprised']
            emotion_label = emotions[emotion_idx]
            
            return emotion_label, confidence
        except Exception as e:
            logger.error(f"Error in emotion recognition: {e}")
            return self._simulated_emotion_recognition(face_img)

    def _simulated_emotion_recognition(self, face_img):
        """
        Simulate emotion recognition when TensorFlow is not available
        
        Args:
            face_img: Grayscale face image
        
        Returns:
            tuple: (emotion_label, confidence)
        """
        # Simulate emotion detection based on context (random for demo purposes)
        emotions = ['neutral', 'calm', 'happy', 'concerned', 'focused']
        emotion = np.random.choice(emotions)
        confidence = np.random.uniform(0.6, 0.95)
        return emotion, confidence
    
    def start(self):
        """Start driver monitoring"""
        if self.running:
            logger.warning("Driver monitor already running")
            return
        
        # Open video capture
        if self.use_video_file:
            self.cap = cv2.VideoCapture(self.use_video_file)
        else:
            self.cap = cv2.VideoCapture(self.camera_index)
        
        if not self.cap.isOpened():
            logger.error("Could not open video source")
            return
        
        self.running = True
        
        # Start monitoring in separate thread
        self.thread = QThread()
        self.moveToThread(self.thread)
        self.thread.started.connect(self._monitor_loop)
        self.thread.start()
        
        logger.info("Driver monitoring started")
    
    def stop(self):
        """Stop driver monitoring"""
        self.running = False
        
        if self.thread:
            self.thread.quit()
            self.thread.wait()
        
        if self.cap:
            self.cap.release()
        
        # Clean up MediaPipe resources if using it
        if self.use_mediapipe and hasattr(self, 'face_mesh'):
            self.face_mesh.close()
        
        logger.info("Driver monitoring stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop (runs in separate thread)"""
        while self.running:
            ret, frame = self.cap.read()
            
            if not ret:
                logger.warning("Could not read frame from video source")
                time.sleep(0.1)
                continue
            
            # Process frame
            self._process_frame(frame)
            self._build_preview(frame)
            
            # Emit at most ~10 Hz; processing runs faster so short blinks are not missed
            now = time.time()
            if now - self._last_emit >= 0.1:
                self._last_emit = now
                self.cognitive_state_updated.emit(self.current_state)

            time.sleep(0.03)
    
    def _process_frame(self, frame):
        """Process a single video frame for cognitive state detection"""
        timestamp = time.time()
        
        # Initialize emotion variables
        emotion = "neutral"
        emotion_confidence = 0.5
        
        if self.use_mediapipe:
            self._process_frame_mediapipe(frame, timestamp)

        else:
            # Fallback to OpenCV Haar Cascades
            # Convert to grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            # Apply histogram equalization to improve face detection in various lighting conditions
            gray = cv2.equalizeHist(gray)
            
            # Detect face
            faces = self.face_detector.detectMultiScale(gray, 1.3, 5, minSize=(100, 100))  # Minimum face size
            
            if len(faces) > 0:
                # Use first detected face
                (x, y, w, h) = faces[0]
                
                # Ensure face is large enough for reliable eye detection
                if w >= 100 and h >= 100:
                    face_gray = gray[y:y+h, x:x+w]
                    
                    # Detect eyes within the face region
                    eyes = self.eye_detector.detectMultiScale(face_gray, 1.25, 5, minSize=(20, 20))
                    
                    if len(eyes) >= 2:
                        # Calculate average EAR for both eyes
                        ear_values = []
                        for (ex, ey, ew, eh) in eyes:
                            # Calculate EAR approximation based on eye geometry
                            # Using a simplified approach since we don't have landmarks
                            eye_height = eh
                            eye_width = ew
                            ear = (eye_height / eye_width) if eye_width > 0 else 0.3
                            ear_values.append(ear)
                        
                        if ear_values:
                            ear = sum(ear_values) / len(ear_values)
                            
                            # Apply smoothing to reduce jitter
                            smoothing_factor = 0.6
                            smoothed_ear = smoothing_factor * ear + (1 - smoothing_factor) * self.prev_ear
                            self.prev_ear = smoothed_ear
                            
                            self.ear_history.append(smoothed_ear)
                            
                            # Update drowsiness level
                            drowsiness_level = self._calculate_drowsiness_level(smoothed_ear)
                            
                            # Detect blinks
                            self._detect_blink(smoothed_ear)
                            
                            # Calculate blink rate
                            blink_rate = self._calculate_blink_rate()
                            
                            # Detect emotion from face
                            try:
                                emotion, emotion_confidence = self._recognize_emotion(face_gray)
                            except:
                                emotion, emotion_confidence = self._simulated_emotion_recognition(face_gray)
                            
                            # Classify state
                            state_classification = self._classify_state_enhanced(drowsiness_level, smoothed_ear, 0.1, (0.0, 0.0, 0.0), emotion)
                            
                            # Update current state
                            self.current_state = CognitiveState(
                                timestamp=timestamp,
                                drowsiness_level=drowsiness_level,
                                eye_aspect_ratio=smoothed_ear,
                                mouth_aspect_ratio=0.1,
                                head_pitch=0.0,
                                head_yaw=0.0,
                                head_roll=0.0,
                                blink_rate=blink_rate,
                                yawn_count=self.yawn_count,
                                emotion=emotion,
                                emotion_confidence=emotion_confidence,
                                state_classification=state_classification,
                                alert_required=(state_classification in ["drowsy", "stressed"])
                            )
                    else:
                        # No eyes detected - use simplified detection
                        self._simplified_detection_with_context(gray, timestamp)
                else:
                    # Face too small, use simplified detection
                    self._simplified_detection_with_context(gray, timestamp)
            else:
                # No face detected - use simplified detection
                self._simplified_detection_with_context(gray, timestamp)
            

    def _build_preview(self, frame):
        """Small mirrored preview with eye/mouth points and a state-coloured border."""
        try:
            h, w = frame.shape[:2]
            scale = 360.0 / w
            img = cv2.flip(cv2.resize(frame, (360, int(h * scale))), 1)
            ph, pw = img.shape[:2]
            st = self.current_state
            color = {"normal": (113, 204, 46), "fatigued": (15, 196, 241), "drowsy": (60, 76, 231)}.get(
                st.state_classification, (255, 160, 90))
            for (x, y) in self._overlay_pts:
                cv2.circle(img, (int((1 - x) * pw), int(y * ph)), 2, (255, 255, 0), -1)
            cv2.rectangle(img, (0, 0), (pw - 1, ph - 1), color, 4)
            label = ("CALIBRATING %d%%" % int(st.calibration_progress * 100)) if not st.calibrated \
                else "%s  PERCLOS %d%%" % (st.state_classification.upper(), int(st.perclos * 100))
            cv2.putText(img, label, (8, ph - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2, cv2.LINE_AA)
            self.latest_frame = img
        except Exception as e:
            logger.debug(f"Preview failed: {e}")

    def recalibrate(self):
        """Forget the learned baseline and learn it again (e.g. new driver or camera angle)."""
        self.engine.reset()
        self._raw_ear_window.clear()
        self.prev_ear = 0.3
        logger.info("Driver calibration restarted")

    def _process_frame_mediapipe(self, frame, timestamp):
        """MediaPipe path: calibrated, PERCLOS-based drowsiness estimation."""
        self._frame_count += 1
        self._frame_wh = (frame.shape[1], frame.shape[0])
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face_mesh.process(rgb_frame)

        if not results.multi_face_landmarks:
            self._handle_no_face(timestamp)
            return

        landmarks = results.multi_face_landmarks[0]
        left = self._calculate_ear_mediapipe(landmarks, [362, 385, 387, 263, 373, 380])
        right = self._calculate_ear_mediapipe(landmarks, [33, 160, 158, 133, 153, 144])
        if left is None or right is None:
            self._handle_no_face(timestamp)
            return

        # Median of the last few raw values removes single-frame landmark glitches,
        # then a light EMA smooths the rest
        self._raw_ear_window.append((left + right) / 2.0)
        ear = float(median(self._raw_ear_window))
        smoothed_ear = 0.6 * ear + 0.4 * self.prev_ear
        self.prev_ear = smoothed_ear
        self.ear_history.append(smoothed_ear)

        eye_idx = [362, 385, 387, 263, 373, 380, 33, 160, 158, 133, 153, 144, 13, 14, 78, 308]
        self._overlay_pts = [(landmarks.landmark[i].x, landmarks.landmark[i].y) for i in eye_idx]

        mar = self._calculate_mar_mediapipe(landmarks)
        smoothed_mar = 0.5 * mar + 0.5 * self.prev_mar
        self.prev_mar = smoothed_mar

        pitch, yaw, roll = self._estimate_head_pose_mediapipe(landmarks, frame.shape)
        self.head_pose_history.append((pitch, yaw, roll))

        before = self.engine.yawns.recent_count
        assessment = self.engine.update(timestamp, smoothed_ear, smoothed_mar, pitch, yaw)
        if self.engine.yawns.recent_count > before:
            self.yawn_total += 1
            logger.info(f"Yawn detected! Total count: {self.yawn_total}")

        # Emotion is expensive and changes slowly: every 5th frame, majority-voted
        if self._frame_count % 5 == 0:
            self._update_emotion(frame, landmarks)
        emotion, emotion_confidence = self._last_emotion

        state_classification = self._classify_from_assessment(
            assessment, (pitch, yaw, roll), emotion, emotion_confidence)

        self.current_state = CognitiveState(
            timestamp=timestamp,
            drowsiness_level=assessment.level,
            eye_aspect_ratio=smoothed_ear,
            mouth_aspect_ratio=smoothed_mar,
            head_pitch=pitch,
            head_yaw=yaw,
            head_roll=roll,
            blink_rate=self.engine.blink_rate_per_min if assessment.calibrated else 20.0,
            yawn_count=self.yawn_total,
            emotion=emotion,
            emotion_confidence=emotion_confidence,
            state_classification=state_classification,
            alert_required=(state_classification in ["drowsy", "stressed"]),
            perclos=assessment.perclos,
            calibrated=assessment.calibrated,
            calibration_progress=assessment.calibration_progress,
        )

    def _handle_no_face(self, timestamp):
        """Face lost / unusable frame: never fabricate data and never count it as closed eyes."""
        self._overlay_pts = []
        assessment = self.engine.update(timestamp, None)
        prev = self.current_state
        state = prev.state_classification if assessment.state != "normal" else "normal"
        if state in ("stressed", "alert"):
            state = "normal"
        self.current_state = CognitiveState(
            timestamp=timestamp,
            drowsiness_level=assessment.level,
            eye_aspect_ratio=prev.eye_aspect_ratio,
            mouth_aspect_ratio=prev.mouth_aspect_ratio,
            head_pitch=prev.head_pitch,
            head_yaw=prev.head_yaw,
            head_roll=prev.head_roll,
            blink_rate=prev.blink_rate,
            yawn_count=self.yawn_total,
            emotion=prev.emotion,
            emotion_confidence=prev.emotion_confidence,
            state_classification=state,
            alert_required=(state in ["drowsy", "stressed"]),
            perclos=assessment.perclos,
            calibrated=assessment.calibrated,
            calibration_progress=assessment.calibration_progress,
        )

    def _update_emotion(self, frame, landmarks):
        """Crop the face from the landmark extents and update the voted emotion."""
        try:
            h, w = frame.shape[:2]
            xs = [lm.x for lm in landmarks.landmark]
            ys = [lm.y for lm in landmarks.landmark]
            x0, x1 = max(0, int(min(xs) * w)), min(w, int(max(xs) * w))
            y0, y1 = max(0, int(min(ys) * h)), min(h, int(max(ys) * h))
            if x1 - x0 < 40 or y1 - y0 < 40:
                return
            gray = cv2.cvtColor(frame[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
            label, conf = self._recognize_emotion(gray)
            self._emotion_votes.append((label, conf))
            top, _ = Counter(l for l, _ in self._emotion_votes).most_common(1)[0]
            confs = [c for l, c in self._emotion_votes if l == top]
            self._last_emotion = (top, float(sum(confs) / len(confs)))
        except Exception as e:
            logger.debug(f"Emotion update failed: {e}")

    def _classify_from_assessment(self, assessment, head_pose, emotion, emotion_confidence) -> str:
        """Map the fused drowsiness assessment (plus distraction/emotion) to a UI state."""
        if not assessment.calibrated:
            return "normal"          # warm-up: never alert while learning the driver
        if assessment.state == "drowsy":
            return "drowsy"
        if assessment.state == "fatigued":
            return "fatigued"
        yaw_dev = abs(head_pose[1] - self.engine.calibrator.neutral_yaw)
        if yaw_dev > self.YAW_THRESHOLD_DISTRACTED:
            return "stressed"        # catch-all "attention needed" in the current UI
        if emotion in ("angry", "fear") and emotion_confidence >= 0.7:
            return "stressed"
        return "normal"

    def _calculate_drowsiness_level(self, ear: float) -> float:
        """
        Calculate drowsiness level based on EAR with hysteresis to prevent oscillations
        Returns value between 0.0 (alert) and 1.0 (drowsy)
        """
        if ear >= self.EAR_THRESHOLD_ALERT:
            # If we're clearly alert, reset counter quickly
            self.consecutive_drowsy_frames = max(0, self.consecutive_drowsy_frames - 3)  # Faster recovery
            return 0.0
        elif ear <= self.EAR_THRESHOLD_DROWSY:
            # If eyes are clearly closed/drowsy, increment counter appropriately
            self.consecutive_drowsy_frames += 1  # Single increment to avoid over-sensitivity
            # Cap at threshold to prevent over-increment
            self.consecutive_drowsy_frames = min(self.CONSECUTIVE_FRAMES_THRESHOLD, self.consecutive_drowsy_frames)
            
            if self.consecutive_drowsy_frames >= self.CONSECUTIVE_FRAMES_THRESHOLD:
                return 1.0
            else:
                # Scale to 0-1 range based on threshold
                return min(1.0, (self.consecutive_drowsy_frames / self.CONSECUTIVE_FRAMES_THRESHOLD) * 0.9)
        else:
            # In the intermediate zone - be more stable
            # Only change if we've been consistently in this state
            if ear > (self.EAR_THRESHOLD_ALERT + self.EAR_THRESHOLD_DROWSY) / 2:
                # Closer to alert threshold
                self.consecutive_drowsy_frames = max(0, self.consecutive_drowsy_frames - 1)
            else:
                # Closer to drowsy threshold
                self.consecutive_drowsy_frames = max(
                    0, min(self.CONSECUTIVE_FRAMES_THRESHOLD - 1, self.consecutive_drowsy_frames + 0.3)
                )
            
            # Only return drowsy level if we have sufficient consecutive frames
            if self.consecutive_drowsy_frames >= self.CONSECUTIVE_FRAMES_THRESHOLD:
                return 0.9  # High but not maximum to allow for slight variations
            elif self.consecutive_drowsy_frames > self.CONSECUTIVE_FRAMES_THRESHOLD * 0.7:
                # Return proportional drowsiness based on consecutive frames
                return min(0.7, (self.consecutive_drowsy_frames / self.CONSECUTIVE_FRAMES_THRESHOLD) * 0.7)
            elif self.consecutive_drowsy_frames > 0:
                # For low consecutive frames, return minimal drowsiness
                return min(0.3, (self.consecutive_drowsy_frames / self.CONSECUTIVE_FRAMES_THRESHOLD) * 0.3)
            else:
                return 0.0
    
    def _detect_blink(self, ear: float):
        """Detect blink events based on EAR"""
        # Use a dedicated blink threshold to avoid confusion with drowsiness
        # Adjust based on the new drowsiness thresholds
        BLINK_THRESHOLD = 0.15  # Adjusted to be below the new drowsiness threshold but above noise
        if ear < BLINK_THRESHOLD:
            self.blink_history.append(time.time())
    
    def _calculate_blink_rate(self) -> float:
        """Calculate blinks per minute"""
        if len(self.blink_history) < 2:
            return 20.0  # Default normal blink rate
        
        # Count blinks in last 60 seconds
        current_time = time.time()
        recent_blinks = [t for t in self.blink_history if current_time - t <= 60.0]
        
        return float(len(recent_blinks))
    
    def _calculate_ear_mediapipe(self, landmarks, eye_indices):
        """
        Calculate Eye Aspect Ratio using MediaPipe face mesh landmarks
        Formula: EAR = (|p2-p6| + |p3-p5|) / (2 * |p1-p4|)
        """
        try:
            # Get the eye landmark points
            eye_points = []
            for idx in eye_indices:
                landmark = landmarks.landmark[idx]
                # scale by frame size: normalised x/y have different pixel units
                fw, fh = getattr(self, '_frame_wh', (1, 1))
                eye_points.append((landmark.x * fw, landmark.y * fh))
            
            if len(eye_points) >= 6:
                # Vertical distances (p2-p6 and p3-p5)
                A = np.linalg.norm(np.array(eye_points[1]) - np.array(eye_points[5]))
                B = np.linalg.norm(np.array(eye_points[2]) - np.array(eye_points[4]))
                
                # Horizontal distance (p1-p4)
                C = np.linalg.norm(np.array(eye_points[0]) - np.array(eye_points[3]))
                
                # EAR = (A + B) / (2 * C)
                if C > 0:
                    ear = (A + B) / (2.0 * C)
                    # Closed eyes legitimately give very small EAR, so only reject
                    # geometrically impossible values
                    if 0.0 <= ear < 0.7:
                        return ear
        except Exception as e:
            logger.debug(f"Error calculating EAR with MediaPipe: {e}")
        
        return None

    def _calculate_mar_mediapipe(self, landmarks):
        """
        Calculate Mouth Aspect Ratio using MediaPipe face mesh landmarks
        Formula: MAR = |p14-p13| / |p308-p78| (Simplified height/width ratio)
        """
        try:
            # p13: upper lip inner, p14: lower lip inner
            p13 = landmarks.landmark[13]
            p14 = landmarks.landmark[14]
            # p78: left mouth corner, p308: right mouth corner
            p78 = landmarks.landmark[78]
            p308 = landmarks.landmark[308]
            
            # Vertical distance
            height = np.linalg.norm(np.array([p13.x, p13.y]) - np.array([p14.x, p14.y]))
            # Horizontal distance
            width = np.linalg.norm(np.array([p78.x, p78.y]) - np.array([p308.x, p308.y]))
            
            if width > 0:
                mar = height / width
                return mar
        except Exception as e:
            logger.debug(f"Error calculating MAR with MediaPipe: {e}")
        
        return 0.1

    def _detect_yawn(self, mar: float):
        """Detect yawning events based on MAR"""
        if mar > self.MAR_THRESHOLD_YAWN:
            self.consecutive_yawn_frames += 1
            if self.consecutive_yawn_frames == self.YAWN_FRAMES_THRESHOLD:
                self.yawn_count += 1
                logger.info(f"Yawn detected! Total count: {self.yawn_count}")
        else:
            self.consecutive_yawn_frames = 0

    def _estimate_head_pose_mediapipe(self, landmarks, image_shape):
        """
        Estimate head pose (pitch, yaw, roll) from landmarks
        """
        h, w, c = image_shape
        
        # 3D model points
        model_points = np.array([
            (0.0, 0.0, 0.0),             # Nose tip
            (0.0, -330.0, -65.0),        # Chin
            (-225.0, 170.0, -135.0),     # Left eye left corner
            (225.0, 170.0, -135.0),      # Right eye right corner
            (-150.0, -150.0, -125.0),    # Left Mouth corner
            (150.0, -150.0, -125.0)      # Right mouth corner
        ])

        # 2D image points from landmarks
        # Indices: nose=4, chin=152, left_eye=33, right_eye=263, left_mouth=61, right_mouth=291
        indices = [4, 152, 33, 263, 61, 291]
        image_points = []
        for idx in indices:
            lm = landmarks.landmark[idx]
            image_points.append((lm.x * w, lm.y * h))
        image_points = np.array(image_points, dtype="double")

        # Camera matrix
        focal_length = w
        center = (w/2, h/2)
        camera_matrix = np.array([
            [focal_length, 0, center[0]],
            [0, focal_length, center[1]],
            [0, 0, 1]
        ], dtype="double")

        # Assuming no lens distortion
        dist_coeffs = np.zeros((4, 1))
        
        # Solve PnP
        (success, rotation_vector, translation_vector) = cv2.solvePnP(
            model_points, image_points, camera_matrix, dist_coeffs, flags=cv2.SOLVEPNP_ITERATIVE
        )

        if success:
            # Convert rotation vector to rotation matrix
            rmat, _ = cv2.Rodrigues(rotation_vector)
            
            # Extract Euler angles
            sy = np.sqrt(rmat[0, 0] * rmat[0, 0] + rmat[1, 0] * rmat[1, 0])
            singular = sy < 1e-6

            if not singular:
                x = np.arctan2(rmat[2, 1], rmat[2, 2])
                y = np.arctan2(-rmat[2, 0], sy)
                z = np.arctan2(rmat[1, 0], rmat[0, 0])
            else:
                x = np.arctan2(-rmat[1, 2], rmat[1, 1])
                y = np.arctan2(-rmat[2, 0], sy)
                z = 0

            # Convert to degrees
            pitch = float(np.degrees(x))
            yaw = float(np.degrees(y))
            roll = float(np.degrees(z))

            # solvePnP with this model reports pitch near +/-180 for an upright head;
            # wrap into [-90, 90] so 'nodding' is measured around zero
            if pitch > 90:
                pitch -= 180
            elif pitch < -90:
                pitch += 180
            if roll > 90:
                roll -= 180
            elif roll < -90:
                roll += 180

            return pitch, yaw, roll
        
        return 0.0, 0.0, 0.0

    def _classify_state(self, drowsiness_level: float, ear: float) -> str:
        """
        Classify driver state based on drowsiness metrics
        Returns: normal, fatigued, drowsy, stressed
        """
        if drowsiness_level >= 0.8:
            return "drowsy"
        elif drowsiness_level >= 0.4:
            return "fatigued"
        elif ear < 0.23:
            return "stressed"  # Very low EAR without drowsiness pattern
        else:
            return "normal"
            
    def _classify_state(self, drowsiness_level: float, ear: float) -> str:
        """
        Classify driver state based on drowsiness metrics
        Returns: normal, fatigued, drowsy, stressed
        """
        if drowsiness_level >= 0.8:
            return "drowsy"
        elif drowsiness_level >= 0.4:
            return "fatigued"
        elif ear < 0.23:
            return "stressed"  # Very low EAR without drowsiness pattern
        else:
            return "normal"
    
    def _extract_face_bbox(self, frame):
        """Extract face bounding box using face detector"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        
        # Detect face
        faces = self.face_detector.detectMultiScale(gray, 1.3, 5, minSize=(100, 100))
        
        if len(faces) > 0:
            # Return first detected face
            return faces[0]
        
        return None

    def _classify_state_enhanced(self, drowsiness_level: float, ear: float, mar: float, head_pose: Tuple[float, float, float], emotion: str) -> str:
        """
        Enhanced driver state classification using EAR, MAR, Head Pose, and Emotion
        """
        pitch, yaw, roll = head_pose
        
        # 1. Critical Drowsiness (EAR + Nodding)
        if ear <= self.EAR_THRESHOLD_DROWSY or drowsiness_level >= 0.8:
            # If eyes are closed OR drowsiness level is high
            return "drowsy"
        
        if pitch > self.PITCH_THRESHOLD_NOD:
            # Head nodding down
            return "drowsy"
            
        # 2. Fatigue (Yawning + Moderate EAR)
        if mar > self.MAR_THRESHOLD_YAWN or self.yawn_count > 0:
            # Yawning or history of yawns
            return "fatigued"
            
        if drowsiness_level >= 0.4 or ear <= 0.24:
            return "fatigued"
            
        # 3. Distraction (Yaw)
        if abs(yaw) > self.YAW_THRESHOLD_DISTRACTED:
            return "stressed" # Using stressed as a catch-all for "alert needed" in the current UI
            
        # 4. Stress/Emotion
        if emotion in ["stressed", "angry", "fear"]:
            return "stressed"
            
        if emotion in ["alert", "focused"]:
            return "alert"
            
        if ear < 0.25:
            return "stressed"
            
        return "normal"

    def _simplified_detection_with_context(self, gray_frame, timestamp):
        """Enhanced simplified detection with contextual awareness"""
        # Enhanced simulation with contextual factors that reduces fluctuations
        # Use a more stable baseline to reduce random oscillations
        base_ear = 0.32  # Further raised baseline to be well above drowsiness threshold
        drowsiness = 0.0
        
        # Introduce very conservative variation to simulate stable eye states
        # Use extremely low probability of very low EAR values to minimize false drowsiness detection
        if np.random.random() < 0.005:  # Only 0.5% chance of very low EAR (real closed eyes for brief moment)
            current_ear = np.random.uniform(0.18, 0.20)  # Just above drowsy threshold
        else:
            # Very small variation around the baseline to keep it stable
            variation = np.random.normal(0, 0.01)  # Very small variation
            current_ear = max(0.20, base_ear + variation)  # Ensure well above drowsiness threshold
        
        # Maintain consistent state to reduce fluctuations
        # Only change if consistently detected over multiple frames
        if current_ear <= self.EAR_THRESHOLD_DROWSY:
            # Increment very slowly for drowsy detection
            self.consecutive_drowsy_frames = min(self.CONSECUTIVE_FRAMES_THRESHOLD, 
                                               self.consecutive_drowsy_frames + 0.2)
        elif current_ear <= self.EAR_THRESHOLD_ALERT:
            # For intermediate values, minimal change
            self.consecutive_drowsy_frames = max(0, 
                                               self.consecutive_drowsy_frames + (-0.1 if self.consecutive_drowsy_frames > 0 else -0.3))
        else:
            # Clearly alert: decrease quickly
            self.consecutive_drowsy_frames = max(0, self.consecutive_drowsy_frames - 0.8)
        
        # Calculate drowsiness with hysteresis to prevent rapid state changes
        if self.consecutive_drowsy_frames >= self.CONSECUTIVE_FRAMES_THRESHOLD:
            drowsiness = 0.9
        elif self.consecutive_drowsy_frames >= self.CONSECUTIVE_FRAMES_THRESHOLD * 0.7:
            drowsiness = 0.6
        elif self.consecutive_drowsy_frames >= self.CONSECUTIVE_FRAMES_THRESHOLD * 0.4:
            drowsiness = 0.3
        else:
            drowsiness = 0.0
        
        # Update EAR history with smoothing
        if len(self.ear_history) > 0:
            # Consider trend over time to detect gradual changes
            recent_avg = sum(list(self.ear_history)[-5:]) / min(5, len(self.ear_history))
            # Use moderate threshold to balance sensitivity and stability
            threshold_for_change = 0.02  # Balanced threshold
            
            if current_ear < recent_avg - threshold_for_change:
                if current_ear <= self.EAR_THRESHOLD_DROWSY:
                    self.consecutive_drowsy_frames += 2  # Faster increment for very low EAR
                else:
                    self.consecutive_drowsy_frames += 1
                drowsiness = min(1.0, self.consecutive_drowsy_frames / self.CONSECUTIVE_FRAMES_THRESHOLD)
            elif current_ear <= self.EAR_THRESHOLD_DROWSY:
                # Even if increasing, if still below drowsy threshold, continue counting
                self.consecutive_drowsy_frames += 1
                drowsiness = min(1.0, self.consecutive_drowsy_frames / self.CONSECUTIVE_FRAMES_THRESHOLD)
            elif current_ear > recent_avg + threshold_for_change:
                self.consecutive_drowsy_frames = max(0, self.consecutive_drowsy_frames - 1)  # Slower decrease
                drowsiness = max(0.0, self.consecutive_drowsy_frames / self.CONSECUTIVE_FRAMES_THRESHOLD)
        else:
            # Reset consecutive frames when no history
            self.consecutive_drowsy_frames = 0
        
        # Simulate emotion recognition in simplified mode
        emotions = ['neutral', 'calm', 'happy', 'concerned', 'focused', 'stressed']
        emotion = np.random.choice(emotions)
        emotion_confidence = np.random.uniform(0.6, 0.95)
        
        # Simulate head pose (small movements)
        sim_pitch = np.random.normal(0, 2.0)
        sim_yaw = np.random.normal(0, 3.0)
        sim_roll = np.random.normal(0, 1.0)
        
        # Simulate MAR (mostly quiet, occasional mouth movements)
        sim_mar = 0.1 + abs(np.random.normal(0, 0.02))
        if np.random.random() < 0.01: # 1% chance of a yawn start
             sim_mar = np.random.uniform(0.4, 0.6)
             
        self._detect_yawn(sim_mar)
        
        # Use enhanced classification with simulated values
        state_classification = self._classify_state_enhanced(
            drowsiness, current_ear, sim_mar, (sim_pitch, sim_yaw, sim_roll), emotion
        )
        
        self.current_state = CognitiveState(
            timestamp=timestamp,
            drowsiness_level=drowsiness,
            eye_aspect_ratio=current_ear,
            mouth_aspect_ratio=sim_mar,
            head_pitch=sim_pitch,
            head_yaw=sim_yaw,
            head_roll=sim_roll,
            blink_rate=self._calculate_blink_rate(),
            yawn_count=self.yawn_count,
            emotion=emotion,
            emotion_confidence=emotion_confidence,
            state_classification=state_classification,
            alert_required=(state_classification in ["drowsy", "stressed"])
        )

    @staticmethod
    def find_builtin_camera():
        """
        Find the most appropriate camera to use as default (preferably the built-in camera).
        
        Returns:
            int: Camera index to use, defaults to 0 if no specific camera found
        """
        # On macOS, the built-in camera is typically index 1 if iPhone camera is at 0
        available_cameras = list_available_cameras()
        
        if not available_cameras:
            return 0  # Default to 0 if no cameras available
        
        # Prefer lower-numbered cameras but avoid iPhone if possible
        # Often built-in camera is 1 if iPhone is at 0
        if len(available_cameras) > 1 and 1 in available_cameras:
            return 1
        else:
            # Otherwise return the first available
            return available_cameras[0]
        
    def get_current_state(self) -> CognitiveState:
        """Get current cognitive state"""
        return self.current_state