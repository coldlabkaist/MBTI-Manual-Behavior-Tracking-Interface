#-*- coding: utf-8 -*-

import os
import sys
import cv2  # type: ignore

import matplotlib.pyplot as plt

from PyQt5.QtWidgets import QFileDialog, QApplication, QDialog, QGraphicsScene, QMainWindow, QGraphicsEllipseItem, QGraphicsTextItem
from PyQt5.QtGui import QBrush, QPen, QColor, QFont
from PyQt5.QtCore import *
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QGraphicsVideoItem
from PyQt5 import uic

# connect mainGUI.ui file to UI.py

form_class = uic.loadUiType("mainGUI.ui")[0]

class MainWindowClass(QDialog, form_class):
    # create a signal to generate frame change detector
    frameChangedsig = pyqtSignal(int) # type: ignore 

    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.setWindowFlags(Qt.WindowCloseButtonHint | Qt.WindowMaximizeButtonHint | Qt.WindowMinimizeButtonHint)
        self.videoloaded = False

        # set ui
        self.loadfolbt.clicked.connect(self.loadfolder)
        self.loadvidbt.clicked.connect(self.load_selected_video)
        self.playbt.clicked.connect(self.video_playorpause)

        self.videoslider.sliderPressed.connect(self.videoslider_pressed)
        self.videoslider.sliderReleased.connect(self.videoslider_released)
        self.videoslider.sliderMoved.connect(self.videoslider_moved)

        self.alertcheck.stateChanged.connect(self.alertcheck_changed)
        self.recordcheck.stateChanged.connect(self.recordcheck_changed)

        self.speedspin.valueChanged.connect(self.speedspin_changed)

        # Create a QGraphicsScene
        self.scene = QGraphicsScene()
        # Set the scene to the QGraphicsView
        self.qgraphicsvideo.setScene(self.scene)

        # Create a QGraphicsVideoItem
        self.video_item = QGraphicsVideoItem()
        self.scene.addItem(self.video_item)

        # Set up the QMediaPlayer
        self.media_player = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.media_player.setVideoOutput(self.video_item)

        # Connect error signals to handle potential issues
        self.media_player.error.connect(self.handle_error)
        self.media_player.mediaStatusChanged.connect(self.handle_media_status)
        self.media_player.stateChanged.connect(self.handle_state_changed)
        self.is_video_played = False

        # load text item
        self.a1time = QGraphicsTextItem("Key Pressed 1")
        self.a2time = QGraphicsTextItem("Key Pressed 2")
        self.a1time.setFont(QFont("Arial", 24))
        self.a2time.setFont(QFont("Arial", 24))
        self.a1time.setDefaultTextColor(QColor(0, 0, 0, 0))
        self.a2time.setDefaultTextColor(QColor(0, 0, 0, 0))
        self.a1time.setPos(100, 100)
        self.a2time.setPos(500, 100)
        self.scene.addItem(self.a1time)
        self.scene.addItem(self.a2time)

        self.record_mode = False

        self.tar1key = [Qt.Key_Tab, Qt.Key_Tab, Qt.Key_F, Qt.Key_1] # type: ignore
        self.tar2key = [Qt.Key_Enter, Qt.Key_Return, Qt.Key_J, Qt.Key_2] # type: ignore

    # ------------------------------ load ------------------------------

    def loadfolder(self):
        dir=QFileDialog.getExistingDirectory(self)
        if dir == '':
            print("directory not selected")
            return
        # to implement: check those files are video
        self.listvideo.clear()
        self.videofolderdir = dir
        self.videofiledir = os.listdir(self.videofolderdir)
        self.listvideo.addItems(self.videofiledir)

    def load_selected_video(self):
        file_sel = self.listvideo.currentText()
        file_path = self.videofolderdir+'/'+file_sel
        self.media_player.setMedia(QMediaContent(QUrl.fromLocalFile(file_path))) # type: ignore 
        self.media_player.play()
        self.media_player.pause()
        self.get_framecount(file_path)
        self.current_frame = 0
        self.videolabel_set()
        self.videoslider_reset()
        self.videoslider_setrange()
        self.videoloaded = True

        # Read fps and size of video
        cv2_vid = cv2.VideoCapture(file_path)
        self.fps = cv2_vid.get(cv2.CAP_PROP_FPS)
        _, frame = cv2_vid.read()
        self.vid_h, self.vid_w, _ = frame.shape
        self.current_frame = 0
        # Define resolution or margin of video (to display without distortion)
        # refer update_scene_size()
        self.vid_h_adjust, self.vid_w_adjust = self.vid_h, self.vid_w
        self.vid_resol_const = 1
        self.vid_resol_var = 100 # in %
        self.vid_bias_x = 0.0
        self.vid_bias_y = 0.0

        self.update_scene_size()

        # timer
        self.frame_check_timer = QTimer(self) # type: ignore 
        self.frame_check_timer.timeout.connect(self.check_frame_change)
        self.frame_check_timer.start(1000 // 10)  # Check every frame # default is 10
        self.frameChangedsig.connect(self.framechanged)

        self.start_time = None
        self.record_mode = False
        self.tar1_time_sum = 0
        self.tar2_time_sum = 0
        self.tar1_time_list = []
        self.tar2_time_list = []
        self.tar1_pressed = False
        self.tar2_pressed = False

    # ------------------------------ videos ------------------------------

    def get_framecount(self, file_path):
        cap = cv2.VideoCapture(file_path)
        self.totalframe = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        self.fps = cap.get(cv2.CAP_PROP_FPS)
        #print(self.totalframe, self.fps)

    def video_playorpause(self):
        #print(self.media_player.mediaStatus(), self.media_player.state())
        if (self.media_player.mediaStatus()==1): # no video loaded
            return
        state = self.media_player.state()
        if(state == 0 or state == 2): # just loaded or paused
            #print('Playing video...')
            self.media_player.play()
            self.is_video_played = True
        elif(state == 1): # playing
            #print('video Paused')
            self.media_player.pause()
            self.is_video_played = False

    def check_frame_change(self):
        position = self.media_player.position()
        new_frame = int((position / 1000) * self.fps)
        if new_frame != self.current_frame:
            self.current_frame = new_frame
            self.frameChangedsig.emit(self.current_frame)

    def framechanged(self):
        currentpos = self.media_player.position()
        currentfr = int((currentpos / 1000) * self.fps)
        #self.videoframelabel.setText(f"Frame: {currentfr}/{int(self.totalframe)}")
        self.videoslider.setValue(currentfr)
        self.videolabel_set()

        # check record related info
        if self.record_mode:
            # check total time
            duration_ms = currentpos - self.start_time
            duration_sec = duration_ms//1000
            duration_min = duration_sec//60
            self.totalnum.setText(f"{duration_min}:{duration_sec%60}")            
            # check target time
            if self.tar1_pressed:
                duration_tar1_ms = currentpos - self.tar1_starttime + self.tar1_time_sum
                duration_tar1_sec = duration_tar1_ms//1000
                duration_tar1_min = duration_tar1_sec//60
                self.tar1num.setText(f"{duration_tar1_min}:{duration_tar1_sec%60}:{duration_tar1_ms%1000//10}")
            if self.tar2_pressed:
                duration_tar2_ms = currentpos - self.tar2_starttime + self.tar2_time_sum
                duration_tar2_sec = duration_tar2_ms//1000
                duration_tar2_min = duration_tar2_sec//60
                self.tar2num.setText(f"{duration_tar2_min}:{duration_tar2_sec%60}:{duration_tar2_ms%1000//10}")

            if duration_ms >= self.minspin.value()*60000:
                self.media_player.pause()
                self.is_video_played = False
                self.recordcheck.toggle()
                print("recording end")

    def update_scene_size(self):
        # get size information of qgraphicsvideo
        screen_rect = self.qgraphicsvideo.rect()
        screen_w = screen_rect.width()
        screen_h = screen_rect.height()
        #screen_x = screen_rect.x()
        #screen_y = screen_rect.y()
        
        # compare the size ratio of screen and video
        # if screen_w/video_w > screen_h/video_h, then height of video is longer
        if (screen_w*self.vid_h > screen_h*self.vid_w):
            # video height is longer, adjust width based on height
            self.resol_const = screen_h/self.vid_h
            self.vid_w_adjust = self.vid_w*self.resol_const
            self.vid_h_adjust = screen_h
            self.bias_x = (screen_w-self.vid_w_adjust)/2
            self.bias_y = 0
        elif (screen_w*self.vid_h <= screen_h*self.vid_w):
            # video width is longer, adjust height based on width
            self.resol_const = screen_w/self.vid_w
            self.vid_w_adjust = screen_w
            self.vid_h_adjust = self.vid_h*self.resol_const
            self.bias_x = 0
            self.bias_y = (screen_h-self.vid_h_adjust)/2

        self.video_item.setSize(QSizeF(self.vid_w_adjust, self.vid_h_adjust)) # type: ignore 
        self.scene.setSceneRect(QRectF(0,0, self.vid_w_adjust, self.vid_h_adjust)) # type: ignore 

    def move_frame(self, direction, Nframe):
        if(direction == "forward"):
            sgn = +1
        elif(direction == "backward"):
            sgn = -1
        else:
            print("error: wrong direction on move_frame")
            return
        
        current_position = self.media_player.position()
        frame_step = (Nframe / self.fps) * 1000
        new_position = current_position + sgn*frame_step
        self.media_player.setPosition(new_position)

    # ------------------------------ video controller ------------------------------

    # videoslider
    def videoslider_setrange(self):
        self.videoslider.setRange(0, self.totalframe+1)
    def videoslider_pressed(self):
        self.media_player.pause()
    def videoslider_moved(self): #, frame
        frame = self.videoslider.value()
        position = (frame / self.fps) * 1000
        self.media_player.setPosition(position)
        self.videolabel_set()
    def videoslider_released(self):
        if(self.is_video_played):
            self.media_player.play()
    def videoslider_reset(self):
        self.videoslider.setValue(0)

    def videolabel_set(self):
        currentpos = self.media_player.position()
        currentfr = int((currentpos / 1000) * self.fps)
        self.videoframelabel.setText(f"Frame: {currentfr} / {int(self.totalframe)}")
        
        currentsec = int(currentfr/self.fps)
        currentmin = int(currentsec/60)
        totalsec = int(self.totalframe/self.fps)
        totalmin = int(totalsec/60)
        self.videotimelabel.setText(f"Time: {currentmin}:{currentsec%60} / {totalmin}:{totalsec%60}")

    def speedspin_changed(self):
        speed = self.speedspin.value()
        self.media_player.setPlaybackRate(speed)

    # ------------------------------ key/bt control ------------------------------

    def recordcheck_changed(self):
        # key pressed 상태에서 check가 True가 된 경우는 고려하지 않음
        if self.recordcheck.isChecked():
            self.start_record()
        else:
            self.escape_record()

    def start_record(self):
        self.start_time = self.media_player.position() # in ms
        self.record_mode = True
        self.tar1_time_sum = 0
        self.tar2_time_sum = 0
        self.tar1_time_list = []
        self.tar2_time_list = []
        self.tar1num.setText("0:0:00")
        self.tar2num.setText("0:0:00")

        if self.tar1_pressed:
            self.tar1_starttime = self.media_player.position()
        if self.tar2_pressed:
            self.tar2_starttime = self.media_player.position()

    def escape_record(self):
        self.start_time = None
        self.record_mode = False

    def alertcheck_changed(self):
        # key pressed 상태에서 check가 True가 된 경우는 고려하지 않음
        if not self.alertcheck.isChecked():
            self.a1time.setDefaultTextColor(QColor(0, 0, 0, 0))
            self.a2time.setDefaultTextColor(QColor(0, 0, 0, 0))

    def keyPressEvent(self, e):
        if not e.isAutoRepeat(): 
            if e.key() == Qt.Key_Space: # type: ignore # Space key play/pause video 
                self.video_playorpause()
            elif e.key() == Qt.Key_Escape: # type: ignore # ESC key quits
                self.close()
            elif e.key() == Qt.Key_Comma: # type: ignore
                self.move_frame("backward", self.fps)
            elif e.key() == Qt.Key_Period: # type: ignore
                self.move_frame("forward", self.fps)
            elif e.key() == Qt.Key_A: # type: ignore
                self.move_frame("backward", self.fps*10)
            elif e.key() == Qt.Key_D: # type: ignore
                self.move_frame("forward", self.fps*10)
            
            if self.record_mode:
                if e.key() in self.tar1key: 
                    if self.alertcheck.isChecked():
                        self.a1time.setDefaultTextColor(QColor(225, 0, 0, 100))
                    self.tar1_starttime = self.media_player.position() # in ms
                    self.tar1_pressed = True
                elif e.key() in self.tar2key: 
                    if self.alertcheck.isChecked():
                        self.a2time.setDefaultTextColor(QColor(0, 0, 225, 100))
                    self.tar2_starttime = self.media_player.position() # in ms
                    self.tar2_pressed = True

    def keyReleaseEvent(self, e):
        if not e.isAutoRepeat(): 
            if e.key() in self.tar1key: # type: ignore
                self.tar1_pressed = False
                if self.record_mode:
                    self.a1time.setDefaultTextColor(QColor(0, 0, 0, 0))
                    self.tar1_time_sum += self.media_player.position() - self.tar1_starttime
            elif e.key() in self.tar2key: # type: ignore 
                self.tar2_pressed = False
                if self.record_mode:
                    self.a2time.setDefaultTextColor(QColor(0, 0, 0, 0))
                    self.tar2_time_sum += self.media_player.position() - self.tar2_starttime
            
    def resizeEvent(self, e):
        if self.videoloaded:
            self.update_scene_size()

    # ------------------------------ error handling ------------------------------
    def handle_error(self, error):
        pass
        #print("Error occurred: ", error, self.media_player.errorString())

    def handle_media_status(self, status):
        pass
        # print("Media status changed: ", status)

    def handle_state_changed(self, state):
        pass
        # print("State changed: ", state)

def main():
    # call GUI
    print("Starting MBTI 1.0.0...")

    #QApplication : a class that runs a program
    app = QApplication(sys.argv)  # type: ignore

    #Creating an Instance of WindowClass
    myWindow = MainWindowClass() 

    #show GUI
    myWindow.showMaximized()

    #Enter the program into the event loop (operate the program)
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
