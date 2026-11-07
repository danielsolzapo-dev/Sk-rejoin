"""Render the existing SK status geometry at the requested physical pixel size."""
import io

def render_icon(name, size, palette):
    from PIL import Image, ImageDraw
    token={'online':'success','offline':'muted','busy':'info','warning':'warning','error':'error'}[name]
    color=palette[token]
    image=Image.new('RGBA',(size*4,size*4),(0,0,0,0))
    draw=ImageDraw.Draw(image)
    def points(values):return [(round(x*size/6),round(y*size/6)) for x,y in values]
    stroke=max(2,round(size/3))
    draw.ellipse((size*4/6,size*4/6,size*20/6,size*20/6),outline=color,width=stroke)
    if name=='online':draw.line(points([(8,12),(11,15),(16,9)]),fill=color,width=stroke)
    if name in ('busy','warning'):draw.line(points([(12,7),(12,12),(15,14)]),fill=color,width=stroke)
    if name=='error':
        draw.line(points([(12,7),(12,13)]),fill=color,width=stroke)
        draw.ellipse((size*11/6,size*15/6,size*13/6,size*17/6),fill=color)
    out=io.BytesIO()
    image.resize((size,size),Image.Resampling.LANCZOS).save(out,format='PNG')
    return out.getvalue()
