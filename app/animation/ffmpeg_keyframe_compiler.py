
class FFmpegKeyframeCompiler:
    @staticmethod
    def _expr(frames,default):
        if not frames:return f"{default:.6f}"
        frames=sorted(frames,key=lambda f:float(f.get('time',0))); expr=f"{float(frames[-1]['value']):.6f}"
        for a,b in reversed(list(zip(frames,frames[1:]))):
            at,bt=float(a['time']),float(b['time']); av,bv=float(a['value']),float(b['value']); p=f"((t-{at:.6f})/{max(.000001,bt-at):.6f})"
            e=a.get('easing','linear')
            if e=='hold': seg=f"{av:.6f}"
            else:
                if e=='ease_in':p=f"({p}*{p})"
                elif e=='ease_out':p=f"(1-(1-{p})*(1-{p}))"
                elif e=='ease_in_out':p=f"if(lt({p},0.5),2*{p}*{p},1-pow(-2*{p}+2,2)/2)"
                seg=f"({av:.6f}+({bv-av:.6f})*{p})"
            expr=f"if(lt(t,{bt:.6f}),{seg},{expr})"
        return f"if(lt(t,{float(frames[0]['time']):.6f}),{float(frames[0]['value']):.6f},{expr})"
    @classmethod
    def compile(cls,keyframes):
        groups={}
        for f in keyframes:groups.setdefault(str(f.get('property')),[]).append(f)
        out=[]
        if groups.get('opacity'):out.append(f"format=rgba,colorchannelmixer=aa='{cls._expr(groups['opacity'],1)}'")
        if groups.get('scale'):out.append(f"scale=w='iw*({cls._expr(groups['scale'],1)})':h='ih*({cls._expr(groups['scale'],1)})':eval=frame")
        if groups.get('rotation'):out.append(f"rotate=angle='({cls._expr(groups['rotation'],0)})*PI/180':ow=rotw(iw):oh=roth(ih)")
        if groups.get('x') or groups.get('y'):out.append(f"pad=width=iw+abs({cls._expr(groups.get('x',[]),0)}):height=ih+abs({cls._expr(groups.get('y',[]),0)}):x='max(0,{cls._expr(groups.get('x',[]),0)})':y='max(0,{cls._expr(groups.get('y',[]),0)})'")
        return out
    @classmethod
    def preview(cls,keyframes):return ','.join(cls.compile(keyframes)) or 'không có animation filter'
