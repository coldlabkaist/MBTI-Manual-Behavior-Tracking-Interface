#-*- coding: utf-8 -*-

import os
import sys
import cv2  # type: ignore
import datetime

from PyQt5.QtWidgets import QFileDialog, QApplication, QDialog, QGraphicsScene, QGraphicsTextItem
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtCore import *
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QGraphicsVideoItem
from PyQt5 import uic

# connect mainGUI.ui file to UI.py

form_class = uic.loadUiType("mainGUI.ui")[0]
form_class_export = uic.loadUiType("exportGUI.ui")[0]

class MainWindowClass(QDialog, form_class):
    # create a signal to generate frame change detector
    frameChangedsig = pyqtSignal(int) # type: ignore 

    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.setWindowFlags(Qt.WindowCloseButtonHint | Qt.WindowMaximizeButtonHint | Qt.WindowMinimizeButtonHint) # type: ignore
        self.videoloaded = False

        # error control
        self.fps = 1
        self.totalframe = 100

        # set ui
        self.loadfolbt.clicked.connect(self.loadfolder)
        self.loadvidbt.clicked.connect(self.load_selected_video)
        self.playbt.clicked.connect(self.video_playorpause)
        self.importbt.clicked.connect(self.callexport)

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
        self.start_time = None
        self.end_time = None

        self.tar1key = [Qt.Key_Tab, Qt.Key_Tab, Qt.Key_F, Qt.Key_1] # type: ignore
        self.tar2key = [Qt.Key_Enter, Qt.Key_Return, Qt.Key_J, Qt.Key_2] # type: ignore
        self.cur1key = None
        self.cur2key = None
        self.isrecorded = False

        # only loader enabled
        self.videoslider.setDisabled(True)
        self.playbt.setDisabled(True)
        self.alertcheck.setDisabled(True)
        self.recordcheck.setDisabled(True)
        self.minspin.setDisabled(True)
        self.importbt.setDisabled(True)
        self.speedspin.setDisabled(True)

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
        self.file_sel = self.listvideo.currentText()
        if not self.file_sel.split('.')[-1] in ['mp4', 'avi']: # modify list
            #print(self.file_sel.split('.')[-1])
            print("incorrect video!")
            return
        file_path = self.videofolderdir+'/'+self.file_sel
        self.media_player.setMedia(QMediaContent(QUrl.fromLocalFile(file_path))) # type: ignore 
        self.media_player.setMuted(True)
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

        # set UI enabled
        self.videoslider.setEnabled(True)
        self.playbt.setEnabled(True)
        self.alertcheck.setEnabled(True)
        self.recordcheck.setEnabled(True)
        self.minspin.setEnabled(True)
        self.speedspin.setEnabled(True)

    # ------------------------------ videos ------------------------------

    def get_framecount(self, file_path):
        cap = cv2.VideoCapture(file_path)
        self.totalframe = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        self.fps = cap.get(cv2.CAP_PROP_FPS)

    def video_playorpause(self):
        if (self.media_player.mediaStatus()==1): # no video loaded
            return
        state = self.media_player.state()
        if(state == 0 or state == 2): # just loaded or paused
            self.media_player.play()
            self.is_video_played = True
        elif(state == 1): # playing
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
            self.totalnum.setText(f"{duration_min}:{duration_sec%60:02d}")
            # check target time
            if self.tar1_pressed:
                self.displaytartime(currentpos - self.tar1_starttime + self.tar1_time_sum, self.tar1num)
            if self.tar2_pressed:
                self.displaytartime(currentpos - self.tar2_starttime + self.tar2_time_sum, self.tar2num)

            if duration_ms >= self.minspin.value()*60000:
                self.media_player.pause()
                self.is_video_played = False
                self.escape_record()
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
        if self.record_mode:
            new_position = min(max(self.start_time, new_position), self.start_time+self.minspin.value()*60000)
        self.media_player.setPosition(new_position)

    # ------------------------------ video controller ------------------------------

    # videoslider
    def videoslider_setrange(self):
        self.videoslider.setRange(0, self.totalframe+1)
    def videoslider_pressed(self):
        if (not self.tar1_pressed) and (not self.tar2_pressed):
            self.media_player.pause()
    def videoslider_moved(self): #, frame
        if (not self.tar1_pressed) and (not self.tar2_pressed):
            frame = self.videoslider.value()
            position = (frame / self.fps) * 1000
            self.media_player.setPosition(position)
            self.videolabel_set()
    def videoslider_released(self):
        if (not self.tar1_pressed) and (not self.tar2_pressed):
            if(self.is_video_played):
                self.media_player.play()
    def videoslider_reset(self):
        self.videoslider.setValue(0)

    def videolabel_set(self):
        currentpos = self.media_player.position()
        currentfr = int((currentpos / 1000) * self.fps)
        self.videoframelabel.setText(f"Frame: {currentfr:04d} / {int(self.totalframe):04d}")
        
        currentsec = int(currentfr/self.fps)
        currentmin = int(currentsec/60)
        totalsec = int(self.totalframe/self.fps)
        totalmin = int(totalsec/60)
        self.videotimelabel.setText(f"Time: {currentmin:02d}:{currentsec%60:02d} / {totalmin:02d}:{totalsec%60:02d}")

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
        self.end_time = None
        self.record_mode = True
        self.tar1_time_sum = 0
        self.tar2_time_sum = 0
        self.tar1_time_list = []
        self.tar2_time_list = []
        self.tar1num.setText("0:00:00")
        self.tar2num.setText("0:00:00")

        if self.tar1_pressed:
            self.tar1_starttime = self.media_player.position()
            self.tar1_time_list.append([self.tar1_starttime, None])
        if self.tar2_pressed:
            self.tar2_starttime = self.media_player.position()
            self.tar2_time_list.append([self.tar2_starttime, None])

        # set some buttons disabled
        self.minspin.setDisabled(True)
        self.videoslider.setDisabled(True)
        self.importbt.setDisabled(True)
        self.listvideo.setDisabled(True)
        self.loadvidbt.setDisabled(True)
        self.loadfolbt.setDisabled(True)

    def escape_record(self):
        self.end_time = self.media_player.position()
        if len(self.tar1_time_list) != 0 and self.tar1_time_list[-1][1] == None:
            self.tar1_time_list[-1][1] = self.end_time
            self.tar1_time_sum += self.end_time - self.tar1_starttime
            self.tar1_time_list[-1][2] = self.tar1_time_sum

        if len(self.tar2_time_list) != 0 and self.tar2_time_list[-1][1] == None:
            self.tar2_time_list[-1][1] = self.end_time
            self.tar2_time_sum += self.end_time - self.tar2_starttime
            self.tar2_time_list[-1][2] = self.tar2_time_sum

        self.displaytartime(self.tar1_time_sum, self.tar1num)
        self.displaytartime(self.tar2_time_sum, self.tar2num)

        # display result for test
        #print(self.start_time, self.end_time)
        #print("tar1: ", self.tar1_time_sum, ": ", self.tar1_time_list)
        #print("tar2: ", self.tar2_time_sum, ": ", self.tar2_time_list)

        if self.start_time != self.end_time:
            self.isrecorded = True
        self.record_mode = False

        if self.recordcheck.isChecked():
            self.recordcheck.toggle()

        # set some buttons enabled
        self.minspin.setEnabled(True)
        self.videoslider.setEnabled(True)
        self.importbt.setEnabled(True)
        self.listvideo.setEnabled(True)
        self.loadvidbt.setEnabled(True)
        self.loadfolbt.setEnabled(True)

    def displaytartime(self, time_sum, displayer):
        duration_ms = time_sum
        duration_sec = duration_ms//1000
        duration_min = duration_sec//60
        displayer.setText(f"{duration_min}:{duration_sec%60:02d}:{duration_ms%1000//10:02d}")

    def recordstarttime(self, time_list, starttime):
        if len(time_list) == 0:
            time_list.append([starttime, None, None])
            return (0, starttime)
        
        while len(time_list)>0:
            if time_list[-1][1] == None:
                return (0, time_list[-1][0])
            elif starttime < time_list[-1][1]: 
                if starttime > time_list[-1][0]: # ori_starttimei < new_starttime < ori_endtimei
                    # should remove ori_endtimei
                    time_list[-1][1] = None
                    # recalculate totaltime, new starttime
                    return (time_list[-2][2], time_list[-1][0])
                else:
                    time_list.pop()
                    continue
            else: # ori_endtimei < ori_starttime < new_starttimei+1
                # should remove time i+1
                time_list.append([starttime, None, None])
                # recalculate totaltime, new starttime
                return (time_list[-2][2], starttime)
        
        time_list.append([starttime, None, None])
        return (0, starttime)

    def alertcheck_changed(self):
        # key pressed 상태에서 check가 True가 된 경우는 고려하지 않음
        if not self.alertcheck.isChecked():
            self.a1time.setDefaultTextColor(QColor(0, 0, 0, 0))
            self.a2time.setDefaultTextColor(QColor(0, 0, 0, 0))

    def keyPressEvent(self, e):
        if not self.videoloaded:
            return
        if e.key() == Qt.Key_Space: # type: ignore # Space key play/pause video 
            self.video_playorpause()
        elif e.key() == Qt.Key_Escape: # type: ignore # ESC key quits
            self.close()
        if (not self.tar1_pressed) and (not self.tar2_pressed):
            if e.key() == Qt.Key_Comma: # type: ignore
                self.move_frame("backward", self.fps)
            elif e.key() == Qt.Key_A: # type: ignore
                self.move_frame("backward", self.fps*10)
        if not self.record_mode:
            if e.key() == Qt.Key_Period: # type: ignore
                self.move_frame("forward", self.fps)
            elif e.key() == Qt.Key_D: # type: ignore
                self.move_frame("forward", self.fps*10)

        if not e.isAutoRepeat(): 
            # check input 1
            if self.cur1key == None:
                bool1 = e.key() in self.tar1key
            else:
                bool1 = e.key() == self.tar1key[self.cur1key]
            if bool1: 
                self.cur1key = self.tar1key.index(e.key())
                self.tar1_pressed = True
                if self.record_mode:
                    if self.alertcheck.isChecked():
                        self.a1time.setDefaultTextColor(QColor(225, 0, 0, 100))
                    self.tar1_starttime = self.media_player.position() # in ms
                    # Check for duplication of time history and append
                    self.tar1_time_sum, self.tar1_starttime = self.recordstarttime(self.tar1_time_list, self.tar1_starttime)
                    
            # check input 2
            if self.cur2key == None:
                bool2 = e.key() in self.tar2key
            else:
                bool2 = e.key() == self.tar2key[self.cur2key]
            if bool2: 
                self.cur2key = self.tar2key.index(e.key())
                self.tar2_pressed = True
                if self.record_mode:
                    if self.alertcheck.isChecked():
                        self.a2time.setDefaultTextColor(QColor(0, 0, 225, 100))
                    self.tar2_starttime = self.media_player.position() # in ms
                    self.tar2_time_sum, self.tar2_starttime = self.recordstarttime(self.tar2_time_list, self.tar2_starttime)
            
    def keyReleaseEvent(self, e):
        if not e.isAutoRepeat(): 
            endtime = self.media_player.position()
            if self.cur1key != None and e.key() == self.tar1key[self.cur1key]: # type: ignore
                self.cur1key = None
                self.tar1_pressed = False
                if self.record_mode:
                    self.a1time.setDefaultTextColor(QColor(0, 0, 0, 0))
                    self.tar1_time_sum += endtime - self.tar1_starttime
                    self.tar1_time_list[-1][2] = self.tar1_time_sum
                    if self.tar1_time_list[-1][0] == endtime:
                        self.tar1_time_list.pop()
                    else:
                        self.tar1_time_list[-1][1] = endtime
                    self.displaytartime(self.tar1_time_sum, self.tar1num)
                #print(self.tar1_time_list)

            if self.cur2key != None and e.key() == self.tar2key[self.cur2key]: # type: ignore 
                self.cur2key = None
                self.tar2_pressed = False
                if self.record_mode:
                    self.a2time.setDefaultTextColor(QColor(0, 0, 0, 0))
                    self.tar2_time_sum += endtime - self.tar2_starttime
                    self.tar2_time_list[-1][2] = self.tar2_time_sum
                    if self.tar2_time_list[-1][0] == endtime:
                        self.tar2_time_list.pop()
                    else:
                        self.tar2_time_list[-1][1] = endtime
                    self.displaytartime(self.tar2_time_sum, self.tar2num)
                #print(self.tar2_time_list)
            
    def resizeEvent(self, e):
        if self.videoloaded:
            self.update_scene_size()

    def wheelEvent(self, e):
        if self.videoloaded and self.media_player.state() != 1:
            if not self.record_mode: # at record mode, prohibit scroll
                # scroll controll
                if self.media_player.state() == 1:
                    self.media_player.pause()
                frame = self.videoslider.value() - e.angleDelta().y()
                position = (frame / self.fps) * 1000
                self.videoslider.setValue(frame)
                self.media_player.setPosition(position)
                self.videolabel_set()
                if self.is_video_played:
                    self.media_player.pause()
                    self.media_player.play()
                else:
                    # to remove lagging
                    self.media_player.play()
                    self.media_player.pause()       

    # ------------------------------ csv export ------------------------------
    def callexport(self):
        if not self.isrecorded:
            print("nothing recorded!")
            return          

        #Creating an Instance of WindowClass
        exWindow = ExportWindowClass((self.videofolderdir, self.file_sel), (self.start_time, self.end_time), (self.tar1_time_sum, self.tar2_time_sum), (self.tar1_time_list, self.tar2_time_list))

        #show GUI
        exWindow.show()

        #Enter the program into the event loop (operate the program)
        exWindow.exec_()

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

