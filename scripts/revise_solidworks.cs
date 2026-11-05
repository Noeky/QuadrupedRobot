using System;
using System.IO;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

public static class RobotRevision {
    static ISldWorks app;
    static string root;
    static IModelDoc2 model;
    static IMathTransform sketchTransform;
    static int axis;
    static bool reverse;
    static double offset;
    static List<string> assemblyRows=new List<string>();
    static IFeature BasePlane(int a) {
        int i=0;for(IFeature f=model.FirstFeature() as IFeature;f!=null;f=f.GetNextFeature() as IFeature)
            if(f.GetTypeName2()=="RefPlane") {if(i++==(a==2?0:a==1?1:2))return f;}
        throw new Exception("No base plane");
    }
    static void Sketch(int a,double at,string name) {
        axis=a;model.ClearSelection2(true);var plane=BasePlane(a);
        plane.Select2(false,0);model.SketchManager.InsertSketch(true);
        var sk=model.SketchManager.ActiveSketch as ISketch;
        sketchTransform=sk.ModelToSketchTransform;
        var inv=sketchTransform.Inverse() as IMathTransform;
        var v=((IMathUtility)app.GetMathUtility()).CreateVector(new double[]{0,0,1}) as IMathVector;
        var xyz=((IMathVector)v.MultiplyTransform(inv)).ArrayData as double[];
        reverse=xyz[a]<0;offset=at*(reverse?-1:1)/1000;
        model.SketchManager.AddToDB=true;model.SketchManager.DisplayWhenAdded=false;
    }
    static double[] P(double u,double v) {
        double[] p=axis==2?new[]{u,v,0.0}:axis==1?new[]{u,0.0,v}:new[]{0.0,u,v};
        var m=((IMathUtility)app.GetMathUtility()).CreatePoint(Array.ConvertAll(p,x=>x/1000)) as IMathPoint;
        return ((IMathPoint)m.MultiplyTransform(sketchTransform)).ArrayData as double[];
    }
    static void Poly(double[][] points) {
        for(int i=0;i<points.Length;i++){var p=P(points[i][0],points[i][1]);var q=P(points[(i+1)%points.Length][0],points[(i+1)%points.Length][1]);
            model.SketchManager.CreateLine(p[0],p[1],0,q[0],q[1],0);}
    }
    static void Rect(double x,double y,double w,double h) {Poly(new[]{new[]{x-w/2,y-h/2},new[]{x+w/2,y-h/2},new[]{x+w/2,y+h/2},new[]{x-w/2,y+h/2}});}
    static void Circle(double x,double y,double r){var p=P(x,y);model.SketchManager.CreateCircleByRadius(p[0],p[1],0,r/1000);}
    static IFeature Finish(double depth,bool cut,string name) {
        model.SketchManager.AddToDB=false;model.SketchManager.DisplayWhenAdded=true;
        var sk=model.SketchManager.ActiveSketch as ISketch;var f=sk as IFeature;
        model.SketchManager.InsertSketch(true);model.ClearSelection2(true);f.Select2(false,0);
        IFeature made=cut?model.FeatureManager.FeatureCut3(true,false,!reverse,0,0,depth/1000,0,false,false,false,false,0,0,false,false,false,false,false,true,true,false,false,false,3,Math.Abs(offset),offset<0):
            model.FeatureManager.FeatureExtrusion2(true,false,reverse,0,0,depth/1000,0,false,false,false,false,0,0,false,false,false,false,true,true,true,3,Math.Abs(offset),offset<0);
        if(made==null)throw new Exception("Feature failed: "+name);made.Name=name;
        model.ClearSelection2(true);return made;
    }
    static void Box(int a,double at,double x,double y,double w,double h,double d,string name){Sketch(a,at,name);Rect(x,y,w,h);Finish(d,false,name);}
    static void Hole(int a,double at,double x,double y,double diameter,double depth,string name){Sketch(a,at,name);Circle(x,y,diameter/2);Finish(depth,true,name);}
    static void New(string name){string t=app.GetDocumentTemplate(1,"",0,0,0);model=app.NewDocument(t,0,0,0) as IModelDoc2;if(model==null)throw new Exception("New part");}
    static void Complete(string name){model.EditRebuild3();model.ShowNamedView2("",7);model.ViewZoomtofit2();Save(model,Path.Combine(root,"cad/current/parts",name+".SLDPRT"));Save(model,Path.Combine(root,"cad/current/step",name+".step"));app.CloseDoc(model.GetTitle());}
    static double[] Along(double x,double y,double u,double v,double a,double b){return new[]{x+u*a-v*b,y+v*a+u*b};}
    static void Bar(double x,double y,double u,double v,double length,double width,double at,double depth,string name) {
        Sketch(2,at,name);Poly(new[]{Along(x,y,u,v,0,-width/2),Along(x,y,u,v,length,-width/2),Along(x,y,u,v,length,width/2),Along(x,y,u,v,0,width/2)});Finish(depth,false,name);
        Sketch(2,at,name);Circle(x,y,width/2);Finish(depth,false,name+"_root");
        Sketch(2,at,name);Circle(x+u*length,y+v*length,width/2);Finish(depth,false,name+"_tip");
    }
    static void Pocket(double u,double v,double at,double depth,string name,bool cut) {
        // R3: gentle taper and a larger rounded tip, with no pinched root neck.
        double radius=cut?4.2:3.8,tip=cut?16.15:17.0,tipRadius=cut?2.5:1.35;
        Sketch(2,at,name);Poly(new[]{Along(0,0,u,v,0,-radius),Along(0,0,u,v,tip,-tipRadius),Along(0,0,u,v,tip,tipRadius),Along(0,0,u,v,0,radius)});Finish(depth,cut,name);
        Sketch(2,at,name);Circle(0,0,radius);Finish(depth,cut,name+"_root");
        Sketch(2,at,name);Circle(u*tip,v*tip,tipRadius);Finish(depth,cut,name+"_tip");
    }
    static void Fasteners(double u,double v,double at,double depth) {
        Sketch(2,at,"Retainer_holes");foreach(double side in new[]{-7.0,7.0}){var p=Along(0,0,u,v,8,side);Circle(p[0],p[1],1.25);}Finish(depth,true,"M2_clearance_2p5_pitch14");
    }
    static void Leg(string name,double u,double v,double length,bool thigh) {
        New(name);double d=thigh?9.85:5.5;
        Bar(0,0,u,v,length,20,0,d,"Leg_plate");
        Pocket(u,v,-.01,2.21,"Horn_slot_R3_gentle_taper_tipR2p5",true);
        Sketch(2,-.01,"Raised_root_relief");Poly(new[]{Along(0,0,u,v,0,-4),Along(0,0,u,v,7,-4),Along(0,0,u,v,7,4),Along(0,0,u,v,0,4)});Finish(3.31,true,"Horn_raised_root_relief_3p3");
        Hole(2,-.1,0,0,8.0,d+.2,"Horn_boss_clearance_8");
        Fasteners(u,v,-.1,d+.2);
        if(thigh){double x=u*length-5.65,y=v*length;
            Box(2,7.35,x,y,38,22,2.5,"Knee_servo_mount");
            Sketch(2,-.1,"Window");Rect(x,y,24,13.2);Finish(d+.2,true,"Servo_window_24x13p2");
            Sketch(2,-.1,"Ear_clearance");Rect(x,y,33.3,13.2);Finish(7.35,true,"Ear_band_clearance");
            Sketch(2,-.1,"Ear_slots");foreach(double dx in new[]{-13.85,13.85})Rect(x+dx,y,3.4,2.5);Finish(d+.2,true,"Mount_slots_3p4x2p5");
        }
        Complete(name);
    }
    static void Retainer(string name,double u,double v) {
        New(name);Bar(0,0,u,v,20,20,-2,2,"Retainer_plate_2mm");
        Pocket(u,v,0,.15,"Horn_contact_pad_0p15",false);
        Hole(2,-2.1,0,0,8,2.5,"Boss_clearance_8");Fasteners(u,v,-2.1,2.5);Complete(name);
    }
    static void Body() {
        New("body");Box(2,0,0,0,120,80,3,"Deck_120x80x3");
        foreach(double hx in new[]{-43.0,43.0})foreach(double sy in new[]{-1.0,1.0}) {
            double x=hx-5.65,y=sy*44.5;
            foreach(double dx in new[]{-14.8,14.8})Box(2,3,x+dx,sy*40.5,8.4,9.4,7.5,"Frame_rib");
            foreach(double dx in new[]{-15.5,15.5})Box(2,10.5,x+dx,y,7,2.5,17,"Mount_upright");
            Box(2,7.5,x,y,38,2.5,3.4,"Mount_lower_beam");Box(2,24.1,x,y,38,2.5,3.4,"Mount_upper_beam");
            Sketch(1,y-2,"Ear_slot");foreach(double dx in new[]{-13.85,13.85})Rect(x+dx,17.5,3.4,2.5);Finish(4,true,"Servo_ear_adjustable_slots");
        }
        Sketch(2,-.1,"Deck_mounting");foreach(double x in new[]{-25.0,25.0})foreach(double y in new[]{-28.0,28.0})Circle(x,y,1.7);
        foreach(double y in new[]{-20.0,20.0})Circle(52,y,1.7);Finish(3.2,true,"M3_deck_mounting_holes");
        Sketch(2,-.1,"PCB_screw_access");foreach(double x in new[]{-24.3,24.3})foreach(double y in new[]{-19.5,19.5})Rect(x,y,3.8,2.6);Finish(3.2,true,"PCB_screw_access");
        Complete("body");
    }
    static void BoardMount() {
        New("board_mount");Box(2,0,0,0,68,64,3,"Board_mount_base");
        Sketch(2,-.1,"Open_bottom");Rect(0,0,39,29);Finish(3.2,true,"Solder_and_connector_opening");
        Sketch(2,-.1,"PCB_holes");foreach(double x in new[]{-24.3,24.3})foreach(double y in new[]{-19.5,19.5})Rect(x,y,3.8,2.6);Finish(3.2,true,"PCB_M2_slots_centres48p6x39");
        Sketch(2,-.1,"Deck_attachment");foreach(double x in new[]{-25.0,25.0})foreach(double y in new[]{-28.0,28.0})Circle(x,y,1.7);
        Finish(3.2,true,"Deck_attachment_M3");Complete("board_mount");
    }
    static void Sensor() {
        New("ultrasonic_bracket");Box(2,0,0,0,18,54,3,"Foot");
        // x is fore/aft; rear of module faces the open window. Transducers point +X.
        Box(2,3,-6,0,3,54,51,"Upright");
        Sketch(0,-8,"Electronics_clearance");Rect(0,36,34,23);Finish(5,true,"Rear_components_open_window");
        Sketch(0,-8,"Sensor_slots");foreach(double y in new[]{-21.0,21.0})foreach(double z in new[]{27.5,44.5})Rect(y,z,4.2,3.6);
        Finish(5,true,"Sensor_M2_slots_centres42x17");
        foreach(double y in new[]{-26.0,24.0}){Sketch(1,y,"Gusset");Poly(new[]{new[]{-4.5,3.0},new[]{8.0,3.0},new[]{-4.5,16.0}});Finish(2,false,"Side_gusset");}
        Sketch(2,-.1,"Foot_holes");foreach(double y in new[]{-20.0,20.0})Circle(0,y,1.7);Finish(3.2,true,"Foot_M3_holes_pitch40");
        Complete("ultrasonic_bracket");
    }
    static void CorrectHorn() {
        model=Open(Path.Combine(root,"hardware/reference/servo_horn.SLDPRT"));
        double cx=38.9683704593794,cy=-.000039981634278,z=27.318082558793;
        double[] old={8.8,11.3,13.8,16.3};
        Sketch(2,z,"Fill_old_holes");foreach(double x in old)Circle(cx+x,cy,.5);Finish(2,false,"Fill_old_four_holes");
        Sketch(2,z-.01,"Measured_holes");foreach(double gap in new[]{6.78,9.16,11.70,14.22})Circle(cx+gap+3,cy,.5);Finish(2.02,true,"Measured_rear4_holes_socketID5");
        model.EditRebuild3();Save(model,Path.Combine(root,"hardware/reference/servo_horn_measured.SLDPRT"));Save(model,Path.Combine(root,"hardware/reference/servo_horn_measured.step"));app.CloseDoc(model.GetTitle());
    }
    static double[,] Mul(double[,] a,double[,] b){var c=new double[3,3];for(int i=0;i<3;i++)for(int j=0;j<3;j++)for(int k=0;k<3;k++)c[i,j]+=a[i,k]*b[k,j];return c;}
    static double[,] Rx(double a){double c=Math.Cos(a),s=Math.Sin(a);return new double[,]{{1,0,0},{0,c,-s},{0,s,c}};}
    static double[,] Rz(double a){double c=Math.Cos(a),s=Math.Sin(a);return new double[,]{{c,-s,0},{s,c,0},{0,0,1}};}
    static double[] Vec(double[,] r,double[] v){var o=new double[3];for(int i=0;i<3;i++)for(int j=0;j<3;j++)o[i]+=r[i,j]*v[j];return o;}
    static void AddPart(IAssemblyDoc assy,IModelDoc2 doc,string file,string name,double[,] r,double[] origin,double[] localOrigin) {
        file=Path.GetFullPath(file);
        var part=Open(file);int error=0;var active=app.ActivateDoc3(doc.GetTitle(),false,0,ref error) as IModelDoc2;
        Console.WriteLine("Insert "+name+" active="+(active==null?"null":active.GetTitle())+" error="+error+" part="+part.GetPathName());
        IComponent2 c=assy.AddComponent5(file,0,"",false,"",0,0,0) as IComponent2;
        if(c==null)throw new Exception("Cannot add "+file);
        var p=Vec(r,localOrigin);double[] d={r[0,0],r[1,0],r[2,0],r[0,1],r[1,1],r[2,1],r[0,2],r[1,2],r[2,2],(origin[0]-p[0])/1000,(origin[1]-p[1])/1000,(origin[2]-p[2])/1000,1,0,0,0};
        c.Transform2=((IMathUtility)app.GetMathUtility()).CreateTransform(d) as MathTransform;c.Name2=name;
        var actual=c.Transform2.ArrayData as double[];for(int i=0;i<13;i++)if(Math.Abs(actual[i]-d[i])>1e-8)throw new Exception("Component transform not applied: "+name);
        assemblyRows.Add(name+"\t"+file+"\t"+String.Join(",",Array.ConvertAll(d,n=>n.ToString("R",System.Globalization.CultureInfo.InvariantCulture))));
        doc.ClearSelection2(true);c.Select4(false,null,false);assy.FixComponent();doc.ClearSelection2(true);
    }
    static void Assembly() {
        string t=app.GetDocumentTemplate(2,"",0,0,0);IModelDoc2 doc=app.NewDocument(t,0,0,0) as IModelDoc2;IAssemblyDoc a=doc as IAssemblyDoc;
        string p=Path.Combine(root,"cad/current/parts"),h=Path.Combine(root,"hardware/reference");
        double[,] identity=Rx(0);var zero=new double[]{0,0,0};
        AddPart(a,doc,Path.Combine(p,"body.SLDPRT"),"Body",Rx(Math.PI),new double[]{0,0,17.5},zero);
        AddPart(a,doc,Path.Combine(p,"board_mount.SLDPRT"),"PCB_mount",identity,new double[]{0,0,17.5},zero);
        AddPart(a,doc,Path.Combine(p,"ultrasonic_bracket.SLDPRT"),"HC_SR04_bracket",identity,new double[]{52,0,17.5},zero);
        foreach(double x in new[]{-43.0,43.0})foreach(int sign in new[]{-1,1}) {
            string side=sign>0?"left":"right",prefix=(x>0?"front_":"rear_")+side;
            var hip=new double[]{x,sign*54,0};var knee=new double[]{x+20,sign*72,-40*Math.Sqrt(3)/2};
            var r=Rx(-sign*Math.PI/2);
            AddPart(a,doc,Path.Combine(p,"thigh_"+side+".SLDPRT"),prefix+"_thigh",r,hip,zero);
            var rs=sign>0?r:Mul(r,Rz(2*Math.PI/3));
            AddPart(a,doc,Path.Combine(p,"shin.SLDPRT"),prefix+"_shin",rs,knee,zero);
            AddPart(a,doc,Path.Combine(p,"hip_horn_clamp.SLDPRT"),prefix+"_hip_clamp",sign>0?r:Mul(r,Rz(-2*Math.PI/3)),hip,zero);
            AddPart(a,doc,Path.Combine(p,"knee_horn_clamp.SLDPRT"),prefix+"_knee_clamp",rs,knee,zero);
            foreach(int joint in new[]{0,1}){
                var at=joint==0?hip:knee;string j=joint==0?"hip":"knee";
                AddPart(a,doc,Path.Combine(h,"servo_sg90.SLDPRT"),prefix+"_"+j+"_servo",sign>0?identity:Rx(Math.PI),at,new double[]{16.8,31.05,6.25});
                double angle=joint==0?Math.PI/3:2*Math.PI/3;
                var hornAt=new double[]{at[0],at[1]+sign*.2,at[2]};
                AddPart(a,doc,Path.Combine(h,"servo_horn_measured.SLDPRT"),prefix+"_"+j+"_horn",Mul(r,Rz(sign*angle)),hornAt,new double[]{38.9683704593794,-.000039981634278,27.318082558793});
            }
        }
        doc.EditRebuild3();doc.ShowNamedView2("",7);doc.ViewZoomtofit2();Save(doc,Path.Combine(root,"cad/current/robot.SLDASM"));Save(doc,Path.Combine(root,"cad/current/robot.step"));File.WriteAllLines(Path.Combine(root,"cad/current/assembly_manifest.tsv"),assemblyRows);app.CloseDoc(doc.GetTitle());
        int e=0,w=0;var reopened=app.OpenDoc6(Path.GetFullPath(Path.Combine(root,"cad/current/robot.SLDASM")),2,1,"",ref e,ref w) as IModelDoc2;
        if(reopened==null||e!=0)throw new Exception("Assembly reopen error "+e);
        object[] cs=((IAssemblyDoc)reopened).GetComponents(false) as object[];
        if(cs==null||cs.Length!=35)throw new Exception("Expected 35 assembly components");
        foreach(IComponent2 c in cs)if(c.GetModelDoc2()==null)throw new Exception("Unresolved "+c.Name2);
        Console.WriteLine("Native assembly reopened: 35 resolved components");app.CloseDoc(reopened.GetTitle());
    }
    static void CloseOwned(){object[] docs=app.GetDocuments() as object[];if(docs!=null)foreach(IModelDoc2 d in docs){string p=d.GetPathName();if(p.StartsWith(Path.Combine(root,"cad\\current"),StringComparison.OrdinalIgnoreCase)||p.StartsWith(Path.Combine(root,"hardware\\reference"),StringComparison.OrdinalIgnoreCase))app.CloseDoc(d.GetTitle());}}
    static void Audit(){CloseOwned();var rows=new List<string>();foreach(string file in Directory.GetFiles(Path.Combine(root,"cad/current/parts"),"*.SLDPRT")){
        if(Path.GetFileNameWithoutExtension(file)=="pilot"||Path.GetFileName(file).StartsWith("~$"))continue;model=Open(file);model.EditRebuild3();int features=0;
        object[] bodies=((IPartDoc)model).GetBodies2(0,false) as object[];if(bodies==null||bodies.Length!=1)throw new Exception("Not one solid "+file);
        for(IFeature f=model.FirstFeature() as IFeature;f!=null;f=f.GetNextFeature() as IFeature){bool warning=false;int code=f.GetErrorCode2(out warning);if(code!=0&&!warning)throw new Exception("Feature error "+f.Name+" "+code);features++;}
        rows.Add(Path.GetFileName(file)+"\t1 solid\t"+features+" features\t0 feature errors");app.CloseDoc(model.GetTitle());
    }
        object[] deps=app.GetDocumentDependencies2(Path.GetFullPath(Path.Combine(root,"cad/current/robot.SLDASM")),true,false,false) as object[];
        if(deps==null)throw new Exception("No assembly references");for(int i=1;i<deps.Length;i+=2){string p=(string)deps[i];if(!File.Exists(p)||!Path.GetFullPath(p).StartsWith(root+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase))throw new Exception("External or missing dependency "+p);}
        File.WriteAllLines(Path.Combine(root,"cad/current/native_validation.tsv"),rows);Console.WriteLine(String.Join("\n",rows));Console.WriteLine("All assembly references remain in workspace");
    }
    static IFeature FindFeature(IModelDoc2 d,string name){for(IFeature f=d.FirstFeature() as IFeature;f!=null;f=f.GetNextFeature() as IFeature)if(f.Name==name)return f;return null;}
    static ISketch FeatureSketch(IModelDoc2 d,string name) {
        var f=FindFeature(d,name);if(f==null)throw new Exception("Missing feature: "+name);
        for(IFeature child=f.GetFirstSubFeature() as IFeature;child!=null;child=child.GetNextSubFeature() as IFeature){var sk=child.GetSpecificFeature2() as ISketch;if(sk!=null)return sk;}
        throw new Exception("Missing absorbed sketch: "+name);
    }
    static double[] CircleInfo(IModelDoc2 d,string name) {
        object[] segments=FeatureSketch(d,name).GetSketchSegments() as object[];
        foreach(object value in segments){var arc=value as ISketchArc;if(arc!=null){var p=arc.GetCenterPoint2() as ISketchPoint;return new[]{arc.GetRadius()*1000,Math.Sqrt(p.X*p.X+p.Y*p.Y+p.Z*p.Z)*1000};}}
        throw new Exception("Missing circle: "+name);
    }
    static long Identity(object item){IntPtr p=Marshal.GetIUnknownForObject(item);long id=p.ToInt64();Marshal.Release(p);return id;}
    static void VerifyPropagation() {
        var existing=new HashSet<long>();object[] before=app.GetDocuments() as object[];if(before!=null)foreach(object d in before)existing.Add(Identity(d));
        var previous=app.ActiveDoc as IModelDoc2;string title=previous==null?"":previous.GetTitle();var rows=new List<string>();
        try {
            foreach(string name in new[]{"thigh_left","thigh_right","shin"}){
                var d=Open(Path.GetFullPath(Path.Combine(root,"cad/current/parts",name+".SLDPRT")));
                string feature="Horn_slot_R3_gentle_taper_tipR2p5";
                var rc=CircleInfo(d,feature+"_root");var tc=CircleInfo(d,feature+"_tip");
                if(Math.Abs(rc[0]-4.2)>.001||Math.Abs(tc[0]-2.5)>.001||Math.Abs(tc[1]-16.15)>.001)throw new Exception("Slot dimensions differ: "+name);
                var points=new List<ISketchPoint>();object[] segs=FeatureSketch(d,feature).GetSketchSegments() as object[];
                foreach(object s in segs){var line=s as ISketchLine;if(line!=null)points.Add(line.GetStartPoint2() as ISketchPoint);}
                var near=new List<ISketchPoint>();var far=new List<ISketchPoint>();foreach(var p in points){if(Math.Sqrt(p.X*p.X+p.Y*p.Y)<.01)near.Add(p);else far.Add(p);}
                if(near.Count!=2||far.Count!=2)throw new Exception("Unexpected tapered contour "+name);
                double width0=Math.Sqrt(Math.Pow(near[0].X-near[1].X,2)+Math.Pow(near[0].Y-near[1].Y,2))*1000;
                double width1=Math.Sqrt(Math.Pow(far[0].X-far[1].X,2)+Math.Pow(far[0].Y-far[1].Y,2))*1000;
                if(Math.Abs(width0-8.4)>.001||Math.Abs(width1-5)>.001)throw new Exception("Unexpected widths "+name);
                if(FindFeature(d,"Horn_pocket_Lplus1_Dplus0p6")!=null)throw new Exception("Legacy horn cut remains "+name);
                rows.Add(name+"\tR3 tapered slot\troot width="+width0.ToString("F3")+" mm\ttip diameter="+width1.ToString("F3")+" mm\tend="+(tc[0]+tc[1]).ToString("F3")+" mm\tPASS");
            }
            foreach(string name in new[]{"hip_horn_clamp","knee_horn_clamp"}){var d=Open(Path.GetFullPath(Path.Combine(root,"cad/current/parts",name+".SLDPRT")));var c=CircleInfo(d,"Horn_contact_pad_0p15_tip");if(Math.Abs(c[0]-1.35)>.001||Math.Abs(c[1]-17)>.001)throw new Exception("Old retainer pad "+name);rows.Add(name+"\tR3 contact pad\tend="+(c[0]+c[1]).ToString("F3")+" mm\tPASS");}
            int error=0,warning=0;var assy=app.OpenDoc6(Path.GetFullPath(Path.Combine(root,"cad/current/robot.SLDASM")),2,1,"",ref error,ref warning) as IModelDoc2;if(assy==null||error!=0)throw new Exception("Assembly open error");
            var expected=new Dictionary<string,int>{{"body",1},{"board_mount",1},{"ultrasonic_bracket",1},{"thigh_left",2},{"thigh_right",2},{"shin",4},{"hip_horn_clamp",4},{"knee_horn_clamp",4},{"servo_sg90",8},{"servo_horn_measured",8}};
            var poses=new List<Tuple<string,double[]>>();foreach(string line in File.ReadAllLines(Path.Combine(root,"cad/current/assembly_manifest.tsv"))){string[] fields=line.Split('\t');poses.Add(Tuple.Create(Path.GetFullPath(fields[1]),Array.ConvertAll(fields[2].Split(','),x=>Double.Parse(x,System.Globalization.CultureInfo.InvariantCulture))));}
            var counts=new Dictionary<string,int>();object[] cs=((IAssemblyDoc)assy).GetComponents(false) as object[];
            foreach(IComponent2 c in cs){var d=c.GetModelDoc2() as IModelDoc2;if(d==null)throw new Exception("Unresolved "+c.Name2);string p=Path.GetFullPath(d.GetPathName());string name=Path.GetFileNameWithoutExtension(p);string folder=(name=="servo_sg90"||name=="servo_horn_measured")?"hardware/reference":"cad/current/parts";if(!String.Equals(p,Path.GetFullPath(Path.Combine(root,folder,name+".SLDPRT")),StringComparison.OrdinalIgnoreCase))throw new Exception("Old reference "+p);if(!counts.ContainsKey(name))counts[name]=0;counts[name]++;
                var t=c.Transform2.ArrayData as double[];int match=-1;for(int i=0;i<poses.Count;i++){if(!String.Equals(p,poses[i].Item1,StringComparison.OrdinalIgnoreCase))continue;bool same=true;for(int j=0;j<13;j++)if(Math.Abs(t[j]-poses[i].Item2[j])>1e-8)same=false;if(same){match=i;break;}}if(match<0)throw new Exception("Assembly pose differs from checked manifest: "+c.Name2);poses.RemoveAt(match);
            }
            foreach(var kv in expected){if(!counts.ContainsKey(kv.Key)||counts[kv.Key]!=kv.Value)throw new Exception("Wrong count "+kv.Key);rows.Add("assembly\t"+kv.Key+"\t"+kv.Value+" current native instances\tPASS");}
            if(cs.Length!=35||poses.Count!=0)throw new Exception("Assembly count differs");rows.Add("assembly\t35 component transforms match checked manifest\tPASS");File.WriteAllLines(Path.Combine(root,"cad/current/fit_propagation_native.tsv"),rows);Console.WriteLine(String.Join("\n",rows));
        } finally {object[] after=app.GetDocuments() as object[];if(after!=null)foreach(IModelDoc2 d in after)if(!existing.Contains(Identity(d)))app.CloseDoc(d.GetTitle());if(title!=""){int e=0;app.ActivateDoc2(title,false,ref e);}}
    }
    static void Save(IModelDoc2 m,string file) {
        file=Path.GetFullPath(file);
        Directory.CreateDirectory(Path.GetDirectoryName(file));int e=0,w=0;
        bool same=String.Equals(m.GetPathName(),file,StringComparison.OrdinalIgnoreCase);
        bool ok=same?m.Save3(1,ref e,ref w):m.Extension.SaveAs(file,0,1,null,ref e,ref w);
        if(!ok||e!=0)throw new Exception("Save failed "+file+" "+e);
    }
    static IModelDoc2 Open(string file) {
        int e=0,w=0;var m=app.OpenDoc6(file,1,1,"",ref e,ref w) as IModelDoc2;
        if(m==null||e!=0)throw new Exception("Open failed "+file+" "+e);return m;
    }
    static void Inspect(string source,string name) {
        string target=Path.Combine(root,"hardware/reference",name+".SLDPRT");
        Directory.CreateDirectory(Path.GetDirectoryName(target));
        if(!File.Exists(target))File.Copy(source,target);
        var m=Open(target);Console.WriteLine(name+" "+m.GetTitle());
        var bs=((IPartDoc)m).GetBodies2(0,false) as object[];
        if(bs!=null)foreach(IBody2 b in bs) {
            var box=b.GetBodyBox() as double[];Console.WriteLine("bbox mm: "+String.Join(",",Array.ConvertAll(box,x=>x*1000)));
            object[] fs=b.GetFaces() as object[];
            foreach(IFace2 f in fs){ISurface s=f.GetSurface() as ISurface;if(s.IsCylinder())Console.WriteLine("cylinder: "+String.Join(",",(double[])s.CylinderParams));}
        }
        Save(m,Path.Combine(root,"hardware/reference",name+".step"));app.CloseDoc(m.GetTitle());
    }
    public static void Run(string directory,string action) {
        root=directory;app=(ISldWorks)Marshal.GetActiveObject("SldWorks.Application");
        if(action=="Audit"){Audit();return;}
        if(action=="VerifyPropagation"){VerifyPropagation();return;}
        if(action=="UpdateHornSlots"){CloseOwned();Leg("thigh_left",.5,Math.Sqrt(3)/2,40,true);Console.WriteLine("R3 left thigh");Leg("thigh_right",.5,-Math.Sqrt(3)/2,40,true);Console.WriteLine("R3 right thigh");Leg("shin",-.5,Math.Sqrt(3)/2,45,false);Console.WriteLine("R3 shin");Retainer("hip_horn_clamp",.5,Math.Sqrt(3)/2);Retainer("knee_horn_clamp",-.5,Math.Sqrt(3)/2);Console.WriteLine("R3 retainers");int e=0,w=0;var d=app.OpenDoc6(Path.GetFullPath(Path.Combine(root,"cad/current/robot.SLDASM")),2,1,"",ref e,ref w) as IModelDoc2;if(d==null||e!=0)throw new Exception("Assembly refresh failed");d.ForceRebuild3(false);Save(d,Path.Combine(root,"cad/current/robot.SLDASM"));Save(d,Path.Combine(root,"cad/current/robot.step"));app.CloseDoc(d.GetTitle());Audit();return;}
        if(action=="UpdateBoard") {CloseOwned();BoardMount();int e=0,w=0;var d=app.OpenDoc6(Path.GetFullPath(Path.Combine(root,"cad/current/robot.SLDASM")),2,1,"",ref e,ref w) as IModelDoc2;if(d==null||e!=0)throw new Exception("Assembly refresh failed");d.ForceRebuild3(false);Save(d,Path.Combine(root,"cad/current/robot.SLDASM"));Save(d,Path.Combine(root,"cad/current/robot.step"));app.CloseDoc(d.GetTitle());Audit();return;}
        if(action=="Show"){int e=0,w=0;var d=app.OpenDoc6(Path.GetFullPath(Path.Combine(root,"cad/current/robot.SLDASM")),2,1,"",ref e,ref w) as IModelDoc2;if(d==null||e!=0)throw new Exception("Cannot show assembly");app.Visible=true;d.ShowNamedView2("",7);d.ViewZoomtofit2();return;}
        if(action=="Assembly"){Assembly();return;}
        if(action=="Build") {
            CloseOwned();
            CorrectHorn();Console.WriteLine("Corrected horn");
            Leg("thigh_left",.5,Math.Sqrt(3)/2,40,true);Console.WriteLine("Left thigh");
            Leg("thigh_right",.5,-Math.Sqrt(3)/2,40,true);Console.WriteLine("Right thigh");
            Leg("shin",-.5,Math.Sqrt(3)/2,45,false);Console.WriteLine("Shin");
            Retainer("hip_horn_clamp",.5,Math.Sqrt(3)/2);Retainer("knee_horn_clamp",-.5,Math.Sqrt(3)/2);Console.WriteLine("Retainers");
            Body();Console.WriteLine("Body");BoardMount();Console.WriteLine("Board mount");Sensor();Console.WriteLine("Ultrasonic bracket");return;
        }
        if(action=="Inspect") {
            Console.WriteLine("SW "+app.RevisionNumber());
            Inspect(@"D:\xwechat_files\wxid_oi5v765qdoxo22_c7bb\msg\file\2026-10\5孔半臂(3).SLDPRT","servo_horn");
            Inspect(@"D:\xwechat_files\wxid_oi5v765qdoxo22_c7bb\msg\file\2026-10\蓝色舵机sg90(1).SLDPRT","servo_sg90");
        }
    }
}


