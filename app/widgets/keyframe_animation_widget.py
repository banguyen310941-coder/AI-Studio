
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QAbstractItemView,QComboBox,QDoubleSpinBox,QFrame,QHBoxLayout,QHeaderView,QLabel,QMessageBox,QPushButton,QTableWidget,QTableWidgetItem,QVBoxLayout,QWidget
from app.animation import FFmpegKeyframeCompiler,KeyframeService
class KeyframeAnimationWidget(QFrame):
    animation_changed=Signal(); PROPERTIES=[('Opacity','opacity'),('Scale','scale'),('Vị trí X','x'),('Vị trí Y','y'),('Rotation','rotation')]
    def __init__(self,timeline_service,parent=None):
        super().__init__(parent); self.setObjectName('card'); self.service=KeyframeService(timeline_service); self._clip_id=None; self._build(); self.setEnabled(False)
    def _build(self):
        root=QVBoxLayout(self); top=QHBoxLayout(); title=QLabel('◆ Keyframe Animation',self); title.setObjectName('sectionTitle'); self.clip_label=QLabel('Chưa chọn video clip',self); self.clip_label.setObjectName('description'); top.addWidget(title); top.addWidget(self.clip_label); top.addStretch(); root.addLayout(top)
        row=QHBoxLayout(); self.prop=QComboBox(self)
        for a,b in self.PROPERTIES:self.prop.addItem(a,b)
        self.time=QDoubleSpinBox(self); self.time.setDecimals(3); self.time.setSuffix(' s'); self.time.setRange(0,86400); self.value=QDoubleSpinBox(self); self.value.setDecimals(4); self.value.setRange(-10000,10000); self.value.setValue(1); self.ease=QComboBox(self)
        for a,b in [('Linear','linear'),('Ease In','ease_in'),('Ease Out','ease_out'),('Ease In/Out','ease_in_out'),('Hold','hold')]:self.ease.addItem(a,b)
        add=QPushButton('＋ Thêm keyframe',self); add.setObjectName('primaryButton'); add.clicked.connect(self._add)
        for w in [QLabel('Thuộc tính:'),self.prop,QLabel('Thời gian:'),self.time,QLabel('Giá trị:'),self.value,QLabel('Easing:'),self.ease,add]:row.addWidget(w)
        row.addStretch(); root.addLayout(row); self.table=QTableWidget(0,4,self); self.table.setHorizontalHeaderLabels(['Thuộc tính','Thời gian','Giá trị','Easing']); self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); self.table.itemSelectionChanged.connect(self._load); root.addWidget(self.table)
        actions=QHBoxLayout(); update=QPushButton('Cập nhật'); update.clicked.connect(self._update); delete=QPushButton('Xóa'); delete.clicked.connect(self._delete); clear=QPushButton('Xóa tất cả'); clear.clicked.connect(self._clear)
        for w in [update,delete,clear]:actions.addWidget(w)
        actions.addStretch(); root.addLayout(actions); self.preview=QLabel('FFmpeg: không có animation filter'); self.preview.setWordWrap(True); self.preview.setObjectName('description'); root.addWidget(self.preview)
    def select_clip(self,clip_id):
        self._clip_id=clip_id; found=self.service.timeline_service.find_clip(clip_id) if clip_id else None
        valid=bool(found and found[0].get('type')=='video'); self.setEnabled(valid); self.clip_label.setText(str(found[1].get('title')) if valid else 'Keyframe chỉ dùng cho video clip'); self.time.setMaximum(float(found[1].get('duration',1)) if valid else 1); self.refresh()
    def refresh(self):
        fs=self.service.keyframes_for_clip(self._clip_id) if self._clip_id else []; self.table.setRowCount(0); labels={b:a for a,b in self.PROPERTIES}
        for r,f in enumerate(fs):
            self.table.insertRow(r)
            for c,v in enumerate([labels.get(f.get('property'),f.get('property')),f"{float(f.get('time',0)):.3f}",f"{float(f.get('value',0)):.4f}",f.get('easing','linear')]):self.table.setItem(r,c,QTableWidgetItem(str(v)))
        self.preview.setText('FFmpeg: '+FFmpegKeyframeCompiler.preview(fs))
    def _index(self):
        rows=self.table.selectionModel().selectedRows(); return rows[0].row() if rows else -1
    def _load(self):
        i=self._index(); fs=self.service.keyframes_for_clip(self._clip_id) if self._clip_id else []
        if 0<=i<len(fs):
            f=fs[i]; self.prop.setCurrentIndex(max(0,self.prop.findData(f.get('property')))); self.time.setValue(float(f.get('time',0))); self.value.setValue(float(f.get('value',0))); self.ease.setCurrentIndex(max(0,self.ease.findData(f.get('easing'))))
    def _add(self):
        if self._clip_id and self.service.add(self._clip_id,self.prop.currentData(),self.time.value(),self.value.value(),self.ease.currentData()):self.refresh();self.animation_changed.emit()
    def _update(self):
        i=self._index()
        if self._clip_id and i>=0 and self.service.update(self._clip_id,i,time=self.time.value(),value=self.value.value(),easing=self.ease.currentData()):self.refresh();self.animation_changed.emit()
    def _delete(self):
        i=self._index()
        if self._clip_id and i>=0 and self.service.remove(self._clip_id,i):self.refresh();self.animation_changed.emit()
    def _clear(self):
        if self._clip_id and QMessageBox.question(self,'Xóa keyframe','Xóa toàn bộ keyframe của clip?')==QMessageBox.StandardButton.Yes and self.service.clear(self._clip_id):self.refresh();self.animation_changed.emit()
