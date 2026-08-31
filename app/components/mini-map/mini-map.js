// Native WeChat WebGL mall renderer. It keeps the old DOM map as a fallback.
const VERT = `
attribute vec3 a_position;
attribute vec3 a_normal;
uniform mat4 u_mvp;
uniform mat4 u_model;
uniform float u_point_size;
uniform float u_lit;
varying float v_light;
void main(){
  gl_Position=u_mvp*vec4(a_position,1.0);
  gl_PointSize=u_point_size;
  vec3 n=normalize((u_model*vec4(a_normal,0.0)).xyz);
  v_light=mix(1.0,0.58+max(dot(n,normalize(vec3(0.45,0.85,0.35))),0.0)*0.42,u_lit);
}`;
const FRAG = `
precision mediump float;
uniform vec4 u_color;
varying float v_light;
void main(){gl_FragColor=vec4(u_color.rgb*v_light,u_color.a);}`;

function identity(){return [1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1];}
function multiply(a,b){
  const out=new Array(16).fill(0);
  for(let c=0;c<4;c++) for(let r=0;r<4;r++) for(let k=0;k<4;k++) out[c*4+r]+=a[k*4+r]*b[c*4+k];
  return out;
}
function perspective(fovy,aspect,near,far){
  const f=1/Math.tan(fovy/2),nf=1/(near-far);
  return [f/aspect,0,0,0,0,f,0,0,0,0,(far+near)*nf,-1,0,0,2*far*near*nf,0];
}
function lookAt(eye,target,up){
  let zx=eye[0]-target[0],zy=eye[1]-target[1],zz=eye[2]-target[2];
  let len=Math.hypot(zx,zy,zz)||1; zx/=len;zy/=len;zz/=len;
  let xx=up[1]*zz-up[2]*zy,xy=up[2]*zx-up[0]*zz,xz=up[0]*zy-up[1]*zx;
  len=Math.hypot(xx,xy,xz)||1;xx/=len;xy/=len;xz/=len;
  const yx=zy*xz-zz*xy,yy=zz*xx-zx*xz,yz=zx*xy-zy*xx;
  return [xx,yx,zx,0,xy,yy,zy,0,xz,yz,zz,0,
    -(xx*eye[0]+xy*eye[1]+xz*eye[2]),-(yx*eye[0]+yy*eye[1]+yz*eye[2]),-(zx*eye[0]+zy*eye[1]+zz*eye[2]),1];
}
function model(x,y,z,sx,sy,sz){return [sx,0,0,0,0,sy,0,0,0,0,sz,0,x,y,z,1];}
function transform(m,p){
  const x=p[0],y=p[1],z=p[2],w=m[3]*x+m[7]*y+m[11]*z+m[15];
  return [(m[0]*x+m[4]*y+m[8]*z+m[12])/w,(m[1]*x+m[5]*y+m[9]*z+m[13])/w,(m[2]*x+m[6]*y+m[10]*z+m[14])/w];
}
function shader(gl,type,source){
  const s=gl.createShader(type); gl.shaderSource(s,source); gl.compileShader(s);
  if(!gl.getShaderParameter(s,gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s)||'shader compile failed');
  return s;
}
function colorOf(category){
  const text=String(category||'');
  if(/餐|菜|轻食/.test(text)) return [0.95,0.56,0.69,1];
  if(/咖啡|茶|奶|甜品|烘焙/.test(text)) return [0.66,0.51,0.88,1];
  if(/影院|儿童|商务/.test(text)) return [0.48,0.65,0.91,1];
  if(/服务/.test(text)) return [0.67,0.72,0.79,1];
  return [0.62,0.72,0.91,1];
}

