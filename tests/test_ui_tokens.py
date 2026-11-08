"""WCAG AA token pairs and isolated visual preference persistence."""
import os
from pathlib import Path
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import theme
import ui_preferences

def luminance(color):
    values=[int(color[i:i+2],16)/255 for i in (1,3,5)]
    values=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in values]
    return .2126*values[0]+.7152*values[1]+.0722*values[2]
def contrast(a,b):
    x,y=sorted([luminance(a),luminance(b)])
    return (y+.05)/(x+.05)
for name,palette in theme.PALETTES.items():
    for text in ('text','muted','accent','success','warning','error','info'):
        for surface in ('bg','surface','alternate','field','selection'):
            ratio=contrast(palette[text],palette[surface])
            assert ratio>=4.5,(name,text,surface,ratio)
    assert contrast('#ffffff',palette['primary'])>=4.5
    assert contrast(palette['text'],palette['selection'])>=4.5
with tempfile.TemporaryDirectory() as folder:
    os.environ['LOCALAPPDATA']=folder
    assert ui_preferences.load()['theme']=='dark'
    data={**ui_preferences.DEFAULTS,'theme':'light','columns':['account','age','status'],'manualWidths':{'account':130,'status':280}}
    ui_preferences.save(data)
    assert ui_preferences.load()==data
    assert not list(ui_preferences.location().parent.glob('*.tmp'))
print('PASS AA text token pairs and isolated UI preferences.')

# UI services preserve the existing file semantics when moved out of Tk callbacks.
import json
from unittest.mock import MagicMock,patch
import ui_services
with tempfile.TemporaryDirectory() as folder:
    root=Path(folder)/'version-fixture';root.mkdir()
    exe=root/'RobloxPlayerBeta.exe';exe.write_bytes(b'fixture-not-executed')
    target=root/'ClientSettings'/'ClientAppSettings.json';target.parent.mkdir()
    target.write_text(json.dumps({'unrelated':7}))
    registry=MagicMock();registry.QueryValueEx.return_value=('"'+str(exe)+'",0',1)
    with patch.dict(sys.modules,{'winreg':registry}):
        ui_services.change_fps(10)
        assert json.loads(target.read_text())=={'unrelated':7,'DFIntTaskSchedulerTargetFps':10}
        ui_services.change_fps(None)
        assert json.loads(target.read_text())=={'unrelated':7}
        target.unlink()
        ui_services.change_fps(None)
        assert not target.exists(),'Removing absent limit must not create a settings file'
with tempfile.TemporaryDirectory() as folder:
    os.environ['LOCALAPPDATA']=folder
    ui_preferences.save({'theme':'light'},revision=20)
    ui_preferences.save({'theme':'dark'},revision=10)
    assert ui_preferences.load()['theme']=='light','Delayed old workers must not overwrite a newer preference'
print('PASS extracted FPS behavior and preference write ordering.')

# Status icons are rasterized from the same geometry at the actual DPI size.
from ui_icons import render_icon
from PIL import Image
import io
for palette in theme.PALETTES.values():
    for size in (16,20,24,32):
        for name in ('online','offline','busy','warning','error'):
            image=Image.open(io.BytesIO(render_icon(name,size,palette)))
            assert image.size==(size,size) and image.mode=='RGBA'
print('PASS DPI-native status icon dimensions (16/20/24/32px)')
