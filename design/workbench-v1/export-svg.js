/*
 * Browser-side design export helper, used only during design handoff.
 * Produces native SVG shapes, text and vector icons; no foreignObject,
 * screenshot embedding or remote resources. It is not loaded by the app.
 */
window.exportDesignSvg = function exportDesignSvg() {
  const esc = value => String(value ?? "").replace(/[&<>"']/g, char =>
    ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&apos;"}[char]));
  const n = value => Number(value).toFixed(2);
  const px = value => parseFloat(value) || 0;
  const visibleColor = color => color && color !== "transparent" && color !== "rgba(0, 0, 0, 0)";
  const width = document.documentElement.clientWidth;
  const height = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);
  let clipIndex = 0;
  const definitions = [];
  function rectangle(x,y,w,h,fill,radius=0,stroke="",strokeWidth=0) {
    return `<rect x="${n(x)}" y="${n(y)}" width="${n(Math.max(0,w))}" height="${n(Math.max(0,h))}" rx="${n(radius)}" fill="${esc(fill)}"${stroke?` stroke="${esc(stroke)}" stroke-width="${n(strokeWidth)}"`:""}/>`;
  }
  function text(x,y,value,style,sizeOverride) {
    const size=sizeOverride||px(style.fontSize);
    return `<text x="${n(x)}" y="${n(y)}" font-family="${esc(style.fontFamily)}" font-size="${n(size)}" font-weight="${style.fontWeight}" fill="${esc(style.color)}"${style.letterSpacing!=="normal"?` letter-spacing="${esc(style.letterSpacing)}"`:""}>${esc(value)}</text>`;
  }
  function textNode(node,style) {
    if(!node.textContent.trim()) return "";
    const range=document.createRange(),lines=[];
    const value=node.textContent;
    for(let i=0;i<value.length;i++){
      range.setStart(node,i);range.setEnd(node,i+1);
      const rect=range.getBoundingClientRect();
      if(!rect.width||!rect.height)continue;
      const key=Math.round(rect.y*2)/2;
      let line=lines.at(-1);
      if(!line||Math.abs(line.key-key)>1){
        line={key,x:rect.x,y:rect.y,height:rect.height,value:""};lines.push(line);
      }
      line.value+=value[i].replace(/\s/g," ");
    }
    return lines.map(line=>text(line.x+scrollX,line.y+scrollY+line.height*.79,line.value,style)).join("");
  }
  function walk(element) {
    if(element.nodeType===Node.TEXT_NODE)return textNode(element,getComputedStyle(element.parentElement));
    if(element.nodeType!==Node.ELEMENT_NODE)return "";
    if(["SCRIPT","STYLE","META","LINK","TITLE"].includes(element.tagName)||element.classList.contains("screen-reader")||element.id==="toast")return "";
    const style=getComputedStyle(element),rect=element.getBoundingClientRect();
    if(style.display==="none"||style.visibility==="hidden"||+style.opacity===0||(!rect.width&&!rect.height))return "";
    const x=rect.x+scrollX,y=rect.y+scrollY,w=rect.width,h=rect.height;
    const radius=Math.min(px(style.borderTopLeftRadius),w/2,h/2);
    let result="";
    if(element.tagName.toLowerCase()==="svg"){
      const clone=element.cloneNode(true);
      clone.setAttribute("x",n(x));clone.setAttribute("y",n(y));
      clone.setAttribute("width",n(w));clone.setAttribute("height",n(h));
      clone.setAttribute("color",style.color);
      clone.setAttribute("fill",style.fill);
      clone.setAttribute("stroke",style.stroke);
      clone.setAttribute("stroke-width",style.strokeWidth);
      clone.setAttribute("stroke-linecap",style.strokeLinecap);
      clone.setAttribute("stroke-linejoin",style.strokeLinejoin);
      clone.removeAttribute("class");
      return clone.outerHTML;
    }
    if(element.tagName==="INPUT"&&["checkbox","radio"].includes(element.type)){
      const toggle=element.classList.contains("toggle");
      if(toggle){
        result+=rectangle(x,y,w,h,element.checked?"#8ca17a":"#dce2d3",h/2);
        result+=`<circle cx="${n(x+(element.checked?w-9:9))}" cy="${n(y+h/2)}" r="6" fill="#fff"/>`;
      }else{
        result+=rectangle(x,y,w,h,element.checked?"#ce603b":"#fff",element.type==="radio"?w/2:2,element.checked?"#ce603b":"#b7beae",1);
        if(element.checked){
          result+=element.type==="radio"?`<circle cx="${n(x+w/2)}" cy="${n(y+h/2)}" r="3" fill="#fff"/>`:
            `<path d="M ${n(x+w*.2)} ${n(y+h*.5)} L ${n(x+w*.42)} ${n(y+h*.7)} L ${n(x+w*.8)} ${n(y+h*.25)}" fill="none" stroke="#fff" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>`;
        }
      }
      return result;
    }
    if(visibleColor(style.backgroundColor))result+=rectangle(x,y,w,h,style.backgroundColor,radius);
    const borderWidths=["Top","Right","Bottom","Left"].map(side=>px(style[`border${side}Width`]));
    const colors=["Top","Right","Bottom","Left"].map(side=>style[`border${side}Color`]);
    if(borderWidths.every(value=>value===borderWidths[0])&&colors.every(value=>value===colors[0])&&borderWidths[0]){
      const b=borderWidths[0];
      result+=rectangle(x+b/2,y+b/2,w-b,h-b,"none",radius,colors[0],b);
    }else{
      [[x,y,x+w,y],[x+w,y,x+w,y+h],[x,y+h,x+w,y+h],[x,y,x,y+h]].forEach((points,i)=>{
        if(borderWidths[i])result+=`<line x1="${n(points[0])}" y1="${n(points[1])}" x2="${n(points[2])}" y2="${n(points[3])}" stroke="${colors[i]}" stroke-width="${n(borderWidths[i])}"/>`;
      });
    }
    if(["INPUT","SELECT","TEXTAREA"].includes(element.tagName)){
      let value=element.tagName==="SELECT"?element.options[element.selectedIndex]?.text:element.value||element.placeholder;
      const size=px(style.fontSize),lineHeight=px(style.lineHeight)||size*1.6;
      const insetX=px(style.paddingLeft)+px(style.borderLeftWidth);
      const insetY=px(style.paddingTop)+px(style.borderTopWidth);
      const lines=element.tagName==="TEXTAREA"?String(value).split("\n"):[String(value||"")];
      lines.forEach((line,i)=>result+=text(x+insetX,y+insetY+size*.96+i*lineHeight,line,style));
      if(element.tagName==="SELECT")result+=`<path d="m${n(x+w-17)},${n(y+h/2-2)} 4,4 4,-4" stroke="#8b9580" stroke-width="1.3" fill="none"/>`;
    }else{
      for(const node of element.childNodes)result+=walk(node);
    }
    let attributes=`data-name="${esc(element.id||element.className||element.tagName.toLowerCase())}"`;
    if(+style.opacity<1)attributes+=` opacity="${style.opacity}"`;
    if(["hidden","auto","scroll"].includes(style.overflowX)||["hidden","auto","scroll"].includes(style.overflowY)){
      const id=`clip-${clipIndex++}`;
      definitions.push(`<clipPath id="${id}">${rectangle(x,y,w,h,"#fff",radius)}</clipPath>`);
      attributes+=` clip-path="url(#${id})"`;
    }
    return `<g ${attributes}>${result}</g>`;
  }
  const body=walk(document.body);
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}"><title>${esc(document.title)}</title><desc>镜流工坊交互原型；原生文字与形状设计导出。示例数据，不含 Figma 自动布局与交互连线。</desc><defs>${definitions.join("")}</defs>${rectangle(0,0,width,height,"#f5f5f1")}${body}</svg>`;
};
