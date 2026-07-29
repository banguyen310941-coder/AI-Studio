
from __future__ import annotations
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox,QDoubleSpinBox,QFormLayout,QFrame,QHBoxLayout,QLabel,QPushButton,QScrollArea,QVBoxLayout,QWidget,QMessageBox
from app.audio.audio_mixer_service import AudioMixerService
from app.audio.ffmpeg_audio_compiler import FFmpegAudioCompiler

class AudioMixerWidget(QFrame):
    audio_changed=Signal()
    def __init__(self,timeline_service,parent=None):
        super().__init__(parent); self.setObjectName("card"); self.service=AudioMixerService(timeline_service); self._rows={}; self._build(); self.refresh()
    def _build(self):
        layout=QVBoxLayout(self); title=QLabel("Audio Mixer Studio",self); title.setObjectName("sectionTitle"); layout.addWidget(title)
        desc=QLabel("Điều chỉnh volume, pan, mute/solo và xem FFmpeg Audio Mix Plan.",self); desc.setObjectName("description"); layout.addWidget(desc)
        self.body=QWidget(self); self.body_layout=QVBoxLayout(self.body); self.body_layout.setContentsMargins(0,0,0,0); layout.addWidget(self.body)
        row=QHBoxLayout(); preview=QPushButton("Xem Audio Mix Plan",self); preview.clicked.connect(self._preview); row.addWidget(preview); row.addStretch(); layout.addLayout(row)
        self.plan=QLabel("",self); self.plan.setWordWrap(True); self.plan.setObjectName("description"); layout.addWidget(self.plan)
    def refresh(self):
        self.service.normalize()
        while self.body_layout.count():
            item=self.body_layout.takeAt(0); w=item.widget();
            if w: w.deleteLater()
        self._rows={}
        tracks=self.service.audio_tracks()
        if not tracks: self.body_layout.addWidget(QLabel("Chưa có audio track.",self.body)); return
        for track in tracks:
            panel=QFrame(self.body); form=QFormLayout(panel); form.addRow(QLabel(str(track.get("name","Audio")),panel))
            volume=QDoubleSpinBox(panel); volume.setRange(0,2); volume.setSingleStep(.05); volume.setValue(float(track.get("volume",1)))
            pan=QDoubleSpinBox(panel); pan.setRange(-1,1); pan.setSingleStep(.1); pan.setValue(float(track.get("pan",0)))
            mute=QCheckBox("Mute",panel); mute.setChecked(bool(track.get("muted",False))); solo=QCheckBox("Solo",panel); solo.setChecked(bool(track.get("solo",False)))
            flags=QWidget(panel); h=QHBoxLayout(flags); h.setContentsMargins(0,0,0,0); h.addWidget(mute); h.addWidget(solo); h.addStretch()
            apply=QPushButton("Áp dụng",panel); tid=str(track.get("id")); apply.clicked.connect(lambda _=False,t=tid,v=volume,p=pan,m=mute,s=solo:self._apply(t,v,p,m,s))
            form.addRow("Volume",volume); form.addRow("Pan L/R",pan); form.addRow("Trạng thái",flags); form.addRow(apply); self.body_layout.addWidget(panel)
        self.body_layout.addStretch()
    def _apply(self,tid,v,p,m,s):
        if self.service.update_track(tid,volume=v.value(),pan=p.value(),muted=m.isChecked(),solo=s.isChecked()): self.audio_changed.emit(); self.refresh()
    def _preview(self):
        try: plan=FFmpegAudioCompiler(self.service).build(); self.plan.setText(plan.filter_complex)
        except ValueError as exc: QMessageBox.information(self,"Audio Mix Plan",str(exc))
