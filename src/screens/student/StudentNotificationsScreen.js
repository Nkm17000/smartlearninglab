import React,{useEffect,useState} from 'react';
import {Text,View} from 'react-native';
import {AppShell,Button,Card,Empty,ErrorState,Header,Loading} from '../../components/UI';
import {api} from '../../services/api';
import {colors} from '../../theme';

export default function StudentNotificationsScreen(){
 const [items,setItems]=useState(null),[error,setError]=useState('');
 const load=async()=>{try{setError('');setItems(api.listOf(await api.notifications()))}catch(e){setError(e.message)}};
 useEffect(()=>{load()},[]);
 if(error)return <AppShell><Header title="Notifications"/><ErrorState title="Notifications could not load" message={error} onRetry={load}/></AppShell>;
 if(!items)return <AppShell><Loading label="Loading notifications…"/></AppShell>;
 return <AppShell><Header title="Notifications" subtitle="Updates about your learning activity." right={<Button title="Mark all read" variant="secondary" onPress={async()=>{await api.markNotificationsRead();load()}}/>}/>
 {items.length===0?<Empty title="You're all caught up" message="New course, lesson and quiz updates will appear here."/>:items.map(n=><Card key={api.idOf(n)} style={{borderColor:n.read?colors.border:'#F9A8D4'}}><View style={{flexDirection:'row',gap:12}}><Text style={{fontSize:24}}>🔔</Text><View style={{flex:1}}><Text style={{fontWeight:'900',color:colors.navy}}>{n.title}</Text><Text style={{color:colors.muted,marginTop:4}}>{n.message}</Text><Text style={{fontSize:11,color:colors.subtle,marginTop:6}}>{n.created_at||''}</Text></View></View></Card>)}
 </AppShell>;
}
