import React,{useEffect,useState} from 'react';
import {Alert,Text,View} from 'react-native';
import {AppShell,Button,Card,Empty,ErrorState,Header,Loading,Badge} from '../../components/UI';
import {api} from '../../services/api';
import {colors} from '../../theme';

export default function AdminStudentsScreen(){
 const [items,setItems]=useState(null),[error,setError]=useState('');
 const load=()=>{setError('');api.students().then(x=>setItems(api.listOf(x))).catch(e=>setError(e.message))};
 useEffect(()=>{load()},[]);
 const toggle=async s=>{try{await api.studentStatus(api.idOf(s),!s.is_active);load()}catch(e){Alert.alert('Student',e.message)}};
 return <AppShell><Header eyebrow="Administration" title="Students" subtitle="View registered learners and manage account status."/>
 {error?<ErrorState title="Students could not load" message={error} onRetry={load}/>:!items?<Loading label="Loading students…"/>:items.length===0?<Empty title="No students yet" message="Students will appear here after registration."/>:
 items.map(s=><Card key={api.idOf(s)}><View style={{flexDirection:'row',alignItems:'center',gap:12}}><View style={{width:46,height:46,borderRadius:23,backgroundColor:colors.blueSoft,alignItems:'center',justifyContent:'center'}}><Text style={{fontWeight:'900',color:colors.primary}}>{(s.name||'S').slice(0,1).toUpperCase()}</Text></View><View style={{flex:1}}><Text style={{fontSize:17,fontWeight:'900',color:colors.navy}}>{s.name}</Text><Text style={{color:colors.muted}}>{s.email}</Text></View><Badge tone={s.is_active?'green':'red'}>{s.is_active?'Active':'Disabled'}</Badge><Button title={s.is_active?'Disable':'Enable'} variant={s.is_active?'danger':'secondary'} onPress={()=>toggle(s)}/></View></Card>)}
 </AppShell>
}
