"""Move presentation literals into the central pt-BR catalog, preserving keys."""
import ast
import hashlib
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import ui_text
catalog=dict(ui_text.CATALOG)
def key(text):
    identity='ui_'+hashlib.sha1(text.encode()).hexdigest()[:12]
    catalog[identity]=text
    return identity
def human(value):
    if not value or not any(c.isalpha() for c in value):return False
    if value.startswith(('/', '#','http','Software\\','<','SK_VISUAL')):return False
    if value in ('Segoe UI','Segoe UI Variable','Consolas','Times New Roman'):return False
    if any(x in value for x in ('Content-Type','application/json','X-Rejoin','X-Heartbeat','roblox-player:')):return False
    return ' ' in value or '\n' in value or (value[0].isupper() and value[1:].islower() and '.' not in value)
class Catalog(ast.NodeTransformer):
    def visit_Expr(self,node):
        if isinstance(node.value,ast.Constant) and isinstance(node.value.value,str):return node
        return self.generic_visit(node)
    def visit_Constant(self,node):
        if isinstance(node.value,str) and human(node.value):
            return ast.copy_location(ast.Call(func=ast.Name(id='tr',ctx=ast.Load()),args=[ast.Constant(key(node.value))],keywords=[]),node)
        return node
    def visit_JoinedStr(self,node):
        text='';keywords=[]
        for value in node.values:
            if isinstance(value,ast.Constant):text+=str(value.value).replace('{','{{').replace('}','}}')
            else:
                name='p'+str(len(keywords));part='{'+name
                if value.conversion!=-1:part+='!'+chr(value.conversion)
                if value.format_spec:
                    if any(not isinstance(x,ast.Constant) for x in value.format_spec.values):return node
                    part+=':'+''.join(x.value for x in value.format_spec.values)
                text+=part+'}';keywords.append(ast.keyword(arg=name,value=self.visit(value.value)))
        if not human(text):return node
        return ast.copy_location(ast.Call(func=ast.Name(id='tr',ctx=ast.Load()),args=[ast.Constant(key(text))],keywords=keywords),node)
for name in ('desktop.py','ui_workspace.py','tray.py','ui_services.py'):
    path=Path(name);tree=Catalog().visit(ast.parse(path.read_text()));ast.fix_missing_locations(tree)
    tree.body=[node for node in tree.body if not (isinstance(node,ast.ImportFrom) and node.module=='ui_text')]
    tree.body.insert(1,ast.ImportFrom(module='ui_text',names=[ast.alias(name='tr')],level=0))
    path.write_text(ast.unparse(tree)+'\n')
Path('ui_text.py').write_text('"""Central pt-BR presentation catalog. No disk access from widget callbacks."""\nCATALOG = '+repr(catalog)+'\n\ndef tr(key, **values):\n    return CATALOG.get(key,key).format(**values)\n')
print('Catalog:',len(catalog),'entries')
