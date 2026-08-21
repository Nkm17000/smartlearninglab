import React,{useEffect,useState} from 'react';
import {Alert,Text,View} from 'react-native';
import {AppShell,Badge,Button,Card,ErrorState,Header,Loading} from '../../components/UI';
import {api} from '../../services/api';
import {colors} from '../../theme';

export default function AdminHomeScreen({navigate}){
 const [data,setData]=useState(null),[error,setError]=useState('');
 const load=()=>{setError('');setData(null);api.adminDashboard().then(setData).catch(e=>setError(e.message))};
 useEffect(()=>{load()},[]);
 if(error)return <AppShell><Header title="Admin dashboard" subtitle="Your learning platform at a glance."/><ErrorState title="Dashboard could not load" message={error} onRetry={load}/></AppShell>;
 if(!data)return <AppShell><Header title="Admin dashboard" subtitle="Loading your learning platform…"/><Loading label="Loading dashboard…"/></AppShell>;
 const stats=[['Courses',data.courses||0,colors.primary],['Lessons',data.lessons||0,colors.purple],['Questions',data.questions||0,colors.warning],['Quizzes',data.quizzes||0,colors.success],['Students',data.students||0,'#0891B2']];
 return <AppShell><Header title="Good morning, Admin 👋" subtitle="Everything you need to manage your learning platform."/><Card style={{backgroundColor:colors.navy,borderColor:colors.navy}}><Text style={{color:'#fff',fontSize:22,fontWeight:'900'}}>Build great learning content</Text><Text style={{color:'#CBD5E1',marginTop:6}}>Create a course, add lessons, build a question bank and publish a quiz.</Text><View style={{flexDirection:'row',flexWrap:'wrap',gap:9,marginTop:16}}><Button title="+ Course" onPress={()=>navigate('courses')} /><Button title="+ Question" variant="secondary" onPress={()=>navigate('questions')}/><Button title="+ Quiz" variant="secondary" onPress={()=>navigate('quizzes')}/></View></Card><View style={{flexDirection:'row',flexWrap:'wrap',gap:12}}>{stats.map(([label,value,color])=><Card key={label} style={{flex:1,minWidth:175}}><View style={{width:10,height:10,borderRadius:5,backgroundColor:color}}/><Text style={{color:colors.muted,fontWeight:'700',marginTop:10}}>{label}</Text><Text style={{fontSize:30,fontWeight:'900',color:colors.navy,marginTop:4}}>{String(value)}</Text></Card>)}</View><Text style={{fontSize:19,fontWeight:'900',color:colors.navy,marginTop:8,marginBottom:10}}>Recommended workflow</Text><Card><View style={{flexDirection:'row',flexWrap:'wrap',gap:10}}>{['1. Create course','2. Add modules','3. Add lessons','4. Add questions','5. Create quiz','6. Publish'].map((x,i)=><Badge key={i} tone={i%2?'purple':'blue'}>{x}</Badge>)}</View></Card></AppShell>;
}
