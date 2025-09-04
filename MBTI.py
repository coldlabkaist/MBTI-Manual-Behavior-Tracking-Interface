import sys, os, cv2, time
from PyQt5.QtCore import Qt, QThread, pyqtSignal, pyqtSlot, QTimer, QRectF, QEvent
from PyQt5.QtGui import QImage, QPixmap, QPainter, QColor, QFont, QKeySequence, QTransform
from PyQt5.QtWidgets import (
     QApplication, QMainWindow, QWidget, QFileDialog, QSizePolicy,
     QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QListWidgetItem,
     QPushButton, QLineEdit, QLabel, QCheckBox, QSpinBox, QDoubleSpinBox, QSlider,
    QListWidget, QMessageBox, QGridLayout, QVBoxLayout, QHBoxLayout,
    QGroupBox, QComboBox, QDialog, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
 )

# ------------------------------ Video Playback Thread ------------------------------
class VideoThread(QThread):
    frameReady = pyqtSignal(QImage, int)
    finished = pyqtSignal()

    def __init__(self, video_path: str, parent=None):
        super().__init__(parent)
        self.video_path = video_path
        self.cap = None
        self.fps = 0.0
        self.total_frames = 0
        self.current_index = 0
        self.playing = False
        self.stopped = False
        self.seek_frame = None
        self.speed = 1.0
        self._eof_emitted = False

    def open_video(self):
        self.cap = cv2.VideoCapture(self.video_path)
        if not self.cap.isOpened():
            raise RuntimeError(f"Failed to open video: {self.video_path}")
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
        self.current_index = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES)) or 0

    def run(self):
        try:
            self.open_video()
        except Exception as e:
            print("Video open error:", e)
            return
        while not self.stopped:
            if self.seek_frame is not None:
                target = max(0, min(self.seek_frame, self.total_frames - 1))
                self.seek_frame = None
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, target)
                self.current_index = target
                ret, frame = self.cap.read()
                if ret:
                    self.current_index = target + 1
                    self.frameReady.emit(self._to_qimage(frame), target)
            if self.playing:
                ret, frame = self.cap.read()
                if not ret:
                    self.playing = False
                    if not self._eof_emitted:
                        self.finished.emit()
                        self._eof_emitted = True
                    # 현재 위치를 끝으로 클램프
                    self.current_index = self.total_frames
                    QThread.msleep(20)
                    continue
                idx = self.current_index
                self.current_index += 1
                self.frameReady.emit(self._to_qimage(frame), idx)
                if self.fps > 0:
                    QThread.msleep(max(0, int((1000 / self.fps) / self.speed)))
            else:
                QThread.msleep(20)
        self.cap.release()

    def _to_qimage(self, cv_frame):
        rgb = cv2.cvtColor(cv_frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        return QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888).copy()

    @pyqtSlot()
    def stop(self):
        self.stopped = True
        self.playing = False

    @pyqtSlot()
    def play(self):
        self.playing = True
        if self.total_frames > 0 and self.current_index >= self.total_frames - 1:
            self.seek(0)
        self.playing = True

    @pyqtSlot()
    def pause(self):
        self.playing = False

    @pyqtSlot(int)
    def seek(self, frame_index: int):
        self.seek_frame = frame_index
        self._eof_emitted = False

    @pyqtSlot(float)
    def set_speed(self, speed: float):
        self.speed = max(0.1, float(speed))


# ------------------------------ Video Viewer (zoom/pan) ------------------------------
class VideoViewer(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._panning = False
        self._last = None
        self._base = 1.0
        self._zoom = 1.0
        self._content_w = 0
        self._content_h = 0

    def wheelEvent(self, e):
        # 기준 배율(_base) 아래로는 내려가지 않음(= fit-to-view 이하로 축소 금지)
        step_up, step_dn = 1.25, 0.8
        factor = step_up if e.angleDelta().y() > 0 else step_dn
        self._zoom = max(1.0, self._zoom * factor)
        self._apply_transform()
        e.accept()

    def reset_to_100(self):
        self._zoom = 1.0
        self.update_fit_base()
        self._apply_transform()

    def set_content_size(self, w: int, h: int):
        """콘텐츠(비디오 프레임) 픽셀 크기 설정 → 기준 배율 갱신."""
        self._content_w, self._content_h = int(w), int(h)
        self.update_fit_base()
        self._apply_transform()

    def update_fit_base(self):
        """현재 뷰포트에 콘텐츠가 '꽉 차게' 보이도록 기준 배율 계산(비율 유지)."""
        vw, vh = self.viewport().width(), self.viewport().height()
        if self._content_w > 0 and self._content_h > 0 and vw > 0 and vh > 0:
            sx = vw / self._content_w
            sy = vh / self._content_h
            self._base = min(sx, sy)  # 비율 유지
        else:
            self._base = 1.0

    def _apply_transform(self):
        t = QTransform()
        scale = self._base * self._zoom
        t.scale(scale, scale)
        self.setTransform(t)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        # 창 크기 변할 때도 기준 배율 갱신(상대 배율은 유지)
        self.update_fit_base()
        self._apply_transform()

    def mousePressEvent(self, e):
        if e.button() == Qt.MiddleButton or (e.button() == Qt.LeftButton and (e.modifiers() & Qt.ControlModifier)):
            self.setCursor(Qt.ClosedHandCursor)
            self._panning, self._last = True, e.pos()
            e.accept()
        else:
            super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._panning and (e.buttons() & (Qt.MiddleButton | Qt.LeftButton)):
            d = e.pos() - self._last
            self._last = e.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - d.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - d.y())
            e.accept()
        else:
            super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if self._panning and (e.button() in (Qt.MiddleButton, Qt.LeftButton)):
            self._panning = False
            self.setCursor(Qt.ArrowCursor)
            e.accept()
        else:
            super().mouseReleaseEvent(e)


