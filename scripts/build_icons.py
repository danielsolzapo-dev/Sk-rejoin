"""Build the small vector icon set as SVG sources and crisp PNG variants."""
from pathlib import Path
from PIL import Image,ImageDraw
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import theme
root=Path(__file__).resolve().parents[1]/'artwork'/'icons'
for mode,palette in theme.PALETTES.items():
 for name,token in [('online','success'),('offline','muted'),('error','error'),('busy','warning')]:
  color=palette[token]
  for size in (16,20,24):
   svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24"><circle cx="12" cy="12" r="8" fill="none" stroke="{color}" stroke-width="2"/>'
   extra='<path d="M8 12l3 3 5-6" fill="none" stroke="'+color+'" stroke-width="2"/>' if name=='online' else '<path d="M12 7v6m0 3v1" stroke="'+color+'" stroke-width="2"/>' if name=='error' else '<path d="M12 7v5l3 2" fill="none" stroke="'+color+'" stroke-width="2"/>' if name=='busy' else ''
   (root/f'{mode}-{name}-{size}.svg').write_text(svg+extra+'</svg>')
   image=Image.new('RGBA',(size*4,size*4),(0,0,0,0));draw=ImageDraw.Draw(image)
   def points(values):return [(round(x*size/6),round(y*size/6)) for x,y in values]
   draw.ellipse((size*4/6,size*4/6,size*20/6,size*20/6),outline=color,width=max(2,round(size/3)))
   if name=='online':draw.line(points([(8,12),(11,15),(16,9)]),fill=color,width=max(2,round(size/3)))
   if name=='busy':draw.line(points([(12,7),(12,12),(15,14)]),fill=color,width=max(2,round(size/3)))
   if name=='error':
    draw.line(points([(12,7),(12,13)]),fill=color,width=max(2,round(size/3)))
    draw.ellipse((size*11/6,size*15/6,size*13/6,size*17/6),fill=color)
   image.resize((size,size),Image.Resampling.LANCZOS).save(root/f'{mode}-{name}-{size}.png')
print('Generated SVG and PNG icon variants.')