Component({
  properties:{
    stores:{type:Array,value:[]},
    route:{type:Array,value:[]},
    routeNodes:{type:Array,value:[]},
    activeId:{type:String,value:''},
    floor:{type:Number,value:0}
  },
  data:{webglReady:false,webglFailed:false,floorCount:2,segs:[]},
  observers:{
    'stores,route,routeNodes,activeId,floor'(){ if(this._gl){this._routeStarted=Date.now();this.render();} }
  },
  lifetimes:{
    ready(){this.initWebGL();},
    detached(){this._destroyed=true;if(this._canvas&&this._raf)this._canvas.cancelAnimationFrame(this._raf);}
  },
  methods:{
    initWebGL(){
      this.createSelectorQuery().select('#mall3d').fields({node:true,size:true,rect:true}).exec(res=>{
        try{
          const hit=res&&res[0]; if(!hit||!hit.node) throw new Error('canvas node unavailable');
          const canvas=hit.node,gl=canvas.getContext('webgl',{antialias:true,alpha:false});
          if(!gl) throw new Error('WebGL unavailable');
          const info=wx.getWindowInfo?wx.getWindowInfo():wx.getSystemInfoSync();
          const dpr=Math.min(info.pixelRatio||1,2);
          canvas.width=Math.max(1,Math.round(hit.width*dpr)); canvas.height=Math.max(1,Math.round(hit.height*dpr));
          this._canvas=canvas;this._gl=gl;this._width=hit.width;this._height=hit.height;this._dpr=dpr;this._left=hit.left||0;this._top=hit.top||0;
          this._yaw=-0.64;this._pitch=0.48;this._routeStarted=Date.now();
          this.createProgram();this.createGeometry();
          gl.enable(gl.DEPTH_TEST);gl.enable(gl.BLEND);gl.blendFunc(gl.SRC_ALPHA,gl.ONE_MINUS_SRC_ALPHA);
          this.setData({webglReady:true,webglFailed:false});this.loop();
        }catch(err){console.error('[mini-map WebGL]',err);this.setData({webglFailed:true,webglReady:false});}
      });
    },
    createProgram(){
      const gl=this._gl,p=gl.createProgram();
      gl.attachShader(p,shader(gl,gl.VERTEX_SHADER,VERT));gl.attachShader(p,shader(gl,gl.FRAGMENT_SHADER,FRAG));gl.linkProgram(p);
      if(!gl.getProgramParameter(p,gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p)||'program link failed');
      this._program=p;gl.useProgram(p);
      this._loc={
        pos:gl.getAttribLocation(p,'a_position'),normal:gl.getAttribLocation(p,'a_normal'),
        mvp:gl.getUniformLocation(p,'u_mvp'),model:gl.getUniformLocation(p,'u_model'),
        color:gl.getUniformLocation(p,'u_color'),point:gl.getUniformLocation(p,'u_point_size'),lit:gl.getUniformLocation(p,'u_lit')
      };
    },
    createGeometry(){
      const gl=this._gl;
      const faces=[
        [[-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1],[0,0,1]],[[1,-1,-1],[-1,-1,-1],[-1,1,-1],[1,1,-1],[0,0,-1]],
        [[1,-1,1],[1,-1,-1],[1,1,-1],[1,1,1],[1,0,0]],[[-1,-1,-1],[-1,-1,1],[-1,1,1],[-1,1,-1],[-1,0,0]],
        [[-1,1,1],[1,1,1],[1,1,-1],[-1,1,-1],[0,1,0]],[[-1,-1,-1],[1,-1,-1],[1,-1,1],[-1,-1,1],[0,-1,0]]
      ];
      const positions=[],normals=[],indices=[];
      faces.forEach((f,fi)=>{const base=fi*4;for(let i=0;i<4;i++){positions.push(...f[i]);normals.push(...f[4]);}indices.push(base,base+1,base+2,base,base+2,base+3);});
      this._pos=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,this._pos);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(positions),gl.STATIC_DRAW);
      this._normal=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,this._normal);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(normals),gl.STATIC_DRAW);
      this._index=gl.createBuffer();gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,this._index);gl.bufferData(gl.ELEMENT_ARRAY_BUFFER,new Uint16Array(indices),gl.STATIC_DRAW);
      this._line=gl.createBuffer();this._cubeCount=indices.length;
    },
    loop(){
      if(this._destroyed)return;this.render();this._raf=this._canvas.requestAnimationFrame(()=>this.loop());
    },
    visibleStores(){
      const floor=Number(this.data.floor||0);return (this.data.stores||[]).filter(s=>!floor||Number(s.floor)===floor);
    },
    storePoint(s){return [(Number(s.pos_x||50)-50)*0.42,Number(s.floor)===2?8:0.8,(Number(s.pos_y||50)-50)*0.32];},
    render(){
      const gl=this._gl;if(!gl)return;
      gl.viewport(0,0,this._canvas.width,this._canvas.height);gl.clearColor(0.969,0.953,0.980,1);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
      const radius=52,eye=[Math.sin(this._yaw)*radius,18+this._pitch*30,Math.cos(this._yaw)*radius];
      const targetY=Number(this.data.floor)===2?7:Number(this.data.floor)===1?1:4;
      const view=lookAt(eye,[0,targetY,0],[0,1,0]),proj=perspective(Math.PI/4,this._canvas.width/this._canvas.height,0.1,160);
      this._vp=multiply(proj,view);this._projected=[];
      const floors=Number(this.data.floor)?[Number(this.data.floor)]:[1,2];
      floors.forEach(f=>this.drawBox(0,f===2?7.2:0,0,23,0.45,18,[0.98,0.97,0.94,f===2?0.82:1]));
      const elevator={x:520,y:520};
      const ep=this.nodePoint({...elevator,floor:1});
      this.drawBox(ep[0],5.4,ep[2],1.35,5.4,1.35,[0.20,0.75,0.82,0.48]);
      const esLow=this.nodePoint({x:720,y:320,floor:1}),esHigh=this.nodePoint({x:520,y:320,floor:2});
      for(let i=0;i<8;i++){const t=i/7;this.drawBox(esLow[0]+(esHigh[0]-esLow[0])*t,esLow[1]+(esHigh[1]-esLow[1])*t,esLow[2],1.35,0.18,0.9,[0.95,0.45,0.35,0.88]);}
      this.visibleStores().forEach(s=>{
        const p=this.storePoint(s),active=s.id===this.data.activeId;
        this.drawBox(p[0],p[1]+1.1,p[2],2.25,1.15,1.9,active?[0.94,0.27,0.31,1]:colorOf(s.category));
        const clip=transform(this._vp,[p[0],p[1]+2.3,p[2]]);
        this._projected.push({store:s,x:(clip[0]+1)*this._width/2,y:(1-clip[1])*this._height/2,z:clip[2]});
      });
      this.drawRoute();
    },
    bindCube(){
      const gl=this._gl,l=this._loc;gl.bindBuffer(gl.ARRAY_BUFFER,this._pos);gl.enableVertexAttribArray(l.pos);gl.vertexAttribPointer(l.pos,3,gl.FLOAT,false,0,0);
      gl.bindBuffer(gl.ARRAY_BUFFER,this._normal);gl.enableVertexAttribArray(l.normal);gl.vertexAttribPointer(l.normal,3,gl.FLOAT,false,0,0);gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,this._index);
    },
    drawBox(x,y,z,sx,sy,sz,color){
      const gl=this._gl,l=this._loc,m=model(x,y,z,sx,sy,sz);this.bindCube();
      gl.uniformMatrix4fv(l.model,false,new Float32Array(m));gl.uniformMatrix4fv(l.mvp,false,new Float32Array(multiply(this._vp,m)));
      gl.uniform4fv(l.color,new Float32Array(color));gl.uniform1f(l.point,1);gl.uniform1f(l.lit,1);gl.drawElements(gl.TRIANGLES,this._cubeCount,gl.UNSIGNED_SHORT,0);
    },
    drawRoute(){
      const gl=this._gl,l=this._loc,routeNodes=this.data.routeNodes||[];
      // 只播放后端 corridor_only 路由。没有走廊节点时宁可不画线，也不直线穿越实体。
      if(!routeNodes.length)return;
      const points=routeNodes.map(n=>this.nodePoint(n));
      if(!points.length)return;
      const flat=[];points.forEach(p=>flat.push(...p));gl.bindBuffer(gl.ARRAY_BUFFER,this._line);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(flat),gl.DYNAMIC_DRAW);
      gl.enableVertexAttribArray(l.pos);gl.vertexAttribPointer(l.pos,3,gl.FLOAT,false,0,0);gl.disableVertexAttribArray(l.normal);gl.vertexAttrib3f(l.normal,0,1,0);
      gl.uniformMatrix4fv(l.model,false,new Float32Array(identity()));gl.uniformMatrix4fv(l.mvp,false,new Float32Array(this._vp));gl.uniform4f(l.color,0.22,0.72,0.45,1);gl.uniform1f(l.lit,0);gl.uniform1f(l.point,1);
      gl.lineWidth(4);gl.drawArrays(gl.LINE_STRIP,0,points.length);
      const elapsed=((Date.now()-this._routeStarted)%Math.max(1400,points.length*850))/Math.max(1400,points.length*850);
      const scaled=elapsed*Math.max(1,points.length-1),index=Math.min(points.length-1,Math.floor(scaled)),next=Math.min(points.length-1,index+1),t=scaled-index;
      const marker=[points[index][0]+(points[next][0]-points[index][0])*t,points[index][1]+0.35,points[index][2]+(points[next][2]-points[index][2])*t];
      gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(marker),gl.DYNAMIC_DRAW);gl.uniform4f(l.color,0.94,0.13,0.18,1);gl.uniform1f(l.point,13*this._dpr);gl.drawArrays(gl.POINTS,0,1);
      gl.enableVertexAttribArray(l.normal);
    },
    nodePoint(n){
      const x=Number(n.x),z=Number(n.y),floor=Number(n.floor)===2?7.95:0.75;
      // 新路线直接使用与 Web 3D 地图一致的 three-world x/z 坐标；兼容旧版 1000×760 数据。
      if(Number.isFinite(x)&&Number.isFinite(z)&&Math.abs(x)<=40&&Math.abs(z)<=40)return[x,floor,z];
      return [((Number.isFinite(x)?x:500)/10-50)*0.42,floor,((Number.isFinite(z)?z:380)/7.6-50)*0.32];
    },
    setFloor(e){this.setData({floor:Number(e.currentTarget.dataset.f)});},
    replayRoute(){this._routeStarted=Date.now();},
    onStoreTap(e){this.triggerEvent('storetap',{store:e.currentTarget.dataset.store});},
    onTouchStart(e){const t=e.touches&&e.touches[0];if(!t)return;this._touch={x:t.x,y:t.y,clientX:t.clientX,clientY:t.clientY,moved:false};},
    onTouchMove(e){
      const t=e.touches&&e.touches[0],last=this._touch;if(!t||!last)return;
      const dx=t.x-last.x,dy=t.y-last.y;if(Math.abs(dx)+Math.abs(dy)>2)last.moved=true;
      this._yaw-=dx*0.012;this._pitch=Math.max(0.12,Math.min(0.92,this._pitch+dy*0.008));last.x=t.x;last.y=t.y;
    },
    onTouchEnd(e){
      const last=this._touch;if(!last||last.moved){this._touch=null;return;}
      const t=e.changedTouches&&e.changedTouches[0];const x=t&&t.x!=null?t.x:(last.clientX-this._left),y=t&&t.y!=null?t.y:(last.clientY-this._top);
      let best=null,dist=42;this._projected.forEach(p=>{if(p.z<-1||p.z>1)return;const d=Math.hypot(p.x-x,p.y-y);if(d<dist){dist=d;best=p.store;}});
      if(best)this.triggerEvent('storetap',{store:best});this._touch=null;
    }
  }
});
