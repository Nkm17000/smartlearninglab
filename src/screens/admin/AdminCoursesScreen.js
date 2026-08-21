import React,{useEffect,useState} from 'react';
import {Alert,Text,View} from 'react-native';
import {AppShell,Badge,Button,Card,Empty,ErrorState,Field,Header,Loading,Select} from '../../components/UI';
import {api} from '../../services/api';
import {colors} from '../../theme';

export default function AdminCoursesScreen({openCourse}){
 const [courses,setCourses]=useState(null),[error,setError]=useState(''),[show,setShow]=useState(false),[editing,setEditing]=useState(null);
 const [form,setForm]=useState({name:'',short_description:'',description:'',category:'General',exam:'General',language:'English',level:'Beginner',instructor_name:'Smart Learning Lab',estimated_minutes:'0',video_count:'0',pdf_count:'0',mock_test_count:'0',tags:''});
 const load=()=>{setError('');api.courses().then(x=>setCourses(api.listOf(x))).catch(e=>setError(e.message))}; useEffect(()=>{load()},[]);
 const reset=()=>{setForm({name:'',short_description:'',description:'',category:'General',exam:'General',language:'English',level:'Beginner',instructor_name:'Smart Learning Lab',estimated_minutes:'0',video_count:'0',pdf_count:'0',mock_test_count:'0',tags:''});setEditing(null);setShow(false)};
 const save=async()=>{try{const body={...form,estimated_minutes:Number(form.estimated_minutes)||0,video_count:Number(form.video_count)||0,pdf_count:Number(form.pdf_count)||0,mock_test_count:Number(form.mock_test_count)||0,tags:form.tags.split(',').map(x=>x.trim()).filter(Boolean),is_free:true,is_published:false};if(editing)await api.updateCourse(editing,body);else await api.createCourse(body);reset();load()}catch(e){Alert.alert('Save failed',e.message)}};
 const edit=c=>{setEditing(api.idOf(c));setForm({...form,...c,estimated_minutes:String(c.estimated_minutes||0),video_count:String(c.video_count||0),pdf_count:String(c.pdf_count||0),mock_test_count:String(c.mock_test_count||0),tags:Array.isArray(c.tags)?c.tags.join(', '):(c.tags||'')});setShow(true)};
 const remove=async c=>{try{await api.deleteCourse(api.idOf(c));load()}catch(e){Alert.alert('Delete failed',e.message)}};
 if(error)return <AppShell><Header title="Courses" subtitle="Create, organize and publish complete learning programs."/><ErrorState title="Courses could not load" message={error} onRetry={load}/></AppShell>;
 return <AppShell><Header eyebrow="Content studio" title="Courses" subtitle="Build an Adda-style learning catalog: exam, level, instructor, resources and test series." right={<Button title={show?'Close':'+ New Course'} onPress={()=>show?reset():setShow(true)}/>}/>
 {show&&<Card><Text style={{fontSize:20,fontWeight:'900',color:colors.navy,marginBottom:14}}>{editing?'Edit course':'Create a new course'}</Text>
 <Field label="Course name" value={form.name} onChangeText={v=>setForm({...form,name:v})} placeholder="English Spoken Masterclass"/>
 <Field label="Short description" value={form.short_description} onChangeText={v=>setForm({...form,short_description:v})} placeholder="One-line value proposition"/>
 <Field label="Full description" value={form.description} onChangeText={v=>setForm({...form,description:v})} multiline/>
 <View style={{flexDirection:'row',gap:10,flexWrap:'wrap'}}>{[['Category','category'],['Exam','exam'],['Language','language'],['Instructor','instructor_name']].map(([l,k])=><View key={k} style={{flex:1,minWidth:220}}><Field label={l} value={form[k]} onChangeText={v=>setForm({...form,[k]:v})}/></View>)}</View>
 <Select label="Level" value={form.level} onChange={v=>setForm({...form,level:v})} options={[{value:'Beginner',label:'Beginner'},{value:'Intermediate',label:'Intermediate'},{value:'Advanced',label:'Advanced'}]}/>
 <View style={{flexDirection:'row',gap:10,flexWrap:'wrap'}}>{[['Duration (min)','estimated_minutes'],['Videos','video_count'],['PDFs','pdf_count'],['Mock tests','mock_test_count']].map(([l,k])=><View key={k} style={{flex:1,minWidth:150}}><Field label={l} value={form[k]} onChangeText={v=>setForm({...form,[k]:v})} keyboardType="numeric"/></View>)}</View>
 <Field label="Tags (comma separated)" value={form.tags} onChangeText={v=>setForm({...form,tags:v})} placeholder="grammar, speaking, beginner"/>
 <View style={{flexDirection:'row',gap:8}}><Button title={editing?'Save Changes':'Create Course'} onPress={save} disabled={!form.name.trim()}/><Button title="Cancel" variant="secondary" onPress={reset}/></View></Card>}
 {!courses?<Loading/>:courses.length===0?<Empty title="No courses yet" message="Start by creating your first course." action={<Button title="+ Create Course" onPress={()=>setShow(true)}/>} />:<>
 <View style={{flexDirection:'row',gap:8,marginBottom:10,flexWrap:'wrap'}}><Badge tone="pink">FREE CATALOG</Badge><Badge>{courses.length} courses</Badge><Badge tone="purple">Course → Topics → Lessons → Tests</Badge></View>
 {courses.map(c=><Card key={api.idOf(c)}><View style={{flexDirection:'row',gap:15,alignItems:'center'}}><View style={{width:58,height:58,borderRadius:14,backgroundColor:colors.pinkSoft,alignItems:'center',justifyContent:'center'}}><Text style={{fontSize:27}}>📚</Text></View><View style={{flex:1}}><Text style={{fontSize:19,fontWeight:'900',color:colors.navy}}>{c.name||c.title}</Text><Text style={{color:colors.muted,marginTop:4}} numberOfLines={2}>{c.short_description||c.description||'No description added yet.'}</Text><View style={{flexDirection:'row',gap:7,marginTop:9,flexWrap:'wrap'}}><Badge>{c.level||'Beginner'}</Badge><Badge tone="purple">{c.exam||c.category||'General'}</Badge><Badge tone={c.is_published?'green':'orange'}>{c.is_published?'Published':'Draft'}</Badge></View></View></View><View style={{flexDirection:'row',flexWrap:'wrap',gap:8,marginTop:14}}><Button title="Manage Course →" onPress={()=>openCourse(api.idOf(c))}/><Button title="Edit" variant="secondary" onPress={()=>edit(c)}/><Button title="Delete" variant="danger" onPress={()=>remove(c)}/></View></Card>)}
 </>}</AppShell>;
}
