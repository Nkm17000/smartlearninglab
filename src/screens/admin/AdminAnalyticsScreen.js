import React,{useEffect,useState} from 'react';
import {Text,View} from 'react-native';
import {AppShell,Card,Empty,ErrorState,Header,Loading} from '../../components/UI';
import {api} from '../../services/api';
import {colors} from '../../theme';

export default function AdminAnalyticsScreen(){
 const [data,setData]=useState(null),[advanced,setAdvanced]=useState(null),[error,setError]=useState('');
 const load=async()=>{try{setError('');const [basic,adv]=await Promise.all([api.adminAnalytics(),api.adminAdvancedAnalytics()]);setData(basic);setAdvanced(adv)}catch(e){setError(e.message)}};
 useEffect(()=>{load()},[]);
 if(error)return <AppShell><Header title="Analytics"/><ErrorState title="Analytics could not load" message={error} onRetry={load}/></AppShell>;
 if(!data)return <AppShell><Loading label="Loading platform analytics…"/></AppShell>;
 const stats=[['Students',data.students],['Courses',data.courses],['Published courses',data.published_courses],['Enrollments',data.enrollments],['Quiz attempts',data.quiz_attempts],['Reviews',data.reviews],['Average quiz score',`${data.average_quiz_score}%`]];
 return <AppShell><Header eyebrow="Platform" title="Analytics" subtitle="Understand engagement, learning and course performance."/>
 <View style={{flexDirection:'row',flexWrap:'wrap',gap:12}}>{stats.map(([l,v])=><Card key={l} style={{flex:1,minWidth:180}}><Text style={{fontSize:12,color:colors.muted,fontWeight:'800'}}>{l}</Text><Text style={{fontSize:26,fontWeight:'900',color:colors.navy,marginTop:6}}>{v}</Text></Card>)}</View>
 {advanced&&<Card><Text style={{fontSize:19,fontWeight:'900',color:colors.navy}}>Advanced platform analytics</Text><View style={{flexDirection:'row',flexWrap:'wrap',gap:10,marginTop:12}}>{[['Courses',advanced.courses],['Students',advanced.students],['Enrollments',advanced.enrollments],['Attempts',advanced.quiz_attempts],['Avg score',`${advanced.average_quiz_score}%`]].map(([l,v])=><View key={l} style={{padding:12,backgroundColor:'#F8FAFC',borderRadius:12,minWidth:115}}><Text style={{fontSize:11,color:colors.muted,fontWeight:'800'}}>{l}</Text><Text style={{fontSize:20,fontWeight:'900',color:colors.navy,marginTop:3}}>{v}</Text></View>)}</View>{advanced.top_courses?.map((c,i)=><Text key={i} style={{marginTop:7,color:colors.text}}>#{i+1} {c.course} — {c.students} students</Text>)}</Card>}
 <Card><Text style={{fontSize:19,fontWeight:'900',color:colors.navy}}>Popular courses</Text>{data.popular_courses?.length?data.popular_courses.map(c=><View key={c.id} style={{paddingVertical:12,borderBottomWidth:1,borderBottomColor:colors.border}}><View style={{flexDirection:'row',justifyContent:'space-between'}}><Text style={{fontWeight:'900',color:colors.navy}}>{c.name}</Text><Text style={{fontWeight:'900',color:colors.primary}}>{c.rating||0} ★</Text></View><Text style={{fontSize:12,color:colors.muted,marginTop:3}}>{c.students||0} students</Text></View>):<Empty title="No course analytics yet"/>}</Card>
 </AppShell>;
}
