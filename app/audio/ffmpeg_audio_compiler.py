
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any

@dataclass(slots=True)
class AudioMixPlan:
    inputs: list[str]
    filter_complex: str
    output_label: str = "[amixout]"
    def ffmpeg_args(self, output_path: str|Path, ffmpeg_path: str="ffmpeg") -> list[str]:
        args=[ffmpeg_path,"-y"]
        for item in self.inputs: args += ["-i", item]
        args += ["-filter_complex",self.filter_complex,"-map",self.output_label,"-c:a","aac","-b:a","192k",str(output_path)]
        return args

class FFmpegAudioCompiler:
    """Biên dịch audio tracks thành filter graph volume/pan/fade/amix."""
    def __init__(self, mixer_service) -> None: self.mixer=mixer_service
    def build(self) -> AudioMixPlan:
        self.mixer.normalize(); inputs=[]; filters=[]; labels=[]; index=0
        for track in self.mixer.effective_tracks():
            tv=max(0.0,float(track.get("volume",1.0))); pan=max(-1.0,min(1.0,float(track.get("pan",0.0))))
            left=min(1.0,1.0-pan); right=min(1.0,1.0+pan)
            for clip in track.get("clips",[]):
                if not clip.get("enabled",True) or not clip.get("source"): continue
                inputs.append(str(clip["source"])); duration=max(.1,float(clip.get("duration",.1)))
                start=max(0.0,float(clip.get("start",0.0))); fi=min(duration,max(0.0,float(clip.get("fade_in",0.0))))
                fo=min(duration,max(0.0,float(clip.get("fade_out",0.0))))
                chain=f"[{index}:a]atrim=0:{duration:.3f},asetpts=PTS-STARTPTS,volume={tv*float(clip.get('volume',1.0)):.4f},pan=stereo|c0={left:.4f}*c0|c1={right:.4f}*c1"
                if fi>0: chain += f",afade=t=in:st=0:d={fi:.3f}"
                if fo>0: chain += f",afade=t=out:st={max(0.0,duration-fo):.3f}:d={fo:.3f}"
                label=f"a{index}"; chain += f",adelay={int(start*1000)}|{int(start*1000)}[{label}]"
                filters.append(chain); labels.append(f"[{label}]"); index+=1
        if not labels: raise ValueError("Không có audio clip khả dụng để mix.")
        filters.append("".join(labels)+f"amix=inputs={len(labels)}:duration=longest:normalize=0[amixout]")
        return AudioMixPlan(inputs,";".join(filters))