class ExportWindowClass(QDialog, form_class_export):
    def __init__(self, proinfo, totaltime, sumtime, listtime):
        super().__init__()
        self.setupUi(self)
        self.setWindowFlags(Qt.WindowCloseButtonHint | Qt.WindowMinimizeButtonHint) # type: ignore
        
        # export gui has its own information
        self.folder = proinfo[0] # (dir, videoname)
        self.video = proinfo[1]

        self.totaltime = totaltime # (start, end)
        self.sumtime = sumtime # (tar1, tar2)
        self.listtime = listtime # (tar1, tar2)

        self.exstart.setText(self.ms2minsec(self.totaltime[0]))
        self.exend.setText(self.ms2minsec(self.totaltime[1]))
        self.extotal.setText(self.ms2minsec(self.totaltime[1]-self.totaltime[0]))
        self.extar1.setText(self.ms2minsec(self.sumtime[0]))
        self.extar2.setText(self.ms2minsec(self.sumtime[1]))

        self.pushButton.clicked.connect(self.export2csv)

    def ms2minsec(self, ms):
        sec, ms = ms//1000, ms%1000
        minu, sec = sec//60, sec%60
        return f"{minu}:{sec:02d}:{ms:03d}"

    # ------------------------------ csv export ------------------------------
    def export2csv(self):
        projectname = self.linepro.text()
        tar1name = self.linetar1.text()
        tar2name = self.linetar2.text()
        if projectname.isspace():
            self.exresult.setText("set project name!")
            return
        
        if tar1name.isspace() or tar2name.isspace():
            self.exresult.setText("set target behavior name!")
            return
        
        if tar1name == tar2name:
            self.exresult.setText("set two names differently :(")
            return

        # create csv line - first line
        texts = []
        listdir = os.listdir(self.folder)
        if not f"{projectname}.csv" in listdir:
            texts.append("export time,video name,behavior,type,record duration(ms),total record time(ms),behavior duration(ms),recorded behavior time(ms)")
        
        # create csv line
        now = datetime.datetime.now()
        time = now.strftime('%Y-%m-%d %H:%M')
        
        # create csv line - tar1 start/end
        type = ["start","end"]
        tarname = [tar1name, tar2name]
        for i in range(2): # behavior
            total_duration = [str(self.totaltime[1]-self.totaltime[0]), ""]
            behavior_duration = [str(self.sumtime[i]), ""]
            for j in range(2): # type
                # text = time, video, start/end/duration, totaltime, behavior
                text = [time, self.video, tarname[i], type[j], total_duration[j], str(self.totaltime[j]), behavior_duration[j]]
                for k in range(len(self.listtime[i])):
                    #print(self.listtime[i][k][j])
                    text.append(str(self.listtime[i][k][j]))
                text = ','.join(text)
                texts.append(text)

        try:
            with open(f"{self.folder}/{projectname}.csv", "a") as f:
                for text in texts:
                    f.write(text)
                    f.write('\n')
                self.close()
        except (OSError, IOError) as e:
            self.exresult.setText("csv file is already opened from other process. Can't overwrite it :(")

    def test(self):
        print(self.totaltime, self.sumtime, self.listtime)

def main():
    # call GUI
    print("Starting MBTI 1.1.1...")

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
