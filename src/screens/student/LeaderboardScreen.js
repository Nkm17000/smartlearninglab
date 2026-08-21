import React,{useEffect,useState} from 'react';
import {Text,View} from 'react-native';
import {AppShell,Badge,Card,Empty,ErrorState,Header,Loading} from '../../components/UI';
import {api} from '../../services/api';
import {colors} from '../../theme';

export default function LeaderboardScreen(){
 const [data,setData]=useState(null),[error,setError]=useState('');
 const load=async()=>{try{setError('');setData(await api.leaderboard(20));}catch(e){setError(e.message)}};
 useEffect(()=>{load()},[]);
 if(error)return <AppShell><Header title="Leaderboard"/><ErrorState title="Leaderboard could not load" message={error} onRetry={load}/></AppShell>;
 if(!data)return <AppShell><Loading label="Loading leaderboard…"/></AppShell>;
 return <AppShell><Header eyebrow="Community" title="Leaderboard" subtitle="Learn, practice and climb the rankings."/>
  {data.me&&<Card style={{backgroundColor:colors.pinkSoft,borderColor:'#F9A8D4'}}><Text style={{fontSize:12,color:colors.primary,fontWeight:'900'}}>YOUR RANK</Text><Text style={{fontSize:28,fontWeight:'900',color:colors.navy,marginTop:5}}>#{data.me.rank}</Text><Text style={{color:colors.muted}}>{data.me.xp} XP · {data.me.lessons} lessons · {data.me.tests} tests</Text></Card>}
  {data.items.length===0?<Empty title="No students yet"/>:data.items.map(row=><Card key={row.id} style={{paddingVertical:13}}><View style={{flexDirection:'row',alignItems:'center',gap:12}}><View style={{width:38,height:38,borderRadius:19,backgroundColor:row.rank===1?'#FEF3C7':row.rank===2?'#F3F4F6':row.rank===3?'#FFEDD5':'#F8FAFC',alignItems:'center',justifyContent:'center'}}><Text style={{fontWeight:'900'}}>#{row.rank}</Text></View><View style={{flex:1}}><Text style={{fontWeight:'900',color:colors.navy}}>{row.name}</Text><Text style={{fontSize:12,color:colors.muted}}>{row.lessons} lessons · {row.tests} tests</Text></View><Badge tone={row.rank<=3?'orange':'blue'}>{row.xp} XP</Badge></View></Card>)}
 </AppShell>;
}
