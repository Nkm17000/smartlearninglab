import React,{useEffect,useState} from 'react';
import {Alert,Text,View} from 'react-native';
import {AppShell,Button,Card,ErrorState,Field,Header,Loading,Empty} from '../../components/UI';
import {api} from '../../services/api';
import {colors} from '../../theme';
export default function CommunityScreen(){
 const [posts,setPosts]=useState(null),[show,setShow]=useState(false),[title,setTitle]=useState(''),[content,setContent]=useState(''),[error,setError]=useState('');
 const load=async()=>{try{setError('');setPosts(api.listOf(await api.communityPosts()))}catch(e){setError(e?.message||'Unable to load the community.')}};useEffect(()=>{load()},[]);
 const add=async()=>{try{await api.createCommunityPost({title,content});setTitle('');setContent('');setShow(false);load()}catch(e){Alert.alert('Community',e.message)}};
 if(error)return <AppShell><Header title="Community" subtitle="Ask questions, share ideas and learn together"/><ErrorState title="Community could not load" message={error} onRetry={load}/></AppShell>;
 if(!posts)return <AppShell><Header title="Community" subtitle="Ask questions, share ideas and learn together"/><Loading label="Loading community…"/></AppShell>;
 return <AppShell><Header eyebrow="Community" title="Learning Community" subtitle="Discuss courses, interview questions and study strategies." right={<Button title={show?'Close':'+ New Post'} onPress={()=>setShow(!show)}/>}/>{show&&<Card><Field label="Title" value={title} onChangeText={setTitle} placeholder="How do I improve my speaking fluency?"/><Field label="Message" value={content} onChangeText={setContent} multiline placeholder="Share your question or tip..."/><Button title="Publish post" onPress={add} disabled={!title.trim()||!content.trim()}/></Card>}{posts.length===0?<Empty title="No discussions yet" message="Start the first discussion."/>:posts.map(p=><Card key={api.idOf(p)}><View style={{flexDirection:'row',justifyContent:'space-between',gap:10}}><Text style={{fontSize:17,fontWeight:'900',color:colors.navy,flex:1}}>{p.title}</Text><Text style={{color:colors.primary,fontWeight:'900'}}>♥ {p.likes||0}</Text></View><Text style={{color:colors.muted,marginTop:7}}>{p.author_name||'Learner'}</Text><Text style={{color:colors.text,lineHeight:20,marginTop:10}}>{p.content}</Text><View style={{marginTop:10}}><Button title="Like" variant="secondary" onPress={async()=>{try{await api.likeCommunityPost(api.idOf(p));load()}catch(e){Alert.alert('Community',e.message)}}}/></View></Card>)}</AppShell>
}