# ------------------------------ Main Window ------------------------------
class MainWindow(QMainWindow):
    SLOTS = 4  # up to 4 keys

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MBTI Manual Behavior Tracking Interface (2.0.0)")
        self.setMinimumSize(1200, 800)
        w = QWidget(self); self.setCentralWidget(w)
        root = QVBoxLayout(w)
        top = QWidget(self)
        top_layout = QHBoxLayout(top)
        root.addWidget(top, 1)  # 상단 영역이 가변적으로 늘어나도록

        # Left: Video
        self.view = VideoViewer()
        top_layout.addWidget(self.view, 10)
        self.scene = self.view.scene()
        self.pix_item = QGraphicsPixmapItem()
        self.scene.addItem(self.pix_item)

        # Right: Control Panel
        right = QWidget(); top_layout.addWidget(right, 3)
        r = QVBoxLayout(right); r.setContentsMargins(6,6,6,6)

        # Group: File
        self.g_file = QGroupBox("Video File"); r.addWidget(self.g_file)
        f = QVBoxLayout(self.g_file)
        self.btn_open_folder = QPushButton("Open Folder")
        self.list_videos = QListWidget()
        self.btn_load_video = QPushButton("Load Video")
        f.addWidget(self.btn_open_folder); f.addWidget(self.list_videos); f.addWidget(self.btn_load_video)

        # Group: Behaviors (input line -> set)
        self.g_beh = QGroupBox("Behaviors"); r.addWidget(self.g_beh)
        b = QVBoxLayout(self.g_beh)
        hl = QHBoxLayout()
        self.edit_behaviors = QLineEdit(); self.edit_behaviors.setPlaceholderText("Enter behaviors, comma-separated")
        self.btn_set_behaviors = QPushButton("Set")
        hl.addWidget(self.edit_behaviors); hl.addWidget(self.btn_set_behaviors)
        b.addLayout(hl)

        # Group: Recording (reworked, but compact)
        self.g_rec = QGroupBox("Recording"); r.addWidget(self.g_rec)
        rec = QGridLayout(self.g_rec)
        self.check_record = QCheckBox("Recording mode")
        rec.addWidget(self.check_record, 0,0,1,2)
        rec.addWidget(QLabel("Limit (min):"), 0,2)
        self.spin_limit = QSpinBox(); self.spin_limit.setRange(1,999); self.spin_limit.setValue(0); self.spin_limit.setAccelerated(True)
        rec.addWidget(self.spin_limit, 0,3)
        # Total을 한 줄 라벨로 통합: "Total  (00:00)"
        self.lbl_rec_total_title = QLabel("Total  (00:00)")
        rec.addWidget(self.lbl_rec_total_title, 1,0,1,4)

        # 4 slots rows: behavior combo + set key + key label + slot timer
        self.slot_ui = []
        for i in range(self.SLOTS):
            row = 2 + i*2
            title = QLabel(f"Slot {i+1}  (00:00)")
            rec.addWidget(title, row, 0)
            cmb = QComboBox(); cmb.addItem("(None)")
            btn = QPushButton("Set physical key")
            keylab = QLabel("-")
            rec.addWidget(cmb,    row,   1)
            rec.addWidget(btn,    row,   2)
            rec.addWidget(keylab, row,   3)
            self.slot_ui.append({'cmb': cmb, 'btn': btn, 'keylab': keylab, 'title': title})

        self.check_overlay = QCheckBox("Show overlay"); self.check_overlay.setChecked(True)
        rec.addWidget(self.check_overlay, 2+self.SLOTS*2, 0, 1, 4)

        # Group: Bookmarks
        self.g_bm = QGroupBox("Bookmarks"); r.addWidget(self.g_bm)
        bm = QVBoxLayout(self.g_bm)
        self.list_bookmarks = QListWidget()
        bmhl = QHBoxLayout()
        self.btn_add_bm = QPushButton("Add Bookmark")
        self.btn_go_bm  = QPushButton("Go to Bookmark")
        self.btn_del_bm = QPushButton("Delete Bookmark")
        bmhl.addWidget(self.btn_add_bm); bmhl.addWidget(self.btn_go_bm); bmhl.addWidget(self.btn_del_bm)
        bm.addWidget(self.list_bookmarks); bm.addLayout(bmhl)

        # Group: Data
        self.g_data = QGroupBox("Data"); r.addWidget(self.g_data)
        dl = QHBoxLayout(self.g_data)
        self.btn_import = QPushButton("Import Labels")
        self.btn_export = QPushButton("Export Labels")
        self.btn_preview = QPushButton("Preview Result")
        dl.addWidget(self.btn_import); dl.addWidget(self.btn_export); dl.addWidget(self.btn_preview)

        r.addStretch(1)
        
        # Group: Playback
        self.g_play = QGroupBox("Playback")
        p = QGridLayout(self.g_play)
        self.btn_play = QPushButton("Play/Pause")
        self.slider = QSlider(Qt.Horizontal); self.slider.setEnabled(False)
        self.lbl_frame = QLabel("Frame: 0000 / 0000")
        self.lbl_time  = QLabel("Time: 00:00 / 00:00")
        # 1행: 슬라이더 전폭
        p.addWidget(self.slider, 0, 0, 1, 7)
        # 2행: 좌측 Speed, 가운데 Play(가로 확장), 우측 Frame/Time
        p.addWidget(QLabel("Speed:"), 1, 0, 1, 1)
        self.spin_speed = QDoubleSpinBox()
        self.spin_speed.setDecimals(1)         # 0.1 단위
        self.spin_speed.setRange(0.3, 5.0)     # 범위 0.3 ~ 5.0
        self.spin_speed.setSingleStep(0.1)     # 스텝 0.1
        self.spin_speed.setValue(1.0)          # 기본 1.0×
        self.spin_speed.setSuffix("×")         # 표시: 배속 기호
        self.spin_speed.setAccelerated(True)   # 화살표 꾹 누르면 가속
        p.addWidget(self.spin_speed, 1, 1, 1, 1)
        self.btn_play.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        p.addWidget(self.btn_play, 1, 2, 1, 3)
        self.lbl_frame.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl_time.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        p.addWidget(self.lbl_frame, 1, 5, 1, 1)
        p.addWidget(self.lbl_time,  1, 6, 1, 1)
        for col in (2,3,4):
            p.setColumnStretch(col, 1)
        for col in (0,1,5,6):
            p.setColumnStretch(col, 0)
        root.addWidget(self.g_play, 0)

        # State
        self.video_thread = None
        self.video_loaded = False
        self.video_folder = ""
        self.current_video_path = None
        self.current_frame_idx = 0
        self.fps = 30.0
        self.total_frames = 0
        self.recording = False
        self.record_start_frame = None
        self.record_start_ms = None
        self.record_total_ms = 0
        self.record_limit_end_frame = None  # 제한 프레임
        self._record_arming_pending = False
        self._fit_initialized = False
        self.data_modified = False

        self.behaviors = []
        self.frame_flags = []           # [n_behaviors][total_frames]
        self.behavior_durations = []    # ms per behavior

        # 4 input slots
        self.slots = [{'key': None, 'behavior': None, 'ms': 0, 'pressed': False,
                       'start_ms': 0, 'start_frame': 0} for _ in range(self.SLOTS)]
        self.key_to_slot = {}  # (qt_key, scan) -> slot_idx
        self.pending_key_capture = None

        # Overlays (view 기준의 QLabel들)
        self.overlay_labels = []
        self._init_overlays()
        # 뷰 리사이즈 감지 → 재배치
        self.view.viewport().installEventFilter(self)

        # Connect
        self.btn_open_folder.clicked.connect(self.open_folder_dialog)
        self.btn_load_video.clicked.connect(self.load_selected_video)
        self.list_videos.itemDoubleClicked.connect(self.load_selected_video)
        self.btn_play.clicked.connect(self.toggle_play_pause)
        self.slider.sliderPressed.connect(self.on_slider_pressed)
        self.slider.sliderReleased.connect(self.on_slider_released)
        self.slider.sliderMoved.connect(self.on_slider_moved)

        self.btn_set_behaviors.clicked.connect(self.define_behaviors)
        self.check_record.stateChanged.connect(self.on_record_toggled)
        self.btn_add_bm.clicked.connect(self.add_bookmark)
        self.btn_go_bm.clicked.connect(self.jump_to_bookmark)
        self.btn_del_bm.clicked.connect(self.delete_bookmark)
        self.btn_import.clicked.connect(self.import_labels)
        self.btn_export.clicked.connect(self.export_labels)
        self.btn_preview.clicked.connect(self.preview_result)
        self.spin_speed.valueChanged.connect(self.on_speed_changed)

        for idx, s in enumerate(self.slot_ui):
            s['btn'].clicked.connect(lambda _, i=idx: self.start_capture(i))
            s['cmb'].currentIndexChanged.connect(lambda _, i=idx: self.on_slot_behavior_changed(i))

        self.update_ui_state()
        # Enter 로 behaviors 확정
        self.edit_behaviors.returnPressed.connect(self.btn_set_behaviors.click)
        # Focus policy: MainWindow 기본 StrongFocus, 자식 위젯 NoFocus(입력칸만 예외)
        self.setFocusPolicy(Qt.StrongFocus)
        self.apply_no_focus()

    def apply_no_focus(self):
        for w in self.findChildren(QWidget):
            if w is self.edit_behaviors:
                w.setFocusPolicy(Qt.ClickFocus)   # ← 예외
            else:
                w.setFocusPolicy(Qt.NoFocus)
        self.setFocusPolicy(Qt.StrongFocus)
        self.activateWindow()
        self.raise_()
        # 메인 초기 포커스는 MainWindow로 유지(입력은 클릭 시 활성화)
        self.setFocus(Qt.ActiveWindowFocusReason)

    # view 리사이즈 시 오버레이 재배치
    def eventFilter(self, obj, ev):
        if obj is self.view.viewport() and ev.type() == QEvent.Resize:
            self._position_overlays()
        return super().eventFilter(obj, ev)

    def _guard_unsaved(self, reason_text: str) -> bool:
        """
        저장되지 않은 라벨이 있으면 경고를 띄워 진행 여부를 결정한다.
        reason_text 예: 'load a new video', 'change behaviors'
        return True → 계속 진행, False → 중단
        """
        if not getattr(self, 'data_modified', False):
            return True
        box = QMessageBox(self)
        box.setWindowTitle("Unsaved labels")
        box.setIcon(QMessageBox.Warning)
        box.setText(f"There are unsaved label changes.\nDo you want to export them before you {reason_text}?")
        btn_export  = box.addButton("Export now", QMessageBox.AcceptRole)
        btn_discard = box.addButton("Continue without saving", QMessageBox.DestructiveRole)
        btn_cancel  = box.addButton("Cancel", QMessageBox.RejectRole)
        box.exec_()
        clicked = box.clickedButton()
        if clicked is btn_cancel:
            return False
        if clicked is btn_export:
            # 사용자가 저장 대화상자에서 취소할 수도 있으므로, 저장 후 플래그 상태로 판단
            self.export_labels()
            return not self.data_modified
        # 저장하지 않고 진행 → 변경 내용 폐기로 간주
        self.data_modified = False
        return True

    # ---------- overlays ----------
    def _init_overlays(self):
        # view.viewport() 좌표계에 고정되는 라벨들
        from PyQt5.QtWidgets import QLabel
        self.overlay_labels = []
        self._overlay_colors = [
            "rgba(217,  99,  78, 180)", 
            "rgba(242, 250,  97, 180)",
            "rgba( 97, 250, 133, 180)",
            "rgba(108, 152, 230, 180)",
        ]
        self._overlay_default_bg = "rgba(0,0,0,150)"
        self._overlay_min_w = 100
        self._overlay_base_w = 200
        self._overlay_h = 44

        for _ in range(self.SLOTS):
            lab = QLabel("", self.view.viewport())
            lab.setVisible(False)
            lab.setAlignment(Qt.AlignCenter)
            lab.setFixedSize(self._overlay_base_w, self._overlay_h)
            lab.setStyleSheet("color: white; font-weight: 600; border-radius: 8px;")
            self.overlay_labels.append(lab)
        self._position_overlays()

    def _position_overlays(self):
        # 뷰포트 상단에서 좌→우로 균등 간격 배치
        vp = self.view.viewport()
        w, h = vp.width(), vp.height()
        margin = 10
        gap = 8
        n = len(self.overlay_labels)
        if n == 0:
            return
        # 창이 작아도 겹치지 않도록, 가용폭에 맞춰 라벨 폭을 동적으로 축소
        total_gap = gap * (n - 1)
        max_w_for_each = (w - 2*margin - total_gap) / max(1, n)
        labw = max(self._overlay_min_w, min(self._overlay_base_w, int(max_w_for_each)))
        y = margin
        xs = [margin + i*(labw + gap) for i in range(n)]
        for i, lab in enumerate(self.overlay_labels):
            # 색상 적용(1~4는 팔레트, 그 이후는 기본색)
            bg = self._overlay_colors[i] if i < len(self._overlay_colors) else self._overlay_default_bg
            lab.setStyleSheet(f"background: {bg}; color: white; font-weight: 700; border-radius: 8px;")
            lab.setFixedSize(labw, self._overlay_h)
            lab.move(int(xs[i]), y)

    def _set_overlay_text(self, slot_idx, text):
        self.overlay_labels[slot_idx].setText(text)

    # ---------- UI states ----------
    def _rec_info_labels(self):
        """Recording 패널 내에서 정보 표시용 라벨들을 모아 반환"""
        labels = []
        # 총 시간 라벨(예: 'Total  (00:00)')가 있으면 포함
        if hasattr(self, "lbl_rec_total_title"):
            labels.append(self.lbl_rec_total_title)
        # 슬롯 타이틀 라벨: slot_ui[i]['title'] 로 관리(없으면 무시)
        if hasattr(self, "slot_ui"):
            for s in self.slot_ui:
                if 'title' in s:
                    labels.append(s['title'])
        return tuple(labels)

    def _refresh_slot_title_styles(self, recording: bool = False):
        """슬롯 타이틀 라벨의 색을 상태에 맞춰 갱신.
           - behavior 미지정: 회색
           - 그 외: 검정색(Recording/Idle 모두)"""
        if not hasattr(self, "slot_ui"):
            return
        for i, s in enumerate(self.slot_ui):
            lab = s.get('title')
            if lab is None:
                continue
            bi = self.slots[i]['behavior'] if i < len(self.slots) else None
            if bi is None:
                lab.setStyleSheet("color: gray;")
            else:
                # 녹화 중에도 정보는 선명한 검정
                lab.setStyleSheet("color: black;")
        # 총 시간 라벨은 항상 검정
        if hasattr(self, "lbl_rec_total_title"):
            self.lbl_rec_total_title.setStyleSheet("color: black;")

    def _set_group_enabled(self, group: QGroupBox, enabled: bool, exceptions: tuple = ()):
        """
        그룹 단위 enable/disable. exceptions가 있을 때는 그룹을 켜둔 채,
        자식 위젯만 개별 제어(예외 위젯은 활성, 나머지는 비활성).
        """
        if not exceptions:
            group.setEnabled(enabled)
            for w in group.findChildren(QWidget):
                w.setEnabled(enabled)
            return
        # 부분 비활성: 부모는 켠 상태에서 자식만 선별 제어
        group.setEnabled(True)
        ex_set = set(exceptions)
        for w in group.findChildren(QWidget):
            w.setEnabled(w in ex_set)

    def update_ui_state(self):
        """
        상태표:
          1) 초기: Video File만 enabled, 나머지(Playback 포함) disabled
          2) 영상 로드: Video File + Behaviors enabled, 나머지 disabled
          3) 영상+Behavior 모두: 기본적으로 모두 enabled 가능.
             - rec False + 재생중 : Recording disabled
             - rec False + 정지중 : 모든 영역 enabled
             - rec True  + 재생중 : Recording, Bookmarks, Data, Playback(단 Play버튼 제외) disabled
             - rec True  + 정지중 : Recording(단 체크박스 제외), Data disabled
        """
        video_loaded = self.video_loaded
        beh_ready = bool(self.behaviors)
        recording = self.recording
        playing = getattr(self, 'is_playing', False)

        # 1) 초기 상태
        if not video_loaded:
            self._set_group_enabled(self.g_file, True)
            self._set_group_enabled(self.g_beh, False)
            self._set_group_enabled(self.g_rec, False)
            self._set_group_enabled(self.g_bm,  False)
            self._set_group_enabled(self.g_data, False)
            self._set_group_enabled(self.g_play, False)
            return

        # 2) 영상만 로드
        if video_loaded and not beh_ready:
            self._set_group_enabled(self.g_file, True)
            self._set_group_enabled(self.g_beh, True)
            self._set_group_enabled(self.g_rec, False)
            self._set_group_enabled(self.g_bm,  False)
            self._set_group_enabled(self.g_data, False, exceptions=(self.btn_import,))
            self._set_group_enabled(self.g_play, False)
            return

        # 3) 영상+Behavior 준비됨 → 기본은 모두 enabled
        self._set_group_enabled(self.g_file, True)
        self._set_group_enabled(self.g_beh, True)
        self._set_group_enabled(self.g_rec, True)
        self._set_group_enabled(self.g_bm,  True)
        self._set_group_enabled(self.g_data, True)
        self._set_group_enabled(self.g_play, True)

        self._refresh_slot_title_styles(recording=False)

        # 추가 규칙
        if not recording and playing:
            # 녹화 off + 재생중 → Recording만 잠금
            self._set_group_enabled(self.g_rec, False)
            return
        if not recording and not playing:
            # 녹화 off + 정지중 → 모두 활성 (이미 반영)
            return
        if recording and playing:
            # 녹화 on + 재생중 → Recording, Bookmarks, Data, Playback(Play 제외) 비활성
            self._set_group_enabled(self.g_rec,  False, exceptions=self._rec_info_labels())
            self._set_group_enabled(self.g_bm,   False)
            self._set_group_enabled(self.g_data, False)
            self._set_group_enabled(self.g_play, False, exceptions=(self.btn_play,))
            self._refresh_slot_title_styles(recording=True)
            return
        if recording and not playing:
            # 녹화 on + 정지중 → Recording(체크박스 2개만 예외), Data 비활성
            self._set_group_enabled(self.g_rec,  False, exceptions=(self.check_record, self.check_overlay) + self._rec_info_labels())
            self._set_group_enabled(self.g_bm,   False) 
            self._set_group_enabled(self.g_data, False)
            self._refresh_slot_title_styles(recording=True)
            return

    # ---------- helpers ----------
    def _fmt_ms(self, ms):
        s = int(ms // 1000); return f"{s//60:02d}:{s%60:02d}"

    def _set_total_label_text(self, ms):
        self.lbl_rec_total_title.setText(f"Total  ({self._fmt_ms(ms)})")

    def _update_slot_title(self, i, ms=None):
        """슬롯 제목을 'Slot N (mm:ss)'로 갱신."""
        sl = self.slots[i]
        if ms is None:
            ms = sl['ms']
            if sl['pressed']:
                ms += max(0, self._ms_now() - sl['start_ms'])
        self.slot_ui[i]['title'].setText(f"Slot {i+1}  ({self._fmt_ms(ms)})")

    def _frame_ms(self, frames):
        return int((frames / self.fps) * 1000) if self.fps else frames * 33

    def _slot_valid(self, i):
        return (self.slots[i]['key'] is not None) and (self.slots[i]['behavior'] is not None)

    def _rebuild_key_index(self):
        self.key_to_slot.clear()
        for i, sl in enumerate(self.slots):
            if sl['key'] is not None:
                self.key_to_slot[sl['key']] = i

    def _key_to_slot(self, event):
        """(qt_key, scan) 우선 매칭, 실패 시 qt_key만으로 fallback."""
        ktuple = (event.key(), event.nativeScanCode())
        idx = self.key_to_slot.get(ktuple)
        if idx is not None:
            return idx
        qk = event.key()
        for i, sl in enumerate(self.slots):
            if sl['key'] and sl['key'][0] == qk:
                return i
        return None

    # ---------- folder/video ----------
    def open_folder_dialog(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Video Folder")
        if not folder: return
        files = [f for f in os.listdir(folder)
                 if os.path.isfile(os.path.join(folder, f)) and f.lower().split('.')[-1] in ('mp4','avi','mov','mkv','wmv')]
        files.sort()
        self.list_videos.clear(); self.list_videos.addItems(files)
        self.video_folder = folder

    def load_selected_video(self):
        if not self._guard_unsaved("load a new video"):
            return
        item = self.list_videos.currentItem()
        if not item: return
        self.current_video_path = item.text()
        path = os.path.join(self.video_folder, item.text())
        if self.video_thread:
            self.video_thread.stop(); self.video_thread.wait(); self.video_thread = None
        self.video_thread = VideoThread(path)
        self.video_thread.frameReady.connect(self.on_frame_ready)
        self.video_thread.finished.connect(self.on_video_finished)
        self.video_thread.start()

        cap = cv2.VideoCapture(path)
        self.fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
        cap.release()

        self.slider.setRange(0, max(0, self.total_frames - 1))
        self.slider.setValue(0)
        self.current_frame_idx = 0
        self._fit_initialized = False
        self.update_time_labels(0)

        self.video_loaded = True

        # reset behaviors/flags when loading new video
        self.behaviors = []
        self.frame_flags = []
        self.behavior_durations = []
        self.frame_index = list(range(self.total_frames))
        self.edit_behaviors.setEnabled(True)
        # reset slots
        for i, sl in enumerate(self.slots):
            sl.update({'key': None, 'behavior': None, 'ms': 0, 'pressed': False, 'start_ms': 0, 'start_frame': 0})
            self.slot_ui[i]['keylab'].setText("-")
            self._update_slot_title(i, 0)
            self.slot_ui[i]['cmb'].clear(); self.slot_ui[i]['cmb'].addItem("(None)")
            if 'title' in self.slot_ui[i]:
                self.slot_ui[i]['title'].setStyleSheet("color: gray;")
        # 총 타이머 00:00
        self.record_total_ms = 0
        self._set_total_label_text(0)
        self._rebuild_key_index()
        # overlay reposition on first frame
        self._position_overlays()
        # request first frame
        if self.video_thread: self.video_thread.seek(0)
        self.apply_no_focus()
        self.data_modified = False
        self.update_ui_state()
        self._refresh_slot_title_styles(recording=False)

    # ---------- playback ----------
    def toggle_play_pause(self):
        if not self.video_loaded or not self.video_thread: return
        if getattr(self, 'is_playing', False):
            self.video_thread.pause(); self.is_playing = False; self.btn_play.setText("Play")
        else:
            if self.current_frame_idx >= max(0, self.total_frames - 1):
                self.video_thread.seek(0)
            self.video_thread.play(); self.is_playing = True; self.btn_play.setText("Pause")
        self.update_ui_state()

    def on_slider_pressed(self):
        if self.video_thread and getattr(self, 'is_playing', False):
            self.video_thread.pause()

    def on_slider_moved(self, value):
        if not self.video_loaded or not self.video_thread: return
        if self.recording and self.record_start_frame is not None and value < self.record_start_frame:
            value = self.record_start_frame
        if self.recording and any(sl['pressed'] for sl in self.slots):
            return
        self.video_thread.seek(int(value))

    def on_slider_released(self):
        if self.video_thread and getattr(self, 'is_playing', False):
            self.video_thread.play()

    def on_frame_ready(self, image: QImage, frame_index: int):
        self.current_frame_idx = frame_index
        self.pix_item.setPixmap(QPixmap.fromImage(image))
        self.scene.setSceneRect(self.pix_item.boundingRect())
        # 기준(시작 프레임/시각/제한프레임)을 확정
        if self.recording and self._record_arming_pending:
            self.record_start_frame = self.current_frame_idx
            self.record_start_ms = self._ms_now()
            if self.spin_limit.value() > 0 and self.fps:
                limit_frames = int(self.spin_limit.value() * 60 * self.fps)
                self.record_limit_end_frame = min(self.total_frames - 1,
                                                  self.record_start_frame + limit_frames)
            else:
                self.record_limit_end_frame = None
            self._set_total_label_text(0)
            self._record_arming_pending = False
        if frame_index == 0 and not self._fit_initialized:
            # 새 영상 첫 프레임에서만 뷰 기준 100% 적용
            self.view.set_content_size(image.width(), image.height())
            self.view.reset_to_100()
            self._position_overlays()
            self._fit_initialized = True
        self.slider.blockSignals(True); self.slider.setValue(frame_index); self.slider.blockSignals(False)
        self.update_time_labels(frame_index)

        # recording timers live update
        if self.recording and self.record_start_ms is not None:
            running = max(0, self._ms_now() - self.record_start_ms)
            self._set_total_label_text(running)
            # per-slot display (include ongoing press)
            for i, sl in enumerate(self.slots):
                disp = sl['ms']
                if sl['pressed']:
                    disp += max(0, self._ms_now() - sl['start_ms'])
                self._update_slot_title(i, disp)

        # 현재 프레임의 behavior를 0으로 초기화
        # 눌려있는(slot.pressed) 슬롯의 behavior만 1로 설정
        if (self.recording and getattr(self, 'is_playing', False)
                and self.behaviors and self.frame_flags
                and 0 <= frame_index < self.total_frames):
            # 이번 세션에서 측정할 행동 컬럼 집합(슬롯에 지정된 것들)
            override_cols = {sl['behavior'] for sl in self.slots if sl['behavior'] is not None}
            # 해당 컬럼들만 0으로 초기화
            for bi in override_cols:
                self.frame_flags[bi][frame_index] = 0
            # 눌린 슬롯의 행동만 1
            for sl in self.slots:
                bi = sl['behavior']
                if bi is not None and sl['pressed']:
                    self.frame_flags[bi][frame_index] = 1
            self.data_modified = True
        
        # 제한시간 도달 시 자동 정지
        if (self.recording and
            self.record_limit_end_frame is not None and
            frame_index >= self.record_limit_end_frame):
            if self.video_thread:
                self.video_thread.pause()
                self.is_playing = False
            # 체크박스 해제 → stop_recording() 호출
            self.check_record.blockSignals(True)
            self.check_record.setChecked(False)
            self.check_record.blockSignals(False)
            self.stop_recording()

    def on_video_finished(self):
        self.is_playing = False
        self.btn_play.setText("Play")
        # 레코딩 중이면 안전하게 종료 + 체크박스 해제
        if self.recording:
            self.check_record.blockSignals(True)
            self.check_record.setChecked(False)
            self.check_record.blockSignals(False)
            self.stop_recording()
        self.update_ui_state()

    def update_time_labels(self, frame_index: int):
        self.lbl_frame.setText(f"Frame: {frame_index:04d} / {self.total_frames:04d}")
        if self.fps:
            tot_s = int(self.total_frames / self.fps)
            cur_s = int(frame_index / self.fps)
            self.lbl_time.setText(f"Time: {cur_s//60:02d}:{cur_s%60:02d} / {tot_s//60:02d}:{tot_s%60:02d}")
        else:
            self.lbl_time.setText("Time: --:-- / --:--")

    def on_speed_changed(self, value):
        v = float(value)
        if self.video_thread:
            self.video_thread.set_speed(v)

    # ---------- behaviors ----------
    def define_behaviors(self):
        if not self.video_loaded: return
        # 가드: 기존 behavior가 있고 저장되지 않은 변경이 있으면 확인
        if self.behaviors and not self._guard_unsaved("change behaviors"):
            return
        text = self.edit_behaviors.text().strip()
        if not text: return
        names = []
        for t in [s.strip() for s in text.split(',') if s.strip()]:
            if t not in names: names.append(t)
        self.behaviors = names
        n = len(names)
        self.frame_flags = [[0]*self.total_frames for _ in range(n)]
        self.behavior_durations = [0]*n

        # populate slot combos with "(None) + behaviors"  + 슬롯 상태 초기화
        for s in self.slot_ui:
            s['cmb'].blockSignals(True)
            s['cmb'].clear(); s['cmb'].addItem("(None)")
            s['cmb'].addItems(self.behaviors)
            s['cmb'].blockSignals(False)
        for i, sl in enumerate(self.slots):
            # behavior만 리셋(키는 유지), 시간/표시 초기화
            sl['behavior'] = None
            sl['ms'] = 0
            sl['pressed'] = False
            self._update_slot_title(i, 0)
            if 'title' in self.slot_ui[i]:
                self.slot_ui[i]['title'].setStyleSheet("color: gray;")
            self._set_overlay_text(i, "")
            self.overlay_labels[i].hide()
            # 콤보 (None)으로 고정
            self.slot_ui[i]['cmb'].blockSignals(True)
            self.slot_ui[i]['cmb'].setCurrentIndex(0)
            self.slot_ui[i]['cmb'].blockSignals(False)
        # 총 타이머 00:00
        self.record_total_ms = 0
        self._set_total_label_text(0)

        # prepare overlays text to match slot behavior name at press time (dynamic)
        QMessageBox.information(self, "Behaviors Set", "Behaviors defined. Assign physical keys per slot.")

        # enable export/preview only when there is data later
        self.btn_preview.setEnabled(True)
        self.btn_export.setEnabled(True)
        self.update_ui_state()
        self._refresh_slot_title_styles(recording=self.recording)

    def on_slot_behavior_changed(self, slot_idx: int):
        """슬롯의 behavior 콤보가 바뀌었을 때: 중복 가드 + 색 갱신."""
        if slot_idx < 0 or slot_idx >= len(self.slot_ui):
            return
        cmb = self.slot_ui[slot_idx]['cmb']
        text = cmb.currentText().strip()

        # "(None)" 처리
        if text == "(None)":
            sl = self.slots[slot_idx]
            # 진행 중이면 즉시 중단/오버레이 off
            if sl.get('pressed'):
                sl['pressed'] = False
                if self.check_overlay.isChecked():
                    self.overlay_labels[slot_idx].hide()
            # behavior 해제 + 시간 리셋
            sl['behavior'] = None
            sl['ms'] = 0
            # 색: 미지정 → 회색
            if 'title' in self.slot_ui[slot_idx]:
                self.slot_ui[slot_idx]['title'].setStyleSheet("color: gray;")
                self._update_slot_title(slot_idx, 0)
            # 오버레이 텍스트도 정리
            self._set_overlay_text(slot_idx, "")
            return

        # 문자열을 behaviors 인덱스로 매핑
        try:
            bi = self.behaviors.index(text)
        except ValueError:
            # 정의되지 않은 이름이 들어왔다면 안전하게 해제
            cmb.setCurrentIndex(0)
            return

        # 중복 행동 가드: 다른 슬롯이 이미 같은 behavior를 사용 중이면 금지
        for i, sl in enumerate(self.slots):
            if i != slot_idx and sl.get('behavior') == bi:
                QMessageBox.warning(self, "Duplicate behavior",
                                    f"'{text}' is already assigned to Slot {i+1}.")
                cmb.blockSignals(True)
                cmb.setCurrentIndex(0)  # (None)으로 되돌림
                cmb.blockSignals(False)
                # 회색으로 반영
                if 'title' in self.slot_ui[slot_idx]:
                    self.slot_ui[slot_idx]['title'].setStyleSheet("color: gray;")
                self.slots[slot_idx]['behavior'] = None
                self._set_overlay_text(slot_idx, "")
                return

        # 정상 할당: 슬롯에 behavior 인덱스 저장
        sl = self.slots[slot_idx]
        # 진행 중이면 즉시 중단/오버레이 off
        if sl.get('pressed'):
            sl['pressed'] = False
            if self.check_overlay.isChecked():
                self.overlay_labels[slot_idx].hide()
        sl['behavior'] = bi
        sl['ms'] = 0
        # 색: 지정됨 → 검정
        if 'title' in self.slot_ui[slot_idx]:
            self.slot_ui[slot_idx]['title'].setStyleSheet("color: black;")
            self._update_slot_title(slot_idx, 0)
        # 오버레이 텍스트 갱신
        self._set_overlay_text(slot_idx, text)
        # 상태에 맞춰 다른 라벨 색도 재정렬(녹화 중/아닐 때 규칙 유지)
        self._refresh_slot_title_styles(recording=self.recording)
        # 필요 시 UI 상태 갱신
        self.update_ui_state()

    # ---------- capture (per-slot & multi) ----------
    def start_capture(self, slot_idx):
        self.check_record.setEnabled(False)
        if self.recording:
            QMessageBox.information(self, "Locked", "Cannot capture keys during recording.")
            return
        self.pending_key_capture = slot_idx
        self.slot_ui[slot_idx]['keylab'].setText("Press any key...")
        self.activateWindow(); self.raise_()
        self.setFocus(Qt.ActiveWindowFocusReason)
        self.grabKeyboard()

    # ---------- recording ----------
    def on_record_toggled(self, state):
        if state == Qt.Checked:
            if not self.start_recording():
                # 시작 실패 시 체크 되돌림
                self.check_record.setChecked(False)
        else:
            self.stop_recording()
        self.update_ui_state()

    def _validate_recording_ready(self):
        # behavior가 선택된 슬롯만 검사
        beh_slots = [i for i in range(self.SLOTS) if self.slots[i]['behavior'] is not None]
        if not beh_slots:
            QMessageBox.warning(self, "Invalid", "Select at least one behavior for a slot.")
            return False
        # 선택된 behavior 슬롯은 반드시 키가 있어야 함
        missing = [i+1 for i in beh_slots if self.slots[i]['key'] is None]
        if missing:
            QMessageBox.warning(self, "Invalid", f"Slots with a behavior must have a physical key (check slots: {missing}).")
            return False
        # 중복 체크(선택된 behavior 슬롯끼리만)
        keys = [self.slots[i]['key'] for i in beh_slots]
        if len(set(keys)) != len(keys):
            QMessageBox.warning(self, "Invalid", "Duplicate physical keys across behavior-assigned slots.")
            return False
        behs = [self.slots[i]['behavior'] for i in beh_slots]
        if len(set(behs)) != len(behs):
            QMessageBox.warning(self, "Invalid", "Behaviors must be unique across slots.")
            return False
        return True

    def start_recording(self):
        self.update_ui_state()
        if not self.behaviors:
            QMessageBox.warning(self, "No Behaviors", "Define behaviors first.")
            return False
        if not self._validate_recording_ready():
            return False

        selected_beh_indices = [sl['behavior'] for sl in self.slots if sl['behavior'] is not None]
        already_labeled = []
        for bi in selected_beh_indices:
            # 해당 행동 컬럼에 1이 한 번이라도 있으면 과거 라벨 존재로 간주
            if bi is not None and any(self.frame_flags[bi]):
                already_labeled.append(bi)
        if already_labeled:
            names = ", ".join(self.behaviors[bi] for bi in sorted(set(already_labeled)))
            box = QMessageBox(self)
            box.setWindowTitle("Confirm re-measure")
            box.setIcon(QMessageBox.Warning)
            box.setText(f"The following behaviors already have labels:\n{names}\n\n"
                        "Continuing will overwrite these behaviors on frames you pass during this session.\n"
                        "Do you want to continue?")
            btn_yes = box.addButton("Continue", QMessageBox.AcceptRole)
            btn_cancel = box.addButton("Cancel", QMessageBox.RejectRole)
            box.exec_()
            if box.clickedButton() is btn_cancel:
                return False

        # reset timers
        self.record_total_ms = 0
        self._set_total_label_text(0)
        for i, sl in enumerate(self.slots):
            sl['ms'] = 0
            self._update_slot_title(i, 0)

        # mark state
        self.recording = True
        # 바로 고정하지 않고, 다음 on_frame_ready에서 확정
        self.record_start_frame = None
        self.record_start_ms = None
        self.record_limit_end_frame = None
        self._record_arming_pending = True

        self._rebuild_key_index()
        self.update_ui_state()
        return True

    def stop_recording(self):
        if not self.recording: return
        # finalize any pressed slots
        any_finalized = False
        for i, sl in enumerate(self.slots):
            if sl['pressed'] and sl['behavior'] is not None:
                bi = sl['behavior']
                end_ms = self._ms_now()
                dur = max(0, end_ms - sl['start_ms'])
                sl['ms'] += dur
                self.behavior_durations[bi] += dur
                s, e = sl['start_frame'], self.current_frame_idx
                if e < s: s, e = e, s
                for f in range(max(0, s), min(self.total_frames-1, e)+1):
                    self.frame_flags[bi][f] = 1
                sl['pressed'] = False
                if self.check_overlay.isChecked():
                    self.overlay_labels[i].hide()
                any_finalized = True
            # update UI time
            self._update_slot_title(i)

        # keep total timer label (do not reset)
        if self.record_start_ms is not None:
            self.record_total_ms = max(0, self._ms_now() - self.record_start_ms)
            self._set_total_label_text(self.record_total_ms)

        self.recording = False
        self._record_arming_pending = False
        self.record_limit_end_frame = None
        if any_finalized:
            self.data_modified = True
        self.update_ui_state()

    def _ms_now(self):
        # use frame index for stability with video timing
        return int((self.current_frame_idx / self.fps) * 1000) if self.fps else int(time.time()*1000)

    # ---------- bookmarks ----------
    def add_bookmark(self):
        f = int(self.current_frame_idx)
        if self.fps:
            total_seconds = int(f / self.fps)
            mm, ss = divmod(total_seconds, 60)
        else:
            mm, ss = 0, 0
        text = f"Frame {f} ({mm:02d}:{ss:02d})"
        # 중복 방지: 데이터(UserRole)로 비교
        for i in range(self.list_bookmarks.count()):
            it = self.list_bookmarks.item(i)
            if it.data(Qt.UserRole) == f:
                return
        it = QListWidgetItem(text)
        it.setData(Qt.UserRole, f)
        self.list_bookmarks.addItem(it)

    def jump_to_bookmark(self):
        item = self.list_bookmarks.currentItem()
        if not item or not self.video_thread: return
        # 저장된 프레임 번호를 직접 사용(파싱 불필요)
        frame = item.data(Qt.UserRole)
        if frame is None:
            # 구버전 북마크(문자열만 저장) 호환
            parts = item.text().split()
            try: frame = int(parts[1])
            except: return
        # 녹화 중엔 시작 프레임 이전으로 점프 금지(설계대로 클램프)
        if self.recording and self.record_start_frame is not None:
            frame = max(frame, self.record_start_frame)
        # 범위 보정 후 실제 점프
        frame = max(0, min(int(frame), self.total_frames - 1))
        self.video_thread.seek(frame)

    def delete_bookmark(self):
        for it in self.list_bookmarks.selectedItems():
            self.list_bookmarks.takeItem(self.list_bookmarks.row(it))

    # ---------- preview/import/export (lightweight CSV) ----------
    def preview_result(self):
        if not self.behaviors or not self.frame_flags:
            QMessageBox.information(self, "Preview", "No data to preview.")
            return
        dlg = QDialog(self); dlg.setWindowTitle("Preview Result")
        dlg.setMinimumSize(900, 600)
        v = QVBoxLayout(dlg)
        meta = QWidget(dlg)
        meta.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        meta_v = QVBoxLayout(meta); meta_v.setContentsMargins(0,0,0,0)
        # 상단 요약
        video_name = self.list_videos.currentItem().text() if self.list_videos.currentItem() else "N/A"
        hdr = QLabel(f"<b>Video:</b> {video_name} &nbsp;&nbsp; "
                     f"<b>Frames:</b> {self.total_frames} &nbsp;&nbsp; "
                     f"<b>FPS:</b> {self.fps:.2f}")
        meta_v.addWidget(hdr)
        frame_dur = 1.0 / self.fps if self.fps else 0
        lines = []
        for i, name in enumerate(self.behaviors):
            cnt = sum(self.frame_flags[i])
            lines.append(f"{name}: {cnt} frames (~{cnt*frame_dur:.2f}s)")
        meta_v.addWidget(QLabel("<b>Totals per behavior</b><br>" + "<br>".join(lines)))
        
        # 하단 테이블: 0..last 모든 프레임 표시 (작은 표 + 스크롤)
        frames_list = list(range(self.total_frames))
        meta_v.addWidget(QLabel(f"All frames: 0 .. {self.total_frames-1}"))
        v.addWidget(meta, 0)  # stretch 0 → 메타는 그대로, 아래 테이블만 늘어남
        table = QTableWidget(len(frames_list), 1 + len(self.behaviors), dlg)
        headers = ["Frame"] + self.behaviors
        table.setHorizontalHeaderLabels(headers)
        # 작은 폰트/행높이/스크롤
        small_font = table.font(); small_font.setPointSize(9)
        table.setFont(small_font)
        table.verticalHeader().setDefaultSectionSize(16)  # 행 높이
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        # 첫 컬럼은 내용 기준, 나머지는 스트레치
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        for c in range(1, 1+len(self.behaviors)):
            table.horizontalHeader().setSectionResizeMode(c, QHeaderView.Stretch)

        # 데이터 채우기
        for r, f in enumerate(frames_list):
            itf = QTableWidgetItem(str(f))
            itf.setTextAlignment(Qt.AlignCenter)
            itf.setFlags(itf.flags() & ~Qt.ItemIsEditable)
            table.setItem(r, 0, itf)
            for c in range(len(self.behaviors)):
                val = 1 if self.frame_flags[c][f] else 0
                it = QTableWidgetItem("1" if val else "0")
                it.setTextAlignment(Qt.AlignCenter)
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                if val:
                    # 1이면 살짝 강조(가독성)
                    it.setBackground(QColor(255, 230, 160))  # 연한 주황빛
                table.setItem(r, 1+c, it)
        # 테이블은 가로/세로 모두 Expanding
        table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        table.setMinimumHeight(240)
        v.addWidget(table, 1)  # stretch 1 → 세로 여유를 전부 테이블이 가져감
        dlg.resize(1000, 700)
        dlg.exec_()

    def import_labels(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Labels", "", "CSV Files (*.csv)")
        if not path: return
        try:
            with open(path, 'r', encoding='utf-8') as fp:
                lines = [ln.strip() for ln in fp if ln.strip()]
        except Exception as e:
            QMessageBox.critical(self, "Import Failed", str(e)); return
        # simple CSV: header "Frame,<beh...>"
        header = None
        for ln in lines:
            if ln.lower().startswith("frame,"):
                header = [h.strip() for h in ln.split(',')]
                break
        if not header:
            QMessageBox.warning(self, "Invalid", "No header 'Frame,...' found.")
            return
        behs = header[1:]
        # define behaviors if different
        self.edit_behaviors.setText(", ".join(behs))
        self.define_behaviors()
        # zero flags
        for i in range(len(self.behaviors)):
            self.frame_flags[i] = [0]*self.total_frames
        # read rows
        start_idx = lines.index(",".join(header)) + 1
        for ln in lines[start_idx:]:
            parts = ln.split(',')
            try:
                f = int(parts[0])
            except:
                continue
            for i in range(len(self.behaviors)):
                if 1+i < len(parts):
                    self.frame_flags[i][f] = 1 if parts[1+i].strip() == '1' else 0
        self.data_modified = False

    def export_labels(self):
        if not self.behaviors or not self.frame_flags:
            QMessageBox.information(self, "Export", "No data to export.")
            return
        if self.current_video_path:
            stem = os.path.splitext(os.path.basename(self.current_video_path))[0]
            default_name = f"{stem}_labels.csv"
            folder = self.video_folder if self.video_folder else os.path.dirname(self.current_video_path)
            initial = os.path.join(folder, default_name)
        else:
            default_name = "labels.csv"
            folder = self.video_folder if self.video_folder else os.getcwd()
            initial = os.path.join(folder, default_name)
        path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", initial, "CSV Files (*.csv)"
        )
        if not path: return
        if os.path.exists(path):
            box = QMessageBox(self)
            box.setWindowTitle("Overwrite file?")
            box.setIcon(QMessageBox.Warning)
            box.setText(f"'{os.path.basename(path)}' already exists.\nDo you want to overwrite it?")
            btn_yes = box.addButton("Overwrite", QMessageBox.AcceptRole)
            btn_no  = box.addButton("Cancel", QMessageBox.RejectRole)
            box.exec_()
            if box.clickedButton() is btn_no:
                return
        try:
            with open(path, 'w', encoding='utf-8') as fp:
                video_name = self.list_videos.currentItem().text() if self.list_videos.currentItem() else "N/A"
                fp.write(f"Video name,{video_name}\n")
                fp.write(f"Video fps,{self.fps}\n")
                # 총계(초/프레임)
                frame_dur = (1.0 / self.fps) if self.fps else 0.0
                totals_frames = [sum(col) for col in self.frame_flags]
                totals_seconds = [round(cnt * frame_dur, 3) for cnt in totals_frames]
                fp.write("Total seconds," + ",".join(str(x) for x in totals_seconds) + "\n")
                fp.write("Total frames,"  + ",".join(str(x) for x in totals_frames)  + "\n")
                # 헤더 + 프레임별 표
                fp.write("Frame," + ",".join(self.behaviors) + "\n")
                for f in range(self.total_frames):
                    row = [str(f)] + [("1" if self.frame_flags[i][f] else "0") for i in range(len(self.behaviors))]
                    fp.write(",".join(row) + "\n")
            QMessageBox.information(self, "Export", "Exported.")
            self.data_modified = False
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", str(e))

    # ---------- key events ----------
    def keyPressEvent(self, event):
        k = event.key()
        # ---- Arrow keys: 1 frame step (allow auto-repeat) ----
        if k in (Qt.Key_Left, Qt.Key_Right):
            # 슬라이더가 비활성화면 방향키도 비활성
            if self.video_loaded and self.video_thread and self.slider.isEnabled():
                # 슬롯 키가 눌린 중엔(라벨링 충돌 방지) 스텝 금지
                if not any(sl['pressed'] for sl in self.slots):
                    delta = 1 if k == Qt.Key_Right else -1
                    new_frame = max(0, min(self.total_frames - 1, self.current_frame_idx + delta))
                    self.video_thread.seek(new_frame)
            return

        # ---- 기타 키는 자동반복 무시 ----
        if event.isAutoRepeat():
            return

        # 1) capture mode has priority
        if self.pending_key_capture is not None:
            self.check_record.setEnabled(False)
            idx = self.pending_key_capture
            # ESC로 캡처 취소
            if event.key() == Qt.Key_Escape:
                self.pending_key_capture = None
                self.slot_ui[idx]['keylab'].setText("-")
                self.releaseKeyboard()
                self.check_record.setEnabled(True)
                return
            qt_key, scan = event.key(), event.nativeScanCode()
            if qt_key in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Space):
                QMessageBox.warning(self, "Not allowed", "Left/Right arrows and Space is are reserved for frame control.")
                self.slot_ui[idx]['keylab'].setText("Press any key...")
                return
            key_id = (qt_key, scan)
            # 다른 슬롯과 중복 물리키 금지
            if any(sl['key'] == key_id for n, sl in enumerate(self.slots) if n != idx):
                QMessageBox.warning(self, "Invalid", "This physical key is already used by another slot.")
                # 캡처 유지: 안내 문구 갱신
                self.slot_ui[idx]['keylab'].setText("Press any key...")
                return
            # 저장 및 UI 갱신
            self.slots[idx]['key'] = key_id
            key_name = QKeySequence(qt_key).toString() or str(qt_key)
            self.slot_ui[idx]['keylab'].setText(f"{key_name}")
            # 종료 처리
            self.pending_key_capture = None
            self.releaseKeyboard()
            self._rebuild_key_index()
            self.check_record.setEnabled(True)
            return

        # 2) slot press handling (recording)
        slot_idx = self._key_to_slot(event)
        if slot_idx is not None and self.recording:
            sl = self.slots[slot_idx]
            bi = sl['behavior']
            if bi is not None and not sl['pressed']:
                sl['pressed'] = True
                sl['start_ms'] = self._ms_now()
                sl['start_frame'] = self.current_frame_idx
                # overlay on with behavior text
                if self.check_overlay.isChecked():
                    self._set_overlay_text(slot_idx, self.behaviors[bi])
                    self.overlay_labels[slot_idx].show()
            return

        # 3) globals
        if k == Qt.Key_Space:
            if not self.btn_play.isEnabled():
                return
            self.toggle_play_pause(); return

        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.isAutoRepeat(): return
        slot_idx = self._key_to_slot(event)
        if slot_idx is not None and self.recording:
            sl = self.slots[slot_idx]
            bi = sl['behavior']
            if bi is not None and sl['pressed']:
                sl['pressed'] = False
                end_ms = self._ms_now()
                dur = max(0, end_ms - sl['start_ms'])
                sl['ms'] += dur
                self.behavior_durations[bi] += dur
                s, e = sl['start_frame'], self.current_frame_idx
                if e < s: s, e = e, s
                for f in range(max(0, s), min(self.total_frames-1, e)+1):
                    self.frame_flags[bi][f] = 1
                if self.check_overlay.isChecked():
                    self.overlay_labels[slot_idx].hide()
                # update UI time
                self._update_slot_title(slot_idx)
                self.data_modified = True
            return
        super().keyReleaseEvent(event)

    # ---------- close ----------
    def closeEvent(self, e):
        if self.video_thread:
            self.video_thread.stop(); self.video_thread.wait()
        e.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    m = MainWindow()
    m.showMaximized()
    sys.exit(app.exec_())
