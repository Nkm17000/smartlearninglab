import React,{useEffect,useState} from 'react';
import {Alert,Pressable,Text,View} from 'react-native';
import {AppShell,Badge,Button,Card,Empty,ErrorState,Field,Header,Loading,Select} from '../../components/UI';
import {api} from '../../services/api';
import {colors} from '../../theme';

const exams=['SSC','Banking','Railway','Teaching','UPSC','Defence','State Exams','Computer'];

function CourseCard({c,onOpen}){
 const name=c.name||c.title||'Course';
 return <Pressable onPress={()=>onOpen(api.idOf(c))} style={({pressed})=>({opacity:pressed ? 0.85 : 1})}>
  <Card style={{width:290,minWidth:260,padding:0,overflow:'hidden'}}>
   <View style={{height:112,backgroundColor:c.banner_url?'#fff':colors.navy,alignItems:'center',justifyContent:'center'}}>{c.banner_url?<Text style={{color:colors.muted,fontWeight:'800'}}>COURSE BANNER</Text>:<Text style={{fontSize:38}}>📚</Text>}</View>
   <View style={{padding:15}}><View style={{flexDirection:'row',gap:6,marginBottom:8}}><Badge tone="pink">{c.is_free===false?'Paid':'FREE'}</Badge><Badge>{c.level||'Beginner'}</Badge></View><Text style={{fontSize:17,fontWeight:'900',color:colors.navy}} numberOfLines={2}>{name}</Text><Text style={{fontSize:12,color:colors.muted,marginTop:5}} numberOfLines={2}>{c.short_description||c.description||'Structured learning with lessons, practice and tests.'}</Text><View style={{flexDirection:'row',gap:12,marginTop:11}}><Text style={{fontSize:12,color:colors.muted}}>🎥 {c.video_count||0}</Text><Text style={{fontSize:12,color:colors.muted}}>📄 {c.pdf_count||0}</Text><Text style={{fontSize:12,color:colors.muted}}>📝 {c.mock_test_count||0}</Text></View><Text style={{fontSize:12,color:colors.primary,fontWeight:'900',marginTop:12}}>View course →</Text></View>
  </Card>
 </Pressable>
}

function QuizCard({q,onOpen}){return <Card style={{width:300,minWidth:260}}><View style={{flexDirection:'row',gap:10,alignItems:'center'}}><View style={{width:42,height:42,borderRadius:12,backgroundColor:colors.pinkSoft,alignItems:'center',justifyContent:'center'}}><Text>📝</Text></View><View style={{flex:1}}><Text style={{fontWeight:'900',color:colors.navy}} numberOfLines={2}>{q.title||q.name}</Text><Text style={{fontSize:12,color:colors.muted,marginTop:3}}>{q.duration_minutes||15} min · {(q.question_ids||[]).length} questions</Text></View></View><Button title="Attempt test" onPress={()=>onOpen(api.idOf(q))} style={{marginTop:12}}/></Card>}

