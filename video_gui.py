import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                           QHBoxLayout, QPushButton, QLabel, QSpinBox, 
                           QDoubleSpinBox, QFileDialog, QCheckBox, QLineEdit,
                           QGroupBox, QMessageBox, QProgressBar, QTextEdit,
                           QSplitter)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
import video_checker
import io
import sys

class OutputRedirector(io.StringIO):
    def __init__(self, signal):
        super().__init__()
        self.signal = signal

    def write(self, text):
        self.signal.emit(text)
        
    def flush(self):
        pass

class VideoProcessThread(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)
    debug_output = pyqtSignal(str)

    def __init__(self, params):
        super().__init__()
        self.params = params

    def run(self):
        try:
            # 如果启用了调试模式，重定向标准输出
            if self.params['debug']:
                old_stdout = sys.stdout
                redirector = OutputRedirector(self.debug_output)
                sys.stdout = redirector

            # 将参数转换为命令行参数格式
            args = type('Args', (), {
                'folder': self.params['folder'],
                'threshold': self.params['threshold'],
                'ratio_threshold': self.params['ratio_threshold'],
                'time_box': self.params['time_box'],
                'no_concat': self.params['no_concat'],
                'output': self.params['output'],
                'debug': self.params['debug']
            })()

            # 调用原有的处理函数
            video_checker.process_video_folder(
                args.folder, 
                args.threshold,
                not args.no_concat,
                args.time_box,
                args.ratio_threshold
            )

            # 恢复标准输出
            if self.params['debug']:
                sys.stdout = old_stdout

            self.finished.emit(True, "处理完成！")
        except Exception as e:
            if self.params['debug']:
                sys.stdout = sys.__stdout__
            self.finished.emit(False, f"处理出错: {str(e)}")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("视频运动检测工具")
        self.setMinimumWidth(800)
        self.setMinimumHeight(600)
        
        # 创建主分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(splitter)

        # 左侧控制面板
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # 文件选择区域
        file_group = QGroupBox("文件设置")
        file_layout = QVBoxLayout()
        
        folder_layout = QHBoxLayout()
        self.folder_edit = QLineEdit()
        folder_button = QPushButton("选择文件夹")
        folder_button.clicked.connect(self.select_folder)
        folder_layout.addWidget(QLabel("视频文件夹:"))
        folder_layout.addWidget(self.folder_edit)
        folder_layout.addWidget(folder_button)
        file_layout.addLayout(folder_layout)

        output_layout = QHBoxLayout()
        self.output_edit = QLineEdit("concatenated_output.mp4")
        output_layout.addWidget(QLabel("输出文件名:"))
        output_layout.addWidget(self.output_edit)
        file_layout.addLayout(output_layout)

        file_group.setLayout(file_layout)
        left_layout.addWidget(file_group)

        # 检测参数区域
        param_group = QGroupBox("检测参数")
        param_layout = QVBoxLayout()

        # 阈值设置
        threshold_layout = QHBoxLayout()
        self.threshold_spin = QSpinBox()
        self.threshold_spin.setRange(0, 10000)
        self.threshold_spin.setValue(1000)
        threshold_layout.addWidget(QLabel("像素差异阈值:"))
        threshold_layout.addWidget(self.threshold_spin)
        param_layout.addLayout(threshold_layout)

        # 比例阈值设置
        ratio_layout = QHBoxLayout()
        self.ratio_spin = QDoubleSpinBox()
        self.ratio_spin.setRange(0.0, 100.0)
        self.ratio_spin.setValue(0.5)
        self.ratio_spin.setSingleStep(0.1)
        ratio_layout.addWidget(QLabel("变化比例阈值(%):"))
        ratio_layout.addWidget(self.ratio_spin)
        param_layout.addLayout(ratio_layout)

        # 时间戳区域设置
        time_box_layout = QHBoxLayout()
        self.time_box_spins = []
        labels = ["X:", "Y:", "宽:", "高:"]
        default_values = [0, 0, 200, 50]
        for label, value in zip(labels, default_values):
            spin = QSpinBox()
            spin.setRange(0, 2000)
            spin.setValue(value)
            time_box_layout.addWidget(QLabel(label))
            time_box_layout.addWidget(spin)
            self.time_box_spins.append(spin)
        param_layout.addWidget(QLabel("时间戳区域:"))
        param_layout.addLayout(time_box_layout)

        param_group.setLayout(param_layout)
        left_layout.addWidget(param_group)

        # 选项区域
        option_group = QGroupBox("其他选项")
        option_layout = QVBoxLayout()
        
        self.concat_check = QCheckBox("合并视频")
        self.concat_check.setChecked(True)
        option_layout.addWidget(self.concat_check)

        self.debug_check = QCheckBox("调试模式")
        self.debug_check.setChecked(False)
        self.debug_check.stateChanged.connect(self.toggle_debug_view)
        option_layout.addWidget(self.debug_check)

        option_group.setLayout(option_layout)
        left_layout.addWidget(option_group)

        # 进度显示
        self.progress_label = QLabel("")
        left_layout.addWidget(self.progress_label)

        # 处理按钮
        self.process_button = QPushButton("开始处理")
        self.process_button.clicked.connect(self.start_processing)
        left_layout.addWidget(self.process_button)

        # 添加弹簧
        left_layout.addStretch()

        # 右侧调试输出区域
        self.debug_widget = QWidget()
        debug_layout = QVBoxLayout(self.debug_widget)
        
        # 调试输出文本框
        self.debug_text = QTextEdit()
        self.debug_text.setReadOnly(True)
        debug_layout.addWidget(QLabel("调试输出:"))
        debug_layout.addWidget(self.debug_text)
        
        # 清除按钮
        clear_button = QPushButton("清除输出")
        clear_button.clicked.connect(self.clear_debug_output)
        debug_layout.addWidget(clear_button)
        
        # 初始时隐藏调试区域
        self.debug_widget.hide()

        # 添加到分割器
        splitter.addWidget(left_widget)
        splitter.addWidget(self.debug_widget)
        
        # 设置分割器的初始大小
        splitter.setSizes([400, 400])

    def toggle_debug_view(self, state):
        self.debug_widget.setVisible(state == Qt.CheckState.Checked.value)
        if state == Qt.CheckState.Checked.value:
            self.setMinimumWidth(1000)
        else:
            self.setMinimumWidth(600)

    def clear_debug_output(self):
        self.debug_text.clear()

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择视频文件夹")
        if folder:
            self.folder_edit.setText(folder)

    def start_processing(self):
        folder = self.folder_edit.text()
        if not folder or not os.path.isdir(folder):
            QMessageBox.warning(self, "错误", "请选择有效的视频文件夹！")
            return

        # 收集所有参数
        params = {
            'folder': folder,
            'threshold': self.threshold_spin.value(),
            'ratio_threshold': self.ratio_spin.value() / 100,  # 转换为小数
            'time_box': [spin.value() for spin in self.time_box_spins],
            'no_concat': not self.concat_check.isChecked(),
            'output': self.output_edit.text(),
            'debug': self.debug_check.isChecked()
        }

        # 如果是调试模式，清除之前的输出
        if params['debug']:
            self.debug_text.clear()

        # 禁用处理按钮
        self.process_button.setEnabled(False)
        self.progress_label.setText("处理中...")

        # 创建并启动处理线程
        self.thread = VideoProcessThread(params)
        self.thread.finished.connect(self.on_process_finished)
        self.thread.debug_output.connect(self.update_debug_output)
        self.thread.start()

    def update_debug_output(self, text):
        self.debug_text.append(text)
        # 滚动到底部
        self.debug_text.verticalScrollBar().setValue(
            self.debug_text.verticalScrollBar().maximum()
        )

    def on_process_finished(self, success, message):
        self.process_button.setEnabled(True)
        self.progress_label.setText(message)
        if success:
            QMessageBox.information(self, "完成", message)
        else:
            QMessageBox.warning(self, "错误", message)

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
