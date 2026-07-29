
from __future__ import annotations
from copy import deepcopy
from typing import Any
DEFAULT_VALUES={"opacity":1.0,"scale":1.0,"x":0.0,"y":0.0,"rotation":0.0}
RANGES={"opacity":(0.0,1.0),"scale":(0.05,10.0),"x":(-10000.0,10000.0),"y":(-10000.0,10000.0),"rotation":(-3600.0,3600.0)}
EASINGS={"linear","ease_in","ease_out","ease_in_out","hold"}
class KeyframeService:
    def __init__(self,timeline_service): self.timeline_service=timeline_service
    def keyframes_for_clip(self,clip_id:str)->list[dict[str,Any]]:
        found=self.timeline_service.find_clip(clip_id)
        if found is None or found[0].get("type")!="video": return []
        frames=found[1].setdefault("keyframes",[]); frames.sort(key=lambda f:(float(f.get("time",0)),str(f.get("property",""))))
        return deepcopy(frames)
    def add(self,clip_id,property_name,time,value,easing="linear"):
        found=self.timeline_service.find_clip(clip_id)
        if found is None or found[0].get("type")!="video" or property_name not in DEFAULT_VALUES: return False
        clip=found[1]; duration=max(.1,float(clip.get("duration",.1))); t=max(0,min(duration,float(time))); lo,hi=RANGES[property_name]; v=max(lo,min(hi,float(value))); easing=easing if easing in EASINGS else "linear"
        self.timeline_service.checkpoint(); frames=clip.setdefault("keyframes",[])
        for f in frames:
            if f.get("property")==property_name and abs(float(f.get("time",0))-t)<.0005: f.update(time=t,value=v,easing=easing); break
        else: frames.append({"property":property_name,"time":t,"value":v,"easing":easing})
        frames.sort(key=lambda f:(float(f.get("time",0)),str(f.get("property","")))); return True
    def update(self,clip_id,index,*,time,value,easing):
        found=self.timeline_service.find_clip(clip_id)
        if found is None: return False
        frames=found[1].setdefault("keyframes",[])
        if not 0<=index<len(frames): return False
        prop=str(frames[index].get("property","opacity")); lo,hi=RANGES[prop]; duration=max(.1,float(found[1].get("duration",.1)))
        self.timeline_service.checkpoint(); frames[index].update(time=max(0,min(duration,float(time))),value=max(lo,min(hi,float(value))),easing=easing if easing in EASINGS else "linear"); frames.sort(key=lambda f:(float(f.get("time",0)),str(f.get("property","")))); return True
    def remove(self,clip_id,index):
        found=self.timeline_service.find_clip(clip_id)
        if found is None: return False
        frames=found[1].setdefault("keyframes",[])
        if not 0<=index<len(frames): return False
        self.timeline_service.checkpoint(); frames.pop(index); return True
    def clear(self,clip_id):
        found=self.timeline_service.find_clip(clip_id)
        if found is None or not found[1].get("keyframes"): return False
        self.timeline_service.checkpoint(); found[1]["keyframes"]=[]; return True
    def value_at(self,clip_id,property_name,time):
        fs=[f for f in self.keyframes_for_clip(clip_id) if f.get("property")==property_name]
        if not fs:return DEFAULT_VALUES[property_name]
        t=float(time)
        if t<=float(fs[0]["time"]):return float(fs[0]["value"])
        if t>=float(fs[-1]["time"]):return float(fs[-1]["value"])
        for a,b in zip(fs,fs[1:]):
            at,bt=float(a["time"]),float(b["time"])
            if at<=t<=bt:
                if a.get("easing")=="hold" or bt<=at:return float(a["value"])
                p=(t-at)/(bt-at); e=a.get("easing","linear")
                if e=="ease_in":p=p*p
                elif e=="ease_out":p=1-(1-p)**2
                elif e=="ease_in_out":p=2*p*p if p<.5 else 1-((-2*p+2)**2)/2
                return float(a["value"])+(float(b["value"])-float(a["value"]))*p
        return DEFAULT_VALUES[property_name]
