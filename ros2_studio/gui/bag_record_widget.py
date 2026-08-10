"""Widget for ROS2 bag recording with topic selection."""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget,
    QPushButton, QLabel, QFileDialog, QLineEdit,
    QGroupBox, QTextEdit, QAbstractItemView, QComboBox, QSpinBox
)
from PyQt5.QtCore import QTimer
from ros2_studio.core.bag_recorder import BagRecorder
import os
import time


class BagRecordWidget(QWidget):
    """Widget for recording ROS2 bags."""
    
    def __init__(self, record_config=None, record_config_path=None):
        """Initialize bag record widget.

        Args:
            record_config: Optional flat dict of default bag record options
                (option_name -> value), pre-populating `bag_recorder.options`
            record_config_path: Path the config was loaded from, shown in a
                startup notice when record_config is set
        """
        super().__init__()
        self.bag_recorder = BagRecorder(initial_options=record_config)
        self.recording_start_time = None
        self.recording_duration = 0
        self.setup_ui()
        self._apply_options_to_widgets()
        if record_config:
            self.status_label.setText('Status: Ready (config loaded)')
            self.info_text.append(
                f'\nℹ Defaults loaded from: {record_config_path}\n'
                '  Some configuration entries are not shown in the GUI but will '
                'still be applied when recording starts.'
            )

        # Timer for updating recording duration
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_recording_info)

    def _apply_options_to_widgets(self):
        """Reflect `bag_recorder.options`' current values in the GUI-editable widgets.

        Called once at startup (after any record config has pre-populated
        `options`) so the widgets shown to the user match what would
        actually be recorded if "Start Recording" were pressed right away.
        """
        options = self.bag_recorder.options

        if options.get('output_dir'):
            self.location_input.setText(options['output_dir'])

        index = self.storage_format_combo.findData(options.get('storage'))
        if index >= 0:
            self.storage_format_combo.setCurrentIndex(index)

        self.split_duration_spinbox.setValue(int(options.get('max_bag_duration', 0)))

        for i in range(self.topic_list.count()):
            item = self.topic_list.item(i)
            if item.text() in options.get('topics', []):
                item.setSelected(True)
    
    def setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Topic selection group
        topic_group = QGroupBox("Select Topics to Record")
        topic_layout = QVBoxLayout()
        
        # Topic list
        topic_header = QHBoxLayout()
        topic_label = QLabel('Available Topics:')
        topic_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        
        self.refresh_topics_button = QPushButton('🔄 Refresh Topics')
        self.refresh_topics_button.clicked.connect(self.refresh_topics)
        
        topic_header.addWidget(topic_label)
        topic_header.addStretch()
        topic_header.addWidget(self.refresh_topics_button)
        
        self.topic_list = QListWidget()
        self.topic_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self.topic_list.setStyleSheet("""
            QListWidget {
                border: 2px solid #bdc3c7;
                border-radius: 5px;
                padding: 5px;
                font-size: 11px;
            }
            QListWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
        """)
        
        # Selection buttons
        selection_buttons = QHBoxLayout()
        self.select_all_button = QPushButton('Select All')
        self.clear_selection_button = QPushButton('Clear Selection')
        self.select_all_button.clicked.connect(self.select_all_topics)
        self.clear_selection_button.clicked.connect(self.clear_topic_selection)
        
        selection_buttons.addWidget(self.select_all_button)
        selection_buttons.addWidget(self.clear_selection_button)
        selection_buttons.addStretch()
        
        topic_layout.addLayout(topic_header)
        topic_layout.addWidget(self.topic_list)
        topic_layout.addLayout(selection_buttons)
        
        topic_group.setLayout(topic_layout)
        layout.addWidget(topic_group)
        
        # Save location group
        location_group = QGroupBox("Save Location")
        location_layout = QVBoxLayout()

        dir_row = QHBoxLayout()
        location_label = QLabel('Directory:')
        location_label.setStyleSheet("font-weight: bold;")

        self.location_input = QLineEdit()
        self.location_input.setPlaceholderText('/path/to/save/bags')
        default_path = os.path.expanduser('~/ros2_bags')
        self.location_input.setText(default_path)

        browse_button = QPushButton('📁 Browse')
        browse_button.clicked.connect(self.browse_location)

        dir_row.addWidget(location_label)
        dir_row.addWidget(self.location_input)
        dir_row.addWidget(browse_button)

        format_row = QHBoxLayout()
        format_label = QLabel('Storage Format:')
        format_label.setStyleSheet("font-weight: bold;")

        self.storage_format_combo = QComboBox()
        self.storage_format_combo.addItem('mcap', 'mcap')
        self.storage_format_combo.addItem('sqlite3', 'sqlite3')
        self.storage_format_combo.setToolTip(
            'mcap: default, streaming append format with lower overhead,\n'
            '      recommended for high-bitrate topics (.mcap)\n'
            'sqlite3: legacy ROS2 format (.db3)'
        )
        self.storage_format_combo.setStyleSheet("""
            QComboBox {
                padding: 4px 8px;
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                font-size: 12px;
                min-width: 100px;
            }
        """)

        format_row.addWidget(format_label)
        format_row.addWidget(self.storage_format_combo)
        format_row.addStretch()

        location_layout.addLayout(dir_row)
        location_layout.addLayout(format_row)

        location_group.setLayout(location_layout)
        layout.addWidget(location_group)
        
        # Control buttons
        control_group = QGroupBox("Recording Controls")
        control_layout = QVBoxLayout()
        
        duration_row = QHBoxLayout()
        duration_label = QLabel('Total Duration:')
        duration_label.setStyleSheet("font-weight: bold;")
        self.duration_spinbox = QSpinBox()
        self.duration_spinbox.setMinimum(0)
        self.duration_spinbox.setMaximum(3600)
        self.duration_spinbox.setValue(0)
        self.duration_spinbox.setSpecialValueText('No limit')
        self.duration_spinbox.setSuffix(' sec')
        self.duration_spinbox.setToolTip('Stop recording automatically after this many seconds. 0 = record until manually stopped.')
        duration_row.addWidget(duration_label)
        duration_row.addWidget(self.duration_spinbox)
        duration_row.addStretch()
        control_layout.addLayout(duration_row)

        split_row = QHBoxLayout()
        split_label = QLabel('Split Every:')
        split_label.setStyleSheet("font-weight: bold;")
        self.split_duration_spinbox = QSpinBox()
        self.split_duration_spinbox.setMinimum(0)
        self.split_duration_spinbox.setMaximum(3600)
        self.split_duration_spinbox.setValue(0)
        self.split_duration_spinbox.setSpecialValueText('No split')
        self.split_duration_spinbox.setSuffix(' sec')
        self.split_duration_spinbox.setToolTip('Split the bag into a new file every N seconds. 0 = single bag file.')
        split_row.addWidget(split_label)
        split_row.addWidget(self.split_duration_spinbox)
        split_row.addStretch()
        control_layout.addLayout(split_row)
        
        button_layout = QHBoxLayout()
        self.start_button = QPushButton('🔴 Start Recording')
        self.stop_button = QPushButton('⏹️ Stop Recording')
        self.stop_button.setEnabled(False)
        
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                font-weight: bold;
                font-size: 14px;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #229954;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        
        self.stop_button.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                font-weight: bold;
                font-size: 14px;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        
        self.start_button.clicked.connect(self.start_recording)
        self.stop_button.clicked.connect(self.stop_recording)
        
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        
        control_layout.addLayout(button_layout)
        control_group.setLayout(control_layout)
        layout.addWidget(control_group)
        
        # Status/Info display
        status_group = QGroupBox("Recording Information")
        status_layout = QVBoxLayout()
        
        self.status_label = QLabel('Status: Ready')
        self.status_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #2c3e50;")
        
        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setMaximumHeight(100)
        self.info_text.setStyleSheet("""
            QTextEdit {
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                padding: 5px;
                font-size: 11px;
                background-color: #ecf0f1;
            }
        """)
        self.info_text.setText('Ready to record. Select topics and click "Start Recording".')
        
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.info_text)
        
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)
        
        # Initialize with topics
        self.refresh_topics()
    
    def refresh_topics(self):
        """Refresh the list of available topics."""
        try:
            self.topic_list.clear()
            topics = self.bag_recorder.get_all_topics()
            
            if topics:
                self.topic_list.addItems(topics)
                self.info_text.append(f'\n✓ Found {len(topics)} topics')
            else:
                self.topic_list.addItem('No topics available')
                self.info_text.append('\n⚠ No topics found. Make sure ROS2 nodes are running.')
        except Exception as e:
            print(f"Error refreshing topics: {e}")
            self.info_text.append(f'\n✗ Error: {e}')
    
    def select_all_topics(self):
        """Select all topics in the list."""
        for i in range(self.topic_list.count()):
            item = self.topic_list.item(i)
            if item.text() != 'No topics available':
                item.setSelected(True)
    
    def clear_topic_selection(self):
        """Clear all topic selections."""
        self.topic_list.clearSelection()
    
    def browse_location(self):
        """Open file dialog to select save location."""
        directory = QFileDialog.getExistingDirectory(
            self, 
            'Select Save Location',
            self.location_input.text()
        )
        if directory:
            self.location_input.setText(directory)
    
    def start_recording(self):
        """Start bag recording."""
        selected_items = self.topic_list.selectedItems()
        selected_topics = [item.text() for item in selected_items]
        save_location = self.location_input.text()
        storage_format = self.storage_format_combo.currentData()

        # Validate inputs
        if not selected_topics:
            self.status_label.setText('Status: ⚠ Please select at least one topic!')
            self.status_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #e74c3c;")
            return

        if selected_topics == ['No topics available']:
            self.status_label.setText('Status: ⚠ No topics available!')
            self.status_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #e74c3c;")
            return

        if not save_location:
            self.status_label.setText('Status: ⚠ Please specify save location!')
            self.status_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #e74c3c;")
            return

        # Write current widget values into bag_recorder.options - this merges
        # seamlessly with any values pre-populated from a record config file,
        # since the user only overrides what they actually changed in the GUI.
        duration = self.duration_spinbox.value()
        split_duration = self.split_duration_spinbox.value()
        self.bag_recorder.options['topics'] = selected_topics
        self.bag_recorder.options['storage'] = storage_format
        self.bag_recorder.options['max_bag_duration'] = split_duration
        self.bag_recorder.options['output_dir'] = save_location

        success = self.bag_recorder.start_recording(save_location, duration)

        if success:
            self.status_label.setText(f'Status: 🔴 Recording {len(selected_topics)} topics...')
            self.status_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #27ae60;")

            self.info_text.append(f'\n▶ Recording started')
            self.info_text.append(f'  Topics: {", ".join(selected_topics)}')
            self.info_text.append(f'  Location: {save_location}')
            self.info_text.append(f'  Format: {storage_format}')
            
            if duration > 0:
                self.info_text.append(f'  Total Duration: {duration} sec (auto-stop)')
            else:
                self.info_text.append(f'  Total Duration: unlimited')
            if split_duration > 0:
                self.info_text.append(f'  Split Every: {split_duration} sec')

            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.topic_list.setEnabled(False)
            self.location_input.setEnabled(False)
            self.storage_format_combo.setEnabled(False)
            self.duration_spinbox.setEnabled(False)
            self.split_duration_spinbox.setEnabled(False)
            
            # Start update timer
            self.recording_start_time = time.time()
            self.recording_duration = duration
            self.update_timer.start(1000)
        else:
            self.status_label.setText('Status: ✗ Failed to start recording!')
            self.status_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #e74c3c;")
            self.info_text.append('\n✗ Failed to start recording. Check console for errors.')
    
    def stop_recording(self):
        """Stop bag recording."""
        self.update_timer.stop()
        
        bag_path = self.bag_recorder.stop_recording()
        
        if bag_path:
            self.status_label.setText('Status: ✓ Recording stopped')
            self.status_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #2980b9;")
            self.info_text.append(f'\n⏹ Recording stopped')
            self.info_text.append(f'  Saved to: {bag_path}')
        else:
            self.status_label.setText('Status: ⚠ Error stopping recording')
            self.status_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #e74c3c;")
        
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.topic_list.setEnabled(True)
        self.location_input.setEnabled(True)
        self.storage_format_combo.setEnabled(True)
        self.duration_spinbox.setEnabled(True)
        self.split_duration_spinbox.setEnabled(True)
        self.recording_start_time = None
        self.recording_duration = 0
    
    def update_recording_info(self):
        """Update recording duration display."""
        if self.recording_start_time:
            elapsed = int(time.time() - self.recording_start_time)
            minutes = elapsed // 60
            seconds = elapsed % 60
            self.status_label.setText(
                f'Status: 🔴 Recording... Duration: {minutes:02d}:{seconds:02d}'
            )

            # Auto-stop when set duration is reached
            if self.recording_duration > 0 and elapsed >= self.recording_duration:
                self.stop_recording()
                return

            if self.bag_recorder.recording_process:
                retcode = self.bag_recorder.recording_process.poll()
                if retcode is not None:
                    if retcode == 0:
                        # Clean exit — duration expired or normal stop
                        self.stop_recording()
                    else:
                        # Process failed — read stderr log tail and show error
                        self.update_timer.stop()
                        stderr_output = self.bag_recorder.read_stderr_tail(300)
                        self.bag_recorder.recording_process = None
                        self.bag_recorder.is_recording = False
                        self.recording_start_time = None

                        error_msg = stderr_output if stderr_output else f'Process exited with code {retcode}'
                        self.status_label.setText('Status: ✗ Recording failed!')
                        self.status_label.setStyleSheet(
                            "font-size: 13px; font-weight: bold; color: #e74c3c;"
                        )
                        self.info_text.append(f'\n✗ Recording process error:\n  {error_msg}')

                        self.start_button.setEnabled(True)
                        self.stop_button.setEnabled(False)
                        self.topic_list.setEnabled(True)
                        self.location_input.setEnabled(True)
                        self.storage_format_combo.setEnabled(True)
                        self.duration_spinbox.setEnabled(True)
                        self.split_duration_spinbox.setEnabled(True)
    
    def cleanup(self):
        """Clean up resources."""
        try:
            self.update_timer.stop()
            self.bag_recorder.cleanup()
        except Exception as e:
            print(f"Error during cleanup: {e}")
