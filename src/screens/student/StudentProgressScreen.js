import React,{useEffect,useState} from 'react';
import {Text,View} from 'react-native';
import {AppShell,Badge,Card,Empty,ErrorState,Header,Loading} from '../../components/UI';
import {api} from '../../services/api';
import {colors} from '../../theme';

export default function StudentProgressScreen(){
 const [courses,setCourses]=useState([]),[progress,setProgress]=useState(null),[results,setResults]=useState([]),[error,setError]=useState('');
 const load=async()=>{try{setError('');const [c,p,r]=await Promise.all([api.studentCourses(),api.progress(),api.allResults()]);setCourses(api.listOf(c));setProgress(api.listOf(p));setResults(api.listOf(r))}catch(e){setError(e.message)}};
 useEffect(()=>{load()},[]);
 if(error)return <AppShell><ErrorState title="Progress could not load" message={error} onRetry={load}/></AppShell>;
 if(!progress)return <AppShell><Loading label="Loading your progress…"/></AppShell>;
 return <AppShell><Header eyebrow="Student" title="My Progress" subtitle="See completed lessons and quiz performance."/>
 {courses.map(c=>{const cid=api.idOf(c);const done=progress.filter(p=>p.course_id===cid&&p.completed).length;return <Card key={cid}><View style={{flexDirection:'row',alignItems:'center',gap:10}}><Text style={{fontSize:24}}>📘</Text><View style={{flex:1}}><Text style={{fontSize:17,fontWeight:'900',color:colors.navy}}>{c.name||c.title}</Text><Text style={{color:colors.muted}}>{done} completed lessons</Text></View><Badge tone={done?'green':'blue'}>{done?'In progress':'Not started'}</Badge></View></Card>})}
 <Text style={{fontSize:20,fontWeight:'900',color:colors.navy,marginTop:8,marginBottom:10}}>Quiz results</Text>
 {results.length===0?<Empty title="No quiz attempts yet" message="Complete a published quiz to see your result here."/>:results.map(r=>{const x=r.result||r;return <Card key={api.idOf(r)}><View style={{flexDirection:'row',justifyContent:'space-between',alignItems:'center'}}><View><Text style={{fontWeight:'900',color:colors.navy}}>Quiz attempt</Text><Text style={{color:colors.muted,marginTop:4}}>{x.correct_count||0} correct · {x.wrong_count||0} wrong</Text></View><Badge tone={x.passed?'green':'red'}>{x.percentage??0}%</Badge></View></Card>})}
 </AppShell>
}
