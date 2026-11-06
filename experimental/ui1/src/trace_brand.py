"""Trace the user's monochrome logo alpha into native vector geometry.

This preserves its lettering, leaper, underline and relative positions. The
high-resolution reference is needed only at build time, not on the old ARM box.
"""
from pathlib import Path
from PIL import Image
import hashlib, json

HERE=Path(__file__).resolve().parent
src=HERE/'assets/jaguar-reference.png'
im=Image.open(src);alpha=im.getchannel('A');w,h=im.size;b=alpha.tobytes()
edges={}
def edge(a,z):edges.setdefault(a,[]).append(z)
for y in range(h):
    for x in range(w):
        i=y*w+x
        if b[i]<128:continue
        if y==0 or b[i-w]<128:edge((x,y),(x+1,y))
        if x==w-1 or b[i+1]<128:edge((x+1,y),(x+1,y+1))
        if y==h-1 or b[i+w]<128:edge((x+1,y+1),(x,y+1))
        if x==0 or b[i-1]<128:edge((x,y+1),(x,y))
loops=[]
while edges:
    start=next(iter(edges));at=start;points=[start]
    while True:
        nxt=edges[at].pop()
        if not edges[at]:del edges[at]
        points.append(nxt);at=nxt
        if at==start:break
    if len(points)>8:loops.append(points)

def simplify(points,eps=.7):
    if len(points)<3:return points
    ax,ay=points[0];bx,by=points[-1];dx=bx-ax;dy=by-ay
    norm=dx*dx+dy*dy
    far=0;idx=0
    for i,(x,y) in enumerate(points[1:-1],1):
        if norm:
            t=max(0,min(1,((x-ax)*dx+(y-ay)*dy)/norm))
            d=(x-ax-t*dx)**2+(y-ay-t*dy)**2
        else:d=(x-ax)**2+(y-ay)**2
        if d>far:far,idx=d,i
    if far>eps*eps:return simplify(points[:idx+1],eps)[:-1]+simplify(points[idx:],eps)
    return [points[0],points[-1]]

parts=[];count=0
for loop in loops:
    points=simplify(loop);count+=len(points)
    parts.append('M'+' L'.join(f'{x} {y}' for x,y in points)+' Z')
box=alpha.getbbox();x,y,r,bottom=box
svg=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x} {y} {r-x} {bottom-y}"><path fill-rule="evenodd" d="'+''.join(parts)+'"/></svg>\n'
(HERE/'assets/jaguar-stacked.svg').write_text(svg)
provenance={'source':'User-supplied artwork, 6 November 2026','jaguar_reference_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'stacked_logo':'Alpha outline converted to vector paths at 0.7-source-pixel tolerance. Entire lockup and underline retained.','licence':'Jaguar trademark artwork; excluded from the code MIT licence.'}
(HERE/'assets/branding-source.json').write_text(json.dumps(provenance,indent=2)+'\n')
print('Traced',len(loops),'contours;',count,'vector points.')
