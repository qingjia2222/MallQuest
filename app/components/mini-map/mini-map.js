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
  data:{webglReady:false,webglFailed:false,floorCount:2,segs:[],labels:[]},
  observers:{
    'stores,route,routeNodes,activeId,floor'(){ if(this._gl){this._routeStarted=Date.now();this.render();this.scheduleLabels();} }
  },
  lifetimes:{
    ready(){this.initWebGL();},
    detached(){this._destroyed=true;if(this._labelTimer)clearTimeout(this._labelTimer);if(this._canvas&&this._raf)this._canvas.cancelAnimationFrame(this._raf);}
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
          this._yaw=-0.64;this._pitch=0.82;this._routeStarted=Date.now();
          this.createProgram();this.createGeometry();
          gl.enable(gl.DEPTH_TEST);gl.enable(gl.BLEND);gl.blendFunc(gl.SRC_ALPHA,gl.ONE_MINUS_SRC_ALPHA);
          this.setData({webglReady:true,webglFailed:false});this.loop();this.scheduleLabels();
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
    floorY(floor){return Number(floor)===2?8.5:1.25;},
    storePoint(s){
      const x=Number(s.map_x),z=Number(s.map_z);
      if(Number.isFinite(x)&&Number.isFinite(z))return[x,this.floorY(s.floor),z];
      return[(Number(s.pos_x||50)-50)*0.42,this.floorY(s.floor),(Number(s.pos_y||50)-50)*0.32];
    },
    projectLabel(key,name,point,facility){
      const clip=transform(this._vp,point);
      this._projectedLabels.push({key,name,x:(clip[0]+1)*this._width/2,y:(1-clip[1])*this._height/2,z:clip[2],facility:Boolean(facility)});
    },
    drawFacilities(floors,all){
      const items=[
        {key:'service_desk_f1',name:'服务台',floor:1,x:-9,z:-1,w:11,d:8,color:[0.34,0.72,0.92,all ? .68 : 1]},
        {key:'waterfall_hall_f1',name:'瀑布厅',floor:1,x:9,z:-1,w:11,d:8,color:[0.30,0.80,0.72,all ? .68 : 1]},
        {key:'children_area_f2',name:'儿童乐园',floor:2,x:-9,z:-1,w:11,d:8,color:[0.55,0.72,0.96,all ? .68 : 1]},
        {key:'food_court_f2',name:'美食广场',floor:2,x:9,z:-1,w:11,d:8,color:[0.96,0.67,0.35,all ? .68 : 1]},
      ];
      items.filter(item=>floors.includes(item.floor)).forEach(item=>{const y=this.floorY(item.floor)+.48;this.drawBox(item.x,y,item.z,item.w/2,.48,item.d/2,item.color);this.projectLabel(item.key,item.name,[item.x,y+1,item.z],true);});
      floors.forEach(floor=>{const y=this.floorY(floor)+.7;this.drawBox(0,y,0,2.6,.7,2.6,[0.18,0.75,0.82,all ? .72 : 1]);this.projectLabel(`elevator_${floor}`,'直梯',[0,y+1.1,0],true);const ex=floor===1?-8:8;this.drawBox(ex,y,-9.5,2.4,.38,1.4,[0.96,0.43,0.34,all ? .74 : 1]);this.projectLabel(`escalator_${floor}`,'扶梯',[ex,y+1,-9.5],true);});
    },
    render(){
      const gl=this._gl;if(!gl)return;
      gl.viewport(0,0,this._canvas.width,this._canvas.height);gl.clearColor(0.969,0.953,0.980,1);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
      const all=!Number(this.data.floor),radius=all?61:52,eye=[Math.sin(this._yaw)*radius,10+this._pitch*32,Math.cos(this._yaw)*radius];
      const targetY=Number(this.data.floor)===2?7:Number(this.data.floor)===1?1:4;
      const view=lookAt(eye,[0,targetY,0],[0,1,0]),proj=perspective(Math.PI/4,this._canvas.width/this._canvas.height,0.1,160);
      this._vp=multiply(proj,view);this._projected=[];this._projectedLabels=[];
      const floors=Number(this.data.floor)?[Number(this.data.floor)]:[1,2];
      gl.depthMask(false);floors.forEach(f=>this.drawBox(0,f===2?7.55:.3,0,29,.42,23,[0.98,0.97,0.94,all ? (f===2 ? .22 : .34) : .96]));gl.depthMask(true);
      this.drawFacilities(floors,all);
      this.visibleStores().forEach(s=>{
        const p=this.storePoint(s),active=s.id===this.data.activeId;
        const width=Math.max(2,Number(s.map_width)||4.5),depth=Math.max(2,Number(s.map_depth)||3.8),color=active?[0.94,0.27,0.31,1]:colorOf(s.category);if(all)color[3]=.76;
        this.drawBox(p[0],p[1]+1.05,p[2],width/2,1.05,depth/2,color);
        const clip=transform(this._vp,[p[0],p[1]+2.3,p[2]]);
        this._projected.push({store:s,x:(clip[0]+1)*this._width/2,y:(1-clip[1])*this._height/2,z:clip[2]});
        this.projectLabel(s.id,s.name,[p[0],p[1]+2.3,p[2]],false);
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
      gl.disable(gl.DEPTH_TEST);gl.lineWidth(5);gl.drawArrays(gl.LINE_STRIP,0,points.length);
      const elapsed=((Date.now()-this._routeStarted)%Math.max(1400,points.length*850))/Math.max(1400,points.length*850);
      const scaled=elapsed*Math.max(1,points.length-1),index=Math.min(points.length-1,Math.floor(scaled)),next=Math.min(points.length-1,index+1),t=scaled-index;
      const marker=[points[index][0]+(points[next][0]-points[index][0])*t,points[index][1]+0.35,points[index][2]+(points[next][2]-points[index][2])*t];
      gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(marker),gl.DYNAMIC_DRAW);gl.uniform4f(l.color,0.94,0.13,0.18,1);gl.uniform1f(l.point,13*this._dpr);gl.drawArrays(gl.POINTS,0,1);
      gl.enable(gl.DEPTH_TEST);gl.enableVertexAttribArray(l.normal);
    },
    nodePoint(n){
      const x=Number(n.x),z=Number(n.y),floor=this.floorY(n.floor)+.35;
      // 新路线直接使用与 Web 3D 地图一致的 three-world x/z 坐标；兼容旧版 1000×760 数据。
      if(Number.isFinite(x)&&Number.isFinite(z)&&Math.abs(x)<=40&&Math.abs(z)<=40)return[x,floor,z];
      return [((Number.isFinite(x)?x:500)/10-50)*0.42,floor,((Number.isFinite(z)?z:380)/7.6-50)*0.32];
    },
    scheduleLabels(){
      if(this._labelTimer)clearTimeout(this._labelTimer);
      this._labelTimer=setTimeout(()=>{
        if(this._destroyed)return;
        const labels=(this._projectedLabels||[]).filter(item=>item.z>=-1&&item.z<=1&&item.x>8&&item.x<this._width-8&&item.y>18&&item.y<this._height-8).map(item=>({...item,x:Math.round(item.x),y:Math.round(item.y)}));
        this.setData({labels});
      },70);
    },
    touchPoint(t){return{x:Number.isFinite(t&&t.x)?t.x:Number.isFinite(t&&t.clientX)?t.clientX-this._left:Number(t&&t.pageX||0)-this._left,y:Number.isFinite(t&&t.y)?t.y:Number.isFinite(t&&t.clientY)?t.clientY-this._top:Number(t&&t.pageY||0)-this._top};},
    setFloor(e){this.setData({floor:Number(e.currentTarget.dataset.f)});},
    replayRoute(){this._routeStarted=Date.now();},
    onStoreTap(e){this.triggerEvent('storetap',{store:e.currentTarget.dataset.store});},
    onTouchStart(e){const t=e.touches&&e.touches[0];if(!t)return;const p=this.touchPoint(t);this._touch={x:p.x,y:p.y,moved:false};},
    onTouchMove(e){
      const t=e.touches&&e.touches[0],last=this._touch;if(!t||!last)return;
      const p=this.touchPoint(t),dx=p.x-last.x,dy=p.y-last.y;if(Math.abs(dx)+Math.abs(dy)>2)last.moved=true;
      this._yaw-=dx*0.012;this._pitch=Math.max(0.05,Math.min(1.45,this._pitch-dy*0.012));last.x=p.x;last.y=p.y;this.scheduleLabels();
    },
    onTouchEnd(e){
      const last=this._touch;if(!last||last.moved){this._touch=null;return;}
      const t=e.changedTouches&&e.changedTouches[0],p=this.touchPoint(t||last),x=p.x,y=p.y;
      let best=null,dist=42;this._projected.forEach(p=>{if(p.z<-1||p.z>1)return;const d=Math.hypot(p.x-x,p.y-y);if(d<dist){dist=d;best=p.store;}});
      if(best)this.triggerEvent('storetap',{store:best});this._touch=null;
    }
  }
});
