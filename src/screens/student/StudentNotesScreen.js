import React,{useEffect,useState} from 'react';
import {Alert,Text} from 'react-native';
import {AppShell,Button,Card,Empty,ErrorState,Field,Header,Loading} from '../../components/UI';
import {api} from '../../services/api';
import {colors} from '../../theme';
export default function StudentNotesScreen(){
 const [notes,setNotes]=useState(null),[show,setShow]=useState(false),[title,setTitle]=useState(''),[content,setContent]=useState(''),[error,setError]=useState('');
 const load=async()=>{try{setError('');setNotes(api.listOf(await api.notes()))}catch(e){setError(e?.message||'Unable to load notes.')}}; useEffect(()=>{load()},[]);
 const save=async()=>{try{await api.addNote({title,content});setTitle('');setContent('');setShow(false);load()}catch(e){Alert.alert('Note error',e.message)}};
 if(error)return <AppShell><Header title="My Notes"/><ErrorState title="Notes could not load" message={error} onRetry={load}/></AppShell>;
 return <AppShell><Header title="My Notes" subtitle="Keep useful explanations and study points in one place." right={<Button title={show?'Close':'+ Note'} onPress={()=>setShow(!show)}/>}/>{show&&<Card><Field label="Title" value={title} onChangeText={setTitle} placeholder="Present simple"/><Field label="Note" value={content} onChangeText={setContent} multiline placeholder="Write your study note..."/><Button title="Save Note" onPress={save} disabled={!content.trim()}/></Card>}{!notes?<Loading label="Loading your notes…"/>:notes.length===0?<Empty title="No notes yet" message="Save your first study note."/>:notes.map(n=><Card key={api.idOf(n)}><Text style={{fontSize:17,fontWeight:'900',color:colors.navy}}>{n.title||'Study note'}</Text><Text style={{color:colors.text,lineHeight:21,marginTop:7}}>{n.content||n.note}</Text></Card>)}</AppShell>;
}