export default function StudentHomeScreen({user,onLogout,openCourse,openQuiz}){
 const [search,setSearch]=useState(''),[activeExam,setActiveExam]=useState(''),[data,setData]=useState(null),[cats,setCats]=useState(null),[error,setError]=useState('');
 const load=async()=>{try{setError('');await api.syncOffline();const results=await Promise.allSettled([api.studentDashboard(),api.catalogCategories(),api.featuredCatalog(10),api.studentQuizzes(),api.analytics()]);const [d,c,f,q,a]=results;if(d.status!=='fulfilled')throw d.reason;const featured=f.status==='fulfilled'?api.listOf(f.value?.courses):[];const featuredQuizzes=f.status==='fulfilled'?api.listOf(f.value?.quizzes):[];const allQuizzes=q.status==='fulfilled'?api.listOf(q.value):[];setData({dashboard:d.value,analytics:a.status==='fulfilled'?a.value:null,featured,quizzes:featuredQuizzes.length?featuredQuizzes:allQuizzes});setCats(c.status==='fulfilled'?c.value:null)}catch(e){setError(e?.message||'Unable to load your learning home.')}};
 useEffect(()=>{load()},[]);
 const searchCourses=async()=>{try{const c=await api.studentCourses({search,category:activeExam});setData(x=>({...x,searchResults:api.listOf(c)}))}catch(e){Alert.alert('Search',e.message)}};
 if(error)return <AppShell><Header title="Smart Learning Lab"/><ErrorState title="Learning data could not load" message={error} onRetry={load}/></AppShell>;
 if(!data)return <AppShell><Loading label="Preparing your learning home…"/></AppShell>;
 const courses=data.searchResults||data.featured||[];
 return <AppShell>
  <Card style={{backgroundColor:colors.navy,borderColor:colors.navy,padding:25}}><View style={{maxWidth:850}}><Badge tone="pink">FREE LEARNING PLATFORM</Badge><Text style={{fontSize:30,fontWeight:'900',color:'#fff',marginTop:10}}>Prepare smarter. Learn every day.</Text><Text style={{color:'#CBD5E1',fontSize:15,lineHeight:23,marginTop:7}}>Courses, topic-wise lessons, mock tests, question practice and progress — all in one place.</Text><View style={{flexDirection:'row',gap:8,marginTop:18,alignItems:'center'}}><View style={{flex:1,minWidth:240}}><Field value={search} onChangeText={setSearch} placeholder="Search courses, exams, topics…"/></View><Button title="Search" onPress={searchCourses}/></View></View></Card>
  <View style={{flexDirection:'row',flexWrap:'wrap',gap:10,marginBottom:12}}>{[['Courses',data.dashboard?.courses_available||0],['Lessons done',data.dashboard?.lessons_completed||0],['Quiz average',`${data.dashboard?.quiz_average||0}%`],['Tests attempted',data.dashboard?.quiz_attempts||0],['🔥 Streak',`${data.analytics?.streak?.current||0} days`],['XP',data.analytics?.xp||0]].map(([a,b])=><Card key={a} style={{flex:1,minWidth:170,marginBottom:0}}><Text style={{fontSize:12,color:colors.muted,fontWeight:'800'}}>{a}</Text><Text style={{fontSize:25,fontWeight:'900',color:colors.navy,marginTop:5}}>{b}</Text></Card>)}</View>
  <Text style={{fontSize:20,fontWeight:'900',color:colors.navy,marginTop:8,marginBottom:10}}>Explore by exam</Text>
  <View style={{flexDirection:'row',flexWrap:'wrap',gap:8,marginBottom:15}}>{[...(cats?.exams||[]),...exams.filter(x=>!(cats?.exams||[]).includes(x))].slice(0,12).map(x=><Pressable key={x} onPress={()=>{setActiveExam(activeExam===x?'':x);setTimeout(searchCourses,0)}} style={{paddingHorizontal:14,paddingVertical:10,borderRadius:22,borderWidth:1,borderColor:activeExam===x?colors.primary:colors.border,backgroundColor:activeExam===x?colors.pinkSoft:'#fff'}}><Text style={{fontWeight:'800',color:activeExam===x?colors.primary:colors.text}}>{x}</Text></Pressable>)}</View>
  <View style={{flexDirection:'row',justifyContent:'space-between',alignItems:'center',marginBottom:10}}><View><Text style={{fontSize:20,fontWeight:'900',color:colors.navy}}>{data.searchResults?'Search results':'Featured courses'}</Text><Text style={{fontSize:12,color:colors.muted,marginTop:3}}>Curated learning paths with practice built in.</Text></View></View>
  {courses.length===0?<Empty title="No courses found" message="Try another search or exam category."/>:<View style={{flexDirection:'row',flexWrap:'wrap',gap:14}}>{courses.map(c=><CourseCard key={api.idOf(c)} c={c} onOpen={openCourse}/>)}</View>}
  <Text style={{fontSize:20,fontWeight:'900',color:colors.navy,marginTop:18,marginBottom:10}}>Test series & mock tests</Text>
  {data.quizzes?.length?<View style={{flexDirection:'row',flexWrap:'wrap',gap:14}}>{data.quizzes.slice(0,8).map(q=><QuizCard key={api.idOf(q)} q={q} onOpen={openQuiz}/>)}</View>:<Empty title="No published tests yet" message="Your admin can publish free quizzes from the Test Series section."/>}
  <Text style={{fontSize:20,fontWeight:'900',color:colors.navy,marginTop:18,marginBottom:10}}>Why use Smart Learning Lab?</Text>
  <View style={{flexDirection:'row',flexWrap:'wrap',gap:12}}>{[['🎯','Topic-wise learning','Follow a clear curriculum from beginner to advanced.'],['📝','Unlimited practice','Build question banks and take mock tests.'],['📈','Track progress','Know what you completed and where to improve.'],['🤖','AI Tutor','Ask questions while learning and revise faster.']].map(([i,t,d])=><Card key={t} style={{flex:1,minWidth:240}}><Text style={{fontSize:25}}>{i}</Text><Text style={{fontSize:16,fontWeight:'900',color:colors.navy,marginTop:8}}>{t}</Text><Text style={{fontSize:12,color:colors.muted,lineHeight:18,marginTop:4}}>{d}</Text></Card>)}</View>
 </AppShell>
}
