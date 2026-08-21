import React,{useEffect,useState} from 'react';
import {Alert,Pressable,ScrollView,Text,View,useWindowDimensions} from 'react-native';
import {AppShell,Badge,Button,Card,Empty,ErrorState,Field,Header,Loading,ProgressBar,Select} from '../../components/UI';
import {api} from '../../services/api';
import {colors} from '../../theme';

export default function StudentCourseScreen({courseId,onBack,openQuiz}){
 const {width}=useWindowDimensions();
 const mobile=width<700;
 const [data,setData]=useState(null),[progress,setProgress]=useState(null),[completed,setCompleted]=useState([]),[tab,setTab]=useState('overview'),[error,setError]=useState(''),[rating,setRating]=useState(5),[review,setReview]=useState(''),[reviews,setReviews]=useState([]),[bookmarked,setBookmarked]=useState(false);
 const load=async()=>{try{setError('');const results=await Promise.allSettled([api.courseOverview(courseId),api.courseProgress(courseId),api.progress(),api.reviews(courseId),api.bookmarks()]);
   const [o,p,allProgress,rv,bm]=results;
   if(o.status!=='fulfilled') throw o.reason;
   setData(o.value);
   setProgress(p.status==='fulfilled'?p.value:null);
   setCompleted(allProgress.status==='fulfilled'?api.listOf(allProgress.value).filter(x=>String(x.course_id)===String(courseId)&&x.completed).map(x=>String(x.lesson_id)):[]);
   setReviews(rv.status==='fulfilled'?api.listOf(rv.value):[]);
   setBookmarked(bm.status==='fulfilled'?api.listOf(bm.value).some(x=>x.item_type==='course'&&String(x.item_id)===String(courseId)):false);
 }catch(e){setError(e?.message||'Unable to open this course.')}};
 useEffect(()=>{load()},[courseId]);
 if(error)return <AppShell><Header title="Course" right={<Button title="← Back" variant="secondary" onPress={onBack}/>}/><ErrorState title="Course could not load" message={error} onRetry={load}/></AppShell>;
 if(!data)return <AppShell><Loading label="Opening course…"/></AppShell>;
 const c=data.course||{},mods=data.modules||[],lessons=data.lessons||[],quizzes=data.quizzes||[];
 const pct=Number(progress?.percentage||0);
 const complete=async l=>{try{await api.completeLesson(api.idOf(l));const [p,all]=await Promise.all([api.courseProgress(courseId),api.progress()]);setProgress(p);setCompleted(api.listOf(all).filter(x=>String(x.course_id)===String(courseId)&&x.completed).map(x=>String(x.lesson_id)))}catch(e){Alert.alert('Progress',e.message)}};
 const enroll=async()=>{try{await api.enroll(courseId);Alert.alert('Enrolled','The course is now in My Learning.')}catch(e){Alert.alert('Enrollment',e.message)}};
 const bookmark=async()=>{try{if(bookmarked){Alert.alert('Bookmark','This course is already saved. Open Bookmarks to manage it.');return;}await api.addBookmark({item_type:'course',item_id:courseId,title:c.name||c.title});setBookmarked(true)}catch(e){Alert.alert('Bookmark',e.message)}};
 const submitReview=async()=>{try{await api.addReview(courseId,{rating,review});setReview('');const r=await api.reviews(courseId);setReviews(api.listOf(r));Alert.alert('Thank you','Your review has been saved.')}catch(e){Alert.alert('Review',e.message)}};
 const certificate=async()=>{try{const x=await api.issueCertificate(courseId);Alert.alert('Certificate ready',x.certificate_id)}catch(e){Alert.alert('Certificate',e.message)}};
 const tabs=[['overview','Overview'],['curriculum','Curriculum'],['tests','Tests'],['resources','Resources'],['reviews','Reviews']];
 return <AppShell>
   <View style={{marginBottom:8}}>
    <Text style={{fontSize:12,color:colors.muted,fontWeight:'800'}}>Home  ›  Courses  ›  {c.name||c.title||'Course'}</Text>
   </View>
   <Header eyebrow="Course overview" title={c.name||c.title||'Course'} subtitle={c.short_description||c.description||'Learn through structured topics, lessons, resources and assessments.'} right={<View style={{flexDirection:'row',gap:8,flexWrap:'wrap',justifyContent:'flex-end'}}><Button title={bookmarked?'🔖 Saved':'🔖 Save'} variant="secondary" onPress={bookmark}/><Button title="← Back" variant="secondary" onPress={onBack}/></View>}/>
   <Card style={{backgroundColor:colors.navy,borderColor:colors.navy,padding:mobile?18:24}}>
    <View style={{flexDirection:mobile?'column':'row',gap:18}}>
      <View style={{flex:1}}>
       <View style={{flexDirection:'row',flexWrap:'wrap',gap:7}}><Badge tone="pink">{c.is_free===false?'PAID':'FREE COURSE'}</Badge><Badge>{c.level||'Beginner'}</Badge><Badge tone="purple">{c.category||'General'}</Badge><Badge tone="green">{c.language||'English'}</Badge></View>
       <Text style={{fontSize:mobile?25:32,fontWeight:'900',color:'#fff',marginTop:12}}>{c.name||c.title}</Text>
       <Text style={{color:'#CBD5E1',lineHeight:22,marginTop:7}}>{c.description||c.short_description||'Build practical skills with topic-wise lessons and assessments.'}</Text>
       <View style={{flexDirection:'row',flexWrap:'wrap',gap:8,marginTop:15}}>{[['🎥',c.video_count||0,'Videos'],['📄',c.pdf_count||0,'PDFs'],['📝',c.mock_test_count||quizzes.length,'Tests'],['⏱',`${c.estimated_minutes||0} min`,'Duration']].map(([icon,val,label])=><View key={label} style={{backgroundColor:'rgba(255,255,255,.09)',borderRadius:12,padding:10,minWidth:90}}><Text style={{color:'#CBD5E1',fontSize:11}}>{icon} {label}</Text><Text style={{color:'#fff',fontWeight:'900',marginTop:3}}>{val}</Text></View>)}</View>
       <Button title="Start / Add to My Learning" onPress={enroll} style={{marginTop:16}}/>
      </View>
      <View style={{width:mobile?'100%':250,backgroundColor:'#fff',borderRadius:16,padding:17}}>
       <Text style={{fontWeight:'900',color:colors.navy}}>Your course progress</Text>
       <Text style={{fontSize:34,fontWeight:'900',color:colors.primary,marginTop:4}}>{pct}%</Text>
       <ProgressBar value={pct}/>
       <Text style={{fontSize:12,color:colors.muted,marginTop:7}}>{progress?.completed_lessons||0} of {progress?.total_lessons||lessons.length||0} lessons complete</Text>
       {pct>0&&pct<100&&<Text style={{fontSize:12,color:colors.success,fontWeight:'800',marginTop:10}}>Keep going — you're making progress.</Text>}
      </View>
    </View>
   </Card>
   <Card style={{padding:0,overflow:'hidden'}}>
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{paddingHorizontal:8}}>
     {tabs.map(([x,label])=><Pressable key={x} onPress={()=>setTab(x)} style={{paddingHorizontal:15,paddingVertical:13,borderBottomWidth:3,borderBottomColor:tab===x?colors.primary:'transparent'}}><Text style={{fontWeight:'900',color:tab===x?colors.primary:colors.muted}}>{label}</Text></Pressable>)}
    </ScrollView>
   </Card>
   {tab==='overview'&&<>
    <Card><Text style={{fontSize:19,fontWeight:'900',color:colors.navy}}>About this course</Text><Text style={{color:colors.text,lineHeight:22,marginTop:8}}>{c.description||'Build practical skills through structured topic-wise lessons and assessments.'}</Text></Card>
    {Array.isArray(c.learning_objectives)&&c.learning_objectives.length>0&&<Card><Text style={{fontSize:19,fontWeight:'900',color:colors.navy}}>What you'll learn</Text>{c.learning_objectives.map((x,i)=><Text key={i} style={{marginTop:9,color:colors.text}}>✓ {x}</Text>)}</Card>}
   </>}
   {tab==='curriculum'&&<>
    <Text style={{fontSize:20,fontWeight:'900',color:colors.navy,marginBottom:10}}>Course curriculum</Text>
    {mods.length===0?<Empty title="Curriculum is not published yet" message="The course is available, but no modules have been published."/>:mods.map((m,mi)=>{const ls=lessons.filter(l=>String(l.topic_id)===String(api.idOf(m)));return <Card key={api.idOf(m)}>
      <View style={{flexDirection:'row',alignItems:'center',gap:10}}><View style={{width:40,height:40,borderRadius:12,backgroundColor:colors.blueSoft,alignItems:'center',justifyContent:'center'}}><Text style={{fontWeight:'900',color:colors.primary}}>{mi+1}</Text></View><View style={{flex:1}}><Text style={{fontSize:17,fontWeight:'900',color:colors.navy}}>{m.name||m.title}</Text>{m.description&&<Text style={{fontSize:12,color:colors.muted,marginTop:3}}>{m.description}</Text>}</View></View>
      {ls.length===0?<Text style={{color:colors.muted,marginTop:12}}>No lessons published in this module yet.</Text>:ls.map((l,i)=>{const lid=api.idOf(l),done=completed.includes(lid);return <View key={lid} style={{flexDirection:mobile?'column':'row',alignItems:mobile?'stretch':'center',gap:10,paddingVertical:12,borderTopWidth:1,borderTopColor:colors.border,marginTop:9}}>
        <View style={{width:36,height:36,borderRadius:10,backgroundColor:done?colors.greenSoft:colors.background,alignItems:'center',justifyContent:'center'}}><Text>{done?'✓':'📖'}</Text></View><View style={{flex:1}}><Text style={{fontWeight:'800',color:colors.navy}}>{i+1}. {l.title||l.name}</Text><Text style={{fontSize:12,color:colors.muted,marginTop:3}}>{l.duration_minutes||10} min {l.resources?.length?`· ${l.resources.length} resources`:''}</Text></View><Button title={done?'Completed':'Mark complete'} variant={done?'success':'secondary'} onPress={()=>complete(l)} /></View>})}
     </Card>})}
   </>}
   {tab==='tests'&&<>
    <Text style={{fontSize:20,fontWeight:'900',color:colors.navy,marginBottom:10}}>Tests & assessments</Text>
    {quizzes.length===0?<Empty title="No tests published" message="Tests attached to this course will appear here."/>:quizzes.map(q=><Card key={api.idOf(q)} style={{borderColor:colors.border}}><View style={{flexDirection:mobile?'column':'row',alignItems:mobile?'stretch':'center',gap:12}}><View style={{width:48,height:48,borderRadius:14,backgroundColor:colors.blueSoft,alignItems:'center',justifyContent:'center'}}><Text style={{fontSize:21}}>📝</Text></View><View style={{flex:1}}><Text style={{fontSize:17,fontWeight:'900',color:colors.navy}}>{q.title||q.name}</Text><Text style={{color:colors.muted,marginTop:4}}>{q.duration_minutes||15} min · {q.question_ids?.length||0} questions · Pass {q.passing_percentage||60}%</Text></View><Button title="Attempt test" onPress={()=>openQuiz(api.idOf(q))}/></View></Card>)}
   </>}
   {tab==='resources'&&<><Card><Text style={{fontSize:19,fontWeight:'900',color:colors.navy}}>Learning resources</Text><Text style={{color:colors.muted,marginTop:5,lineHeight:19}}>Videos, PDFs, notes and practice material attached to published lessons.</Text></Card>{lessons.flatMap(l=>(l.resources||[]).map((r,i)=><Card key={`${api.idOf(l)}-${i}`}><Text style={{fontWeight:'900',color:colors.navy}}>{l.title||l.name}</Text><Text style={{color:colors.primary,marginTop:5}}>{String(r)}</Text></Card>))}</>}
   {tab==='reviews'&&<><Card><Text style={{fontSize:19,fontWeight:'900',color:colors.navy}}>Rate this course</Text><Select label="Rating" value={rating} onChange={setRating} options={[1,2,3,4,5].map(x=>({label:`${x} ★`,value:x}))}/><Field label="Review" value={review} onChangeText={setReview} placeholder="What did you think about the course?" multiline/><Button title="Submit review" onPress={submitReview}/></Card>{reviews.length===0?<Empty title="No reviews yet" message="Be the first learner to review this course."/>:reviews.map(r=><Card key={api.idOf(r)}><Text style={{fontWeight:'900',color:colors.navy}}>{r.user_name||'Learner'} · {r.rating} ★</Text><Text style={{color:colors.muted,marginTop:5}}>{r.review}</Text></Card>)}</>}
   {pct>=100&&<Card style={{backgroundColor:colors.greenSoft,borderColor:'#86EFAC'}}><Text style={{fontSize:18,fontWeight:'900',color:colors.navy}}>🎓 Course completed</Text><Text style={{color:colors.muted,marginTop:5}}>You can now request your certificate.</Text><Button title="Get certificate" variant="success" onPress={certificate} style={{marginTop:12}}/></Card>}
 </AppShell>;
}
